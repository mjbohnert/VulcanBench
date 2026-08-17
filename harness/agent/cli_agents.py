"""Run models inside their own agent CLI (subscription billing).

``claude-code:<model>``, ``codex:<model>``, and ``cursor:<model>`` run a task
in the product's headless CLI instead of the VulcanBench agent loop.  The
external harness owns its prompts, context management, and tools; everything
downstream (git diff, verifier, evaluator, scoring) remains under VulcanBench.

Why this exists: Claude Code authenticates with a Claude subscription
(Pro/Max), so runs bill the subscription instead of API rates — and it is also
a legitimate benchmark target in its own right, since most people use the
model *through* its vendor harness. Two honesty rules follow:

- Results measure **model + vendor harness**, not the VulcanBench uniform
  loop. A ``claude-code:claude-opus-4-8`` column is not comparable to an
  ``anthropic:claude-opus-4-8`` column; the summary records the harness so
  the leaderboard can't silently mix them.
- ``cost_usd`` remains a backward-compatible API-equivalent value.  The
  ``economics`` receipt is authoritative and separates marginal cash, plan
  allocation, quota consumption, and API-equivalent value.

Subscription plans have rolling usage limits. A limit hit raises
:class:`~harness.agent.providers.ProviderError` so the suite records an
*error* (resumable with ``--only-missing``) instead of scoring a starved run
as a 0.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from harness.agent.providers import (
    LLMProvider,
    LLMResponse,
    NonRetryableProviderError,
    ProviderError,
    TokenUsage,
)
from harness.pricing import cost_usd
from harness.redaction import sanitize

CLI_AGENT_PROVIDERS = frozenset({"claude-code", "codex", "cursor", "grok-build"})

# Claude Code's headless result text when a subscription window is exhausted
# (e.g. "Claude AI usage limit reached|...", "5-hour limit reached ∙ resets 3am").
_LIMIT_PATTERN = re.compile(r"usage limit|rate limit|limit reached|limit will reset", re.I)

_SAFE_ENV_KEYS = frozenset(
    {
        "PATH",
        "HOME",
        "SHELL",
        "TMPDIR",
        "LANG",
        "TERM",
        "USER",
        "LOGNAME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "CODEX_HOME",
        "CLAUDE_CONFIG_DIR",
        "GROK_HOME",
    }
)

# The VulcanBench loop has no web tools, so parity default is web-off; the
# ``--network`` flag opts back in (the CLI runs host-side, so this only gates
# the agent's tools, not the host's connectivity).
_WEB_TOOLS = "WebSearch,WebFetch"

# Cursor permission sets. ``allow`` covers the tools a benchmark run needs;
# ``deny`` blocks the web tools that would let an agent fetch its task's own
# upstream fix. The schema requires both keys.
_CURSOR_WEB_DENIED_PERMISSIONS = {
    "allow": [
        "Shell(*)",
        "Read(*)",
        "Write(*)",
        "Edit(*)",
        "Glob(*)",
        "Grep(*)",
        "Delete(*)",
        "Ls(*)",
    ],
    "deny": ["WebFetch(*)", "WebSearch", "WebSearch(*)"],
}

# Single-shot judge/grader calls must not wander the filesystem.
_JUDGE_DISALLOWED_TOOLS = (
    "Bash,Edit,Write,NotebookEdit,Read,Glob,Grep,WebSearch,WebFetch,Task,TodoWrite"
)

_ISSUE_SUFFIX = (
    "\n\nSolve this issue in the current repository. Make the smallest correct "
    "change and run the tests to verify it. Leave your changes uncommitted in "
    "the working tree — do not create git commits."
)


class _Collector(Protocol):
    def record(self, event_type: str, data: dict[str, Any]) -> None: ...


class SubscriptionQuotaError(NonRetryableProviderError):
    """A rolling subscription limit that should pause, not hot-loop retries."""


@dataclass(frozen=True)
class HarnessCapabilities:
    """Features an external harness can prove to VulcanBench."""

    harness: str
    display_name: str
    executable: str
    structured_events: bool
    reports_tokens: bool
    reports_model: bool
    supports_effort: bool
    supports_live_cost_cap: bool
    sandbox: str

    def as_summary(self) -> dict[str, Any]:
        return {
            "harness": self.harness,
            "display_name": self.display_name,
            "executable": self.executable,
            "structured_events": self.structured_events,
            "reports_tokens": self.reports_tokens,
            "reports_model": self.reports_model,
            "supports_effort": self.supports_effort,
            "supports_live_cost_cap": self.supports_live_cost_cap,
            "sandbox": self.sandbox,
        }


@dataclass(frozen=True)
class HarnessPreflight:
    """Non-secret readiness receipt returned by ``harness doctor``."""

    harness: str
    available: bool
    version: str | None
    authenticated: bool
    auth_mode: str | None
    plan_name: str | None = None
    detail: str | None = None

    @property
    def ready(self) -> bool:
        return self.available and self.authenticated and self.auth_mode == "subscription"

    def as_summary(self) -> dict[str, Any]:
        return {
            "harness": self.harness,
            "available": self.available,
            "version": self.version,
            "authenticated": self.authenticated,
            "auth_mode": self.auth_mode,
            "plan_name": self.plan_name,
            "ready": self.ready,
            "detail": self.detail,
        }


class CliAgentAdapter(Protocol):
    """Contract implemented by subscription-backed execution harnesses."""

    @property
    def harness_id(self) -> str: ...

    def capabilities(self) -> HarnessCapabilities: ...

    def preflight(self) -> HarnessPreflight: ...

    def run_task(self, **kwargs: Any) -> CliAgentOutcome: ...


def is_cli_agent_spec(spec: str) -> bool:
    """True when ``spec`` selects a vendor agent CLI (e.g. ``claude-code:...``)."""
    provider = spec.partition(":")[0].strip().lower()
    return provider in CLI_AGENT_PROVIDERS


def build_cli_prompt(issue: str) -> str:
    """The kickoff prompt handed to the agent CLI for a task."""
    return f"# Issue\n\n{issue}{_ISSUE_SUFFIX}"


def _subscription_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Minimal environment for a subscription CLI process.

    Provider API keys and unrelated shell secrets are deliberately absent. The
    CLI can still find its executable and cached browser/keychain login through
    ``PATH`` and ``HOME``.  Test adapters may add explicit non-secret values via
    ``extra``.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if key in _SAFE_ENV_KEYS or key.startswith("LC_")
    }
    # PATH leaks this checkout's location (.venv/bin sits under the repo), and
    # a live grok run was observed extracting the prefix and running
    # `find <repo> -name cargo` over it. Scrub repo-rooted entries: the CLIs
    # find their own binaries through the remaining entries.
    repo_root = str(Path(__file__).resolve().parents[2])
    if "PATH" in env:
        env["PATH"] = os.pathsep.join(
            p for p in env["PATH"].split(os.pathsep) if p and not p.startswith(repo_root)
        )
    env["DISABLE_AUTOUPDATER"] = "1"
    if extra:
        env.update(extra)
    return env


def _fold_usage(usage: dict[str, Any]) -> tuple[int, int]:
    """Anthropic usage -> (effective prompt tokens, completion tokens).

    Same fold as ``AnthropicProvider``: ``input_tokens`` is the uncached
    remainder; cache reads bill ~0.1x and cache writes ~1.25x.
    """
    uncached = int(usage.get("input_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
    cache_write = int(usage.get("cache_creation_input_tokens", 0) or 0)
    prompt = round(uncached + cache_read * 0.1 + cache_write * 1.25)
    return prompt, int(usage.get("output_tokens", 0) or 0)


def _fold_usage_totals(usages: Iterable[dict[str, Any]]) -> tuple[int, int]:
    prompt = completion = 0
    for usage in usages:
        p, c = _fold_usage(usage)
        prompt += p
        completion += c
    return prompt, completion


def _version(executable: str) -> str | None:
    if shutil.which(executable) is None:
        return None
    try:
        proc = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            env=_subscription_env(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or proc.stderr).strip()
    return text.splitlines()[0] if text else None


def _claude_preflight(claude_bin: str = "claude") -> HarnessPreflight:
    version = _version(claude_bin)
    if version is None:
        return HarnessPreflight(
            harness="claude-code",
            available=False,
            version=None,
            authenticated=False,
            auth_mode=None,
            detail=f"{claude_bin!r} not found on PATH",
        )
    try:
        proc = subprocess.run(
            [claude_bin, "auth", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            env=_subscription_env(),
            check=False,
        )
        body = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return HarnessPreflight(
            harness="claude-code",
            available=True,
            version=version,
            authenticated=False,
            auth_mode=None,
            detail=f"could not read Claude authentication status: {exc}",
        )
    logged_in = bool(body.get("loggedIn"))
    auth_method = str(body.get("authMethod") or "").lower()
    subscription = logged_in and auth_method == "claude.ai"
    return HarnessPreflight(
        harness="claude-code",
        available=True,
        version=version,
        authenticated=logged_in,
        auth_mode="subscription" if subscription else (auth_method or None),
        plan_name=str(body.get("subscriptionType") or "") or None,
        detail=None if subscription else "Claude Code is not using a Claude subscription login",
    )


def _codex_preflight(codex_bin: str = "codex") -> HarnessPreflight:
    version = _version(codex_bin)
    if version is None:
        return HarnessPreflight(
            harness="codex",
            available=False,
            version=None,
            authenticated=False,
            auth_mode=None,
            detail=f"{codex_bin!r} not found on PATH",
        )
    try:
        proc = subprocess.run(
            [codex_bin, "login", "status"],
            capture_output=True,
            text=True,
            timeout=15,
            env=_subscription_env(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return HarnessPreflight(
            harness="codex",
            available=True,
            version=version,
            authenticated=False,
            auth_mode=None,
            detail=f"could not read Codex authentication status: {exc}",
        )
    status = f"{proc.stdout}\n{proc.stderr}".strip().lower()
    authenticated = proc.returncode == 0 and "not logged in" not in status
    subscription = authenticated and "chatgpt" in status
    api_key = authenticated and ("api key" in status or "api-key" in status)
    return HarnessPreflight(
        harness="codex",
        available=True,
        version=version,
        authenticated=authenticated,
        auth_mode="subscription" if subscription else ("api" if api_key else None),
        detail=None if subscription else "Codex is not using a ChatGPT subscription login",
    )


def _cursor_preflight(cursor_bin: str = "cursor-agent") -> HarnessPreflight:
    version = _version(cursor_bin)
    if version is None:
        return HarnessPreflight(
            harness="cursor",
            available=False,
            version=None,
            authenticated=False,
            auth_mode=None,
            detail=f"{cursor_bin!r} not found on PATH",
        )
    if os.environ.get("CURSOR_API_KEY"):
        # API-key auth bills xAI/OpenAI-style metered usage, not the Cursor
        # plan; fail closed exactly like a signed-out Claude Code or Codex.
        return HarnessPreflight(
            harness="cursor",
            available=True,
            version=version,
            authenticated=True,
            auth_mode="api-key",
            detail="CURSOR_API_KEY is set; unset it to bill the Cursor subscription",
        )
    try:
        proc = subprocess.run(
            [cursor_bin, "status"],
            capture_output=True,
            text=True,
            timeout=15,
            env=_subscription_env(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return HarnessPreflight(
            harness="cursor",
            available=True,
            version=version,
            authenticated=False,
            auth_mode=None,
            detail=f"`{cursor_bin} status` failed: {exc}",
        )
    status_text = (proc.stdout or "") + (proc.stderr or "")
    if re.search(r"not logged in", status_text, re.I):
        return HarnessPreflight(
            harness="cursor",
            available=True,
            version=version,
            authenticated=False,
            auth_mode=None,
            detail=f"signed out; run `{cursor_bin} login`",
        )
    plan_match = re.search(r"(?:plan|membership)\s*[:=]?\s*(\S[^\n]*)", status_text, re.I)
    return HarnessPreflight(
        harness="cursor",
        available=True,
        version=version,
        authenticated=True,
        auth_mode="subscription",
        plan_name=plan_match.group(1).strip() if plan_match else None,
    )


def run_cursor_task(  # noqa: PLR0912, PLR0915 — linear stream-parse loop
    *,
    workspace: Path,
    prompt: str,
    model: str,
    priced_spec: str,
    max_turns: int,
    collector: _Collector,
    stream_log_path: Path | None = None,
    timeout_s: float | None = None,
    network: bool = False,
    max_run_cost: float | None = None,
    effort: str | None = None,
    cursor_bin: str = "cursor-agent",
    env_overrides: dict[str, str] | None = None,
    preflight: HarnessPreflight | None = None,
) -> CliAgentOutcome:
    """Run one task through ``cursor-agent -p`` billed to the Cursor account.

    Cursor's stream-json reports no token usage or cost, so the outcome carries
    zero token counts and the economics receipt honestly records the
    API-equivalent value as unavailable — Cursor's own dashboard is the only
    ledger for what a run consumed. ``max_turns`` cannot be forwarded (no such
    flag) and ``max_run_cost`` cannot be enforced live (no streamed usage).
    """
    del priced_spec, max_turns
    workspace = workspace.resolve()
    if timeout_s is not None and timeout_s <= 0:
        raise ProviderError("run budget exhausted before CLI agent start")
    if max_run_cost is not None:
        raise ProviderError(
            "cursor-agent reports no usage stream, so --max-run-cost cannot be "
            "enforced; use a wall-clock --timeout for subscription runs"
        )

    checked = preflight or _cursor_preflight(cursor_bin)
    _require_subscription(checked)
    if not network:
        # Web parity with the loop (which has no web tools) and with
        # claude-code's --disallowedTools. Without this, v3's post-cutoff
        # decontamination is defeated at runtime: tasks derive from public
        # merged PRs, and an unrestricted agent does fetch the exact upstream
        # fix (observed in Harness Study No. 01).
        #
        # Verified against cursor-agent 2026.08, and the mechanism is fussy:
        #   * --force approves every permission query, INCLUDING denied ones,
        #     so a deny list under --force is silently useless.
        #   * --trust honours denies, but with no allow list it also rejects
        #     shell calls, which the benchmark needs for running tests.
        # So: --trust plus an explicit allow list for the work tools, and a
        # deny list for web. Both keys are required by the config schema.
        cursor_dir = workspace / ".cursor"
        cursor_dir.mkdir(exist_ok=True)
        (cursor_dir / "cli.json").write_text(
            json.dumps({"permissions": _CURSOR_WEB_DENIED_PERMISSIONS}, indent=1),
            encoding="utf-8",
        )
    # Cursor's per-model bracket syntax carries effort when the loop resolved a
    # supported level (e.g. "grok-4.6[effort=high]").
    model_arg = f"{model}[effort={effort}]" if effort else model
    cmd = [
        cursor_bin,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--model",
        model_arg,
        "--sandbox",
        "enabled",
        # --force would override the web deny; --trust honours it and the
        # allow list above restores the tools a run needs.
        "--force" if network else "--trust",
    ]

    collector.record(
        "cli_agent_start",
        {
            "harness": "cursor",
            "argv": [cmd[0], "-p", "<prompt omitted>", *cmd[3:]],
            "harness_version": checked.version,
        },
    )
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=workspace,
            env=_subscription_env(env_overrides),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ProviderError(
            f"{cursor_bin!r} not found on PATH; install the Cursor CLI and run `{cursor_bin} login`"
        ) from exc

    stderr_chunks: list[str] = []

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for chunk in proc.stderr:
            stderr_chunks.append(chunk)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    outcome = CliAgentOutcome(
        harness="cursor",
        execution_boundary=(
            "host-workspace; cursor-sandbox=enabled; "
            + ("force-allow; web-allowed" if network else "trust+allowlist; web-denied")
        ),
        requested_model=model,
        harness_version=checked.version,
        auth_method=checked.auth_mode,
        plan_name=checked.plan_name,
    )
    killed = {"timeout": False}

    def _kill_on_timeout() -> None:
        killed["timeout"] = True
        proc.kill()

    watchdog: threading.Timer | None = None
    if timeout_s is not None:
        watchdog = threading.Timer(timeout_s, _kill_on_timeout)
        watchdog.daemon = True
        watchdog.start()

    result_msg: dict[str, Any] | None = None
    stream_f = stream_log_path.open("w", encoding="utf-8") if stream_log_path else None
    try:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if stream_f:
                json.dump(sanitize(event), stream_f)
                stream_f.write("\n")
            etype = event.get("type")
            if etype == "system" and event.get("subtype") == "init":
                outcome.session_id = event.get("session_id")
                reported_model = event.get("model")
                if reported_model:
                    outcome.reported_model = str(reported_model)
                    outcome.model_identity_confidence = "cli-reported"
                collector.record(
                    "cli_agent_init",
                    {
                        "session_id": outcome.session_id,
                        "model": reported_model,
                        "harness_version": outcome.harness_version,
                    },
                )
            elif etype == "assistant":
                msg = event.get("message") or {}
                collector.record("llm_response", _assistant_trace_data(msg))
            elif etype == "tool_call":
                collector.record(
                    "tool_observation" if event.get("subtype") == "completed" else "tool_call",
                    {
                        "tool": event.get("call_id", ""),
                        "result": event.get("result"),
                    },
                )
            elif etype == "result":
                result_msg = event
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if stream_f:
            stream_f.close()

    proc.wait()
    stderr_thread.join(timeout=5)
    outcome.timed_out = killed["timeout"]

    if result_msg is None:
        if killed["timeout"]:
            # Partial work still counts; the caller diffs and verifies it.
            return outcome
        tail = "".join(stderr_chunks)[-500:].strip()
        detail = tail or "no stderr"
        if _LIMIT_PATTERN.search(detail):
            raise SubscriptionQuotaError(
                "cursor usage limit hit — rerun after topping up credits "
                f"(use --only-missing to resume): {detail[:300]}"
            )
        raise ProviderError(
            f"cursor-agent exited without a result (exit {proc.returncode}): {detail}"
        )

    outcome.subtype = result_msg.get("subtype")
    outcome.session_id = result_msg.get("session_id") or outcome.session_id
    result_text = str(result_msg.get("result") or "")
    if result_msg.get("is_error") or outcome.subtype != "success":
        if _LIMIT_PATTERN.search(result_text):
            raise SubscriptionQuotaError(
                "cursor usage limit hit — rerun after topping up credits "
                f"(use --only-missing to resume): {result_text[:300]}"
            )
        raise ProviderError(f"cursor-agent run failed ({outcome.subtype}): {result_text[:300]}")

    outcome.finished = True
    collector.record("cli_agent_result", outcome.summary())
    return outcome


def _grok_build_preflight(grok_bin: str = "grok") -> HarnessPreflight:
    version = _version(grok_bin)
    if version is None:
        return HarnessPreflight(
            harness="grok-build",
            available=False,
            version=None,
            authenticated=False,
            auth_mode=None,
            detail=f"{grok_bin!r} not found on PATH",
        )
    if os.environ.get("XAI_API_KEY"):
        # API-key auth bills metered console.x.ai usage, not the Grok plan;
        # fail closed exactly like CURSOR_API_KEY on the Cursor adapter.
        return HarnessPreflight(
            harness="grok-build",
            available=True,
            version=version,
            authenticated=True,
            auth_mode="api-key",
            detail="XAI_API_KEY is set; unset it to bill the Grok subscription",
        )
    try:
        proc = subprocess.run(
            [grok_bin, "models"],
            capture_output=True,
            text=True,
            timeout=30,
            env=_subscription_env(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return HarnessPreflight(
            harness="grok-build",
            available=True,
            version=version,
            authenticated=False,
            auth_mode=None,
            detail=f"`{grok_bin} models` failed: {exc}",
        )
    status_text = (proc.stdout or "") + (proc.stderr or "")
    if re.search(r"not authenticated|not logged in", status_text, re.I):
        return HarnessPreflight(
            harness="grok-build",
            available=True,
            version=version,
            authenticated=False,
            auth_mode=None,
            detail=f"signed out; run `{grok_bin} login`",
        )
    login_match = re.search(r"logged in with\s+(\S+)", status_text, re.I)
    return HarnessPreflight(
        harness="grok-build",
        available=True,
        version=version,
        authenticated=True,
        auth_mode="subscription",
        plan_name=login_match.group(1).strip().rstrip(".") if login_match else None,
    )


# Tools Grok Build must not have on a decontaminated suite. Removal via
# --disallowed-tools is airtight (the model cannot call a tool that does not
# exist), at the cost of the "refused attempts" telemetry the Cursor study
# had — a deliberate trade after Harness Study No. 01 showed how fussy
# permission-layer denies are. --deny WebFetch rides along as a second layer.
_GROK_WEB_TOOLS = "web_search,web_fetch"


def _grok_session_dir(session_id: str) -> Path | None:
    """Locate ``~/.grok/sessions/**/<session_id>`` for the trace artifacts."""
    home = Path(os.environ.get("GROK_HOME") or Path.home() / ".grok")
    root = home / "sessions"
    if not root.is_dir():
        return None
    for candidate in root.rglob(session_id):
        if candidate.is_dir() and (candidate / "summary.json").exists():
            return candidate
    return None


def _harvest_grok_trace(  # noqa: PLR0912 — linear artifact-copy + fold loop
    session_dir: Path,
    run_dir: Path,
    stream_f: Any,
    outcome: CliAgentOutcome,
) -> None:
    """Copy session artifacts into the run dir and fold them into the stream.

    Grok's live streaming-json is text/thought/end only; every tool call
    (with ``toolCallId`` and ``rawInput`` — the audit substrate) lives in the
    session's ``updates.jsonl``. Appending those records to the stream log is
    what lets ``run_audit`` see grok runs at all.
    """
    dest = run_dir / "grok-session"
    dest.mkdir(exist_ok=True)
    max_tokens = 0
    for name in ("summary.json", "updates.jsonl", "events.jsonl"):
        src = session_dir / name
        if not src.exists():
            continue
        shutil.copy2(src, dest / name)
    updates = session_dir / "updates.jsonl"
    if updates.exists() and stream_f is not None:
        with updates.open(encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                meta = (record.get("params") or {}).get("_meta") or {}
                total = meta.get("totalTokens")
                if isinstance(total, int):
                    max_tokens = max(max_tokens, total)
                json.dump(sanitize(record), stream_f)
                stream_f.write("\n")
    if max_tokens:
        outcome.cli_total_tokens = max_tokens
    summary_path = session_dir / "summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        reported = summary.get("current_model_id")
        if reported:
            outcome.reported_model = str(reported)
            outcome.model_identity_confidence = "cli-reported"
        if summary.get("reasoning_effort"):
            outcome.reported_effort = str(summary["reasoning_effort"])
        if summary.get("sandbox_profile"):
            outcome.sandbox_profile = str(summary["sandbox_profile"])


def run_grok_build_task(  # noqa: PLR0912, PLR0915 — linear stream-parse loop
    *,
    workspace: Path,
    prompt: str,
    model: str,
    priced_spec: str,
    max_turns: int,
    collector: _Collector,
    stream_log_path: Path | None = None,
    timeout_s: float | None = None,
    network: bool = False,
    max_run_cost: float | None = None,
    effort: str | None = None,
    grok_bin: str = "grok",
    env_overrides: dict[str, str] | None = None,
    preflight: HarnessPreflight | None = None,
) -> CliAgentOutcome:
    """Run one task through ``grok -p`` billed to the Grok subscription.

    Verified against grok 0.2.69 (alpha), where the flag surface has one trap:
    ``--effort`` parses and is silently IGNORED for reasoning (the session
    keeps the default "high"); ``--reasoning-effort`` is the flag that
    actually moves the knob (accepted: none/minimal/low/medium/high/xhigh —
    confirmed by reading back ``reasoning_effort`` from the session summary).
    The live stream carries no tool calls or usage; both are harvested
    post-run from the session's trace files, which is why the session id is
    chosen up front with ``-s`` (a timeout must still find its trace).

    ``--sandbox strict`` is Seatbelt/Landlock-enforced: reads outside the
    workspace are kernel-denied, which contains the filesystem channel harder
    than Cursor's sandbox did. On macOS the sandbox does NOT block child
    network (curl in a shell still works); web tools are removed instead and
    the audit remains the check on the rest.
    """
    del priced_spec
    workspace = workspace.resolve()
    if timeout_s is not None and timeout_s <= 0:
        raise ProviderError("run budget exhausted before CLI agent start")
    if max_run_cost is not None:
        raise ProviderError(
            "grok reports no priced usage stream, so --max-run-cost cannot be "
            "enforced; use a wall-clock --timeout for subscription runs"
        )

    checked = preflight or _grok_build_preflight(grok_bin)
    _require_subscription(checked)

    session_id = str(uuid.uuid4())
    # Custom kernel sandbox: toolchain parity with other harnesses (read
    # everywhere, write CWD — `strict` also denied ~/.cargo and homebrew,
    # crippling non-Python tasks), plus a kernel deny on this checkout so the
    # answer keys are unreadable even if the agent learns the repo path.
    # Grok fails closed if the profile cannot be applied.
    repo_root = str(Path(__file__).resolve().parents[2])
    grok_dir = workspace / ".grok"
    grok_dir.mkdir(exist_ok=True)
    (grok_dir / "sandbox.toml").write_text(
        f'[profiles.vulcanbench]\nextends = "workspace"\ndeny = ["{repo_root}"]\n',
        encoding="utf-8",
    )
    cmd = [
        grok_bin,
        "-p",
        prompt,
        "--cwd",
        str(workspace),
        "--output-format",
        "streaming-json",
        "--yolo",
        "--no-auto-update",
        # Cross-session memory would let run N+1 remember run N's task —
        # repeat-to-repeat contamination inside one sweep.
        "--no-memory",
        "--sandbox",
        "vulcanbench",
        "--session-id",
        session_id,
        "-m",
        model,
        "--max-turns",
        str(max_turns),
    ]
    if effort:
        # NOT --effort; see docstring.
        cmd += ["--reasoning-effort", effort]
    if not network:
        cmd += ["--disallowed-tools", _GROK_WEB_TOOLS, "--deny", "WebFetch"]

    collector.record(
        "cli_agent_start",
        {
            "harness": "grok-build",
            "argv": [cmd[0], "-p", "<prompt omitted>", *cmd[3:]],
            "harness_version": checked.version,
        },
    )
    env = _subscription_env(env_overrides)
    env["GROK_DISABLE_AUTOUPDATER"] = "1"
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=workspace,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ProviderError(
            f"{grok_bin!r} not found on PATH; install Grok Build and run `{grok_bin} login`"
        ) from exc

    stderr_chunks: list[str] = []

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for chunk in proc.stderr:
            stderr_chunks.append(chunk)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    outcome = CliAgentOutcome(
        harness="grok-build",
        execution_boundary=(
            "host-workspace; grok-sandbox=vulcanbench "
            "(workspace-writes + kernel-denied repo reads); "
            + ("web-allowed" if network else "web-tools-removed")
        ),
        requested_model=model,
        harness_version=checked.version,
        auth_method=checked.auth_mode,
        plan_name=checked.plan_name,
        session_id=session_id,
    )
    killed = {"timeout": False}

    def _kill_on_timeout() -> None:
        killed["timeout"] = True
        proc.kill()

    watchdog: threading.Timer | None = None
    if timeout_s is not None:
        watchdog = threading.Timer(timeout_s, _kill_on_timeout)
        watchdog.daemon = True
        watchdog.start()

    end_msg: dict[str, Any] | None = None
    error_msg: str | None = None
    text_parts: list[str] = []
    thought_chars = 0
    stream_f = stream_log_path.open("w", encoding="utf-8") if stream_log_path else None
    try:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = event.get("type")
            # text/thought chunks are word-level; logging each would bloat the
            # stream log ~100x for no audit value (tool calls arrive later
            # from the trace). Aggregate them and log everything else.
            if etype == "text":
                text_parts.append(str(event.get("data") or ""))
                continue
            if etype == "thought":
                thought_chars += len(str(event.get("data") or ""))
                continue
            if stream_f:
                json.dump(sanitize(event), stream_f)
                stream_f.write("\n")
            if etype == "end":
                end_msg = event
            elif etype == "error":
                error_msg = str(event.get("message") or "")
            elif etype == "max_turns_reached":
                outcome.subtype = "max_turns"
    finally:
        if watchdog is not None:
            watchdog.cancel()
        proc.wait()
        stderr_thread.join(timeout=5)
        if text_parts or thought_chars:
            collector.record(
                "llm_response",
                {
                    "text": "".join(text_parts)[:4000],
                    "thought_chars": thought_chars,
                },
            )
        session_dir = _grok_session_dir(session_id)
        if session_dir is not None and stream_log_path is not None:
            run_dir = stream_log_path.parent
            _harvest_grok_trace(session_dir, run_dir, stream_f, outcome)
        if stream_f:
            stream_f.close()

    outcome.timed_out = killed["timeout"]

    if end_msg is None:
        if killed["timeout"]:
            # Partial work still counts; the caller diffs and verifies it.
            return outcome
        tail = (error_msg or "").strip() or "".join(stderr_chunks)[-500:].strip() or "no stderr"
        if _LIMIT_PATTERN.search(tail):
            raise SubscriptionQuotaError(
                "grok usage limit hit — rerun after the window resets "
                f"(use --only-missing to resume): {tail[:300]}"
            )
        raise ProviderError(f"grok exited without an end event (exit {proc.returncode}): {tail}")

    outcome.subtype = outcome.subtype or str(end_msg.get("stopReason") or "")
    outcome.session_id = end_msg.get("sessionId") or outcome.session_id
    outcome.finished = True
    collector.record("cli_agent_result", outcome.summary())
    return outcome


def _require_subscription(preflight: HarnessPreflight) -> None:
    if preflight.ready:
        return
    detail = preflight.detail or "subscription authentication is not ready"
    raise ProviderError(f"{preflight.harness} preflight failed: {detail}")


@dataclass
class CliAgentOutcome:
    """What a CLI-agent run produced, in the loop's accounting terms."""

    harness: str = "unknown"
    billing: str = "subscription"
    cost_basis: str = "api-equivalent"
    execution_boundary: str | None = None
    requested_model: str | None = None
    reported_model: str | None = None
    model_identity_confidence: str = "requested-only"
    harness_version: str | None = None
    auth_method: str | None = None
    plan_name: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_output_tokens: int = 0
    finished: bool = False
    cost_capped: bool = False
    timed_out: bool = False
    session_id: str | None = None
    subtype: str | None = None
    num_turns: int | None = None
    cli_reported_cost_usd: float | None = None
    # Cumulative context+output total when a CLI reports only that (Grok
    # Build's trace `_meta.totalTokens`); no prompt/completion split exists,
    # so it never feeds pricing — it is provenance, not a bill.
    cli_total_tokens: int | None = None
    reported_effort: str | None = None
    sandbox_profile: str | None = None

    def summary(self) -> dict[str, Any]:
        """Provenance block persisted into the run summary."""
        return {
            "harness": self.harness,
            "harness_version": self.harness_version,
            "billing": self.billing,
            "cost_basis": self.cost_basis,
            "execution_boundary": self.execution_boundary,
            "auth_method": self.auth_method,
            "plan_name": self.plan_name,
            "requested_model": self.requested_model,
            "reported_model": self.reported_model,
            "model_identity_confidence": self.model_identity_confidence,
            "session_id": self.session_id,
            "subtype": self.subtype,
            "num_turns": self.num_turns,
            "cached_input_tokens": self.cached_input_tokens,
            "reasoning_output_tokens": self.reasoning_output_tokens,
            "cli_reported_cost_usd": self.cli_reported_cost_usd,
            "cli_total_tokens": self.cli_total_tokens,
            "reported_effort": self.reported_effort,
            "sandbox_profile": self.sandbox_profile,
        }


def run_claude_code_task(  # noqa: PLR0912, PLR0915 — linear stream-parse loop
    *,
    workspace: Path,
    prompt: str,
    model: str,
    priced_spec: str,
    max_turns: int,
    collector: _Collector,
    stream_log_path: Path | None = None,
    timeout_s: float | None = None,
    network: bool = False,
    max_run_cost: float | None = None,
    effort: str | None = None,
    claude_bin: str = "claude",
    env_overrides: dict[str, str] | None = None,
    preflight: HarnessPreflight | None = None,
) -> CliAgentOutcome:
    """Run one task with Claude Code headless in ``workspace``.

    Streams ``--output-format stream-json`` events into the trace (so
    ``replay.html`` still works), enforces the wall-clock budget with a kill
    timer, and enforces ``max_run_cost`` against the cumulative hypothetical
    API cost of the streamed usage. Partial work survives a timeout or cost
    cap and is diffed/verified by the caller, mirroring the loop's semantics.
    """
    if timeout_s is not None and timeout_s <= 0:
        raise ProviderError("run budget exhausted before CLI agent start")

    checked = preflight or _claude_preflight(claude_bin)
    _require_subscription(checked)

    cmd = [
        claude_bin,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        model,
        "--max-turns",
        str(max_turns),
        "--permission-mode",
        "auto",
        "--safe-mode",
        "--no-session-persistence",
        # Hermetic runs: don't let the operator's user-level config/memory
        # leak instructions into the benchmark.
        "--setting-sources",
        "project",
    ]
    if effort:
        cmd += ["--effort", effort]
    if not network:
        cmd += ["--disallowedTools", _WEB_TOOLS]

    collector.record(
        "cli_agent_start",
        {"harness": "claude-code", "argv": [cmd[0], "-p", "<prompt omitted>", *cmd[3:]]},
    )

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=workspace,
            env=_subscription_env(env_overrides),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise ProviderError(
            f"{claude_bin!r} not found on PATH; install Claude Code and sign in "
            "with your subscription by running `claude` once"
        ) from e

    stderr_chunks: list[str] = []

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for chunk in proc.stderr:
            stderr_chunks.append(chunk)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    outcome = CliAgentOutcome(
        harness="claude-code",
        execution_boundary="host-workspace; permission-mode=auto; safe-mode",
        requested_model=model,
        harness_version=checked.version,
        auth_method=checked.auth_mode,
        plan_name=checked.plan_name,
    )
    killed = {"timeout": False, "cost": False}

    def _kill_on_timeout() -> None:
        killed["timeout"] = True
        proc.kill()

    watchdog: threading.Timer | None = None
    if timeout_s is not None:
        watchdog = threading.Timer(timeout_s, _kill_on_timeout)
        watchdog.daemon = True
        watchdog.start()

    usage_by_msg: dict[str, dict[str, Any]] = {}
    result_msg: dict[str, Any] | None = None
    stream_f = stream_log_path.open("w", encoding="utf-8") if stream_log_path else None
    try:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if stream_f:
                json.dump(sanitize(event), stream_f)
                stream_f.write("\n")
            etype = event.get("type")
            if etype == "system" and event.get("subtype") == "init":
                outcome.session_id = event.get("session_id")
                reported_model = event.get("model")
                if reported_model:
                    outcome.reported_model = str(reported_model)
                    outcome.model_identity_confidence = "cli-reported"
                collector.record(
                    "cli_agent_init",
                    {
                        "session_id": outcome.session_id,
                        "model": reported_model,
                        "harness_version": outcome.harness_version,
                    },
                )
            elif etype == "assistant":
                msg = event.get("message") or {}
                usage = msg.get("usage")
                if isinstance(usage, dict):
                    # Keyed by message id: some CLI versions re-emit a message
                    # per content block; overwriting avoids double counting.
                    usage_by_msg[str(msg.get("id") or len(usage_by_msg))] = usage
                collector.record("llm_response", _assistant_trace_data(msg))
                if max_run_cost is not None:
                    p, c = _fold_usage_totals(usage_by_msg.values())
                    run_cost = cost_usd(priced_spec, p, c)
                    if run_cost is not None and run_cost >= max_run_cost:
                        collector.record(
                            "cost_cap_exceeded",
                            {"cost_usd": run_cost, "max_run_cost": max_run_cost},
                        )
                        outcome.cost_capped = True
                        killed["cost"] = True
                        proc.kill()
                        break
            elif etype == "user":
                for block in (event.get("message") or {}).get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        collector.record(
                            "tool_observation",
                            {
                                "tool": block.get("tool_use_id", ""),
                                "result": block.get("content"),
                                "error": "tool error" if block.get("is_error") else None,
                            },
                        )
            elif etype == "result":
                result_msg = event
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if stream_f:
            stream_f.close()

    proc.wait()
    stderr_thread.join(timeout=5)
    outcome.timed_out = killed["timeout"]

    if result_msg is None:
        # Killed by the budget/cost watchdog (partial work still counts), or
        # the CLI died without reporting — approximate usage from the stream.
        outcome.prompt_tokens, outcome.completion_tokens = _fold_usage_totals(usage_by_msg.values())
        if not (killed["timeout"] or killed["cost"]):
            tail = "".join(stderr_chunks)[-500:].strip()
            raise ProviderError(
                f"claude code exited without a result (exit {proc.returncode}): {tail or 'no stderr'}"
            )
        return outcome

    usage = result_msg.get("usage") or {}
    outcome.prompt_tokens, outcome.completion_tokens = _fold_usage(usage)
    outcome.subtype = result_msg.get("subtype")
    outcome.num_turns = result_msg.get("num_turns")
    outcome.session_id = result_msg.get("session_id") or outcome.session_id
    reported = result_msg.get("total_cost_usd")
    if isinstance(reported, (int, float)):
        outcome.cli_reported_cost_usd = float(reported)
    result_text = str(result_msg.get("result") or "")

    if result_msg.get("is_error") or outcome.subtype != "success":
        if _LIMIT_PATTERN.search(result_text):
            raise SubscriptionQuotaError(
                "claude code subscription limit hit — rerun after the window "
                f"resets (use --only-missing to resume): {result_text[:300]}"
            )
        if outcome.subtype == "error_max_turns":
            # Ran out of turns: a legitimate outcome (like the loop exhausting
            # max_steps); the partial diff is verified and scored honestly.
            collector.record("cli_agent_result", outcome.summary())
            return outcome
        raise ProviderError(f"claude code run failed ({outcome.subtype}): {result_text[:300]}")

    outcome.finished = True
    collector.record("cli_agent_result", outcome.summary())
    return outcome


def _assistant_trace_data(msg: dict[str, Any]) -> dict[str, Any]:
    """Mirror the loop's ``llm_response`` trace shape so replay.html renders."""
    blocks = [b for b in msg.get("content") or [] if isinstance(b, dict)]
    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    tool_calls = [
        {"id": b.get("id", ""), "name": b.get("name", ""), "arguments": b.get("input") or {}}
        for b in blocks
        if b.get("type") == "tool_use"
    ]
    return {"content": text or None, "tool_calls": tool_calls, "usage": msg.get("usage") or {}}


def _codex_item_trace_data(item: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Translate a Codex JSONL item to a replay-compatible event."""
    item_type = item.get("type")
    if item_type == "agent_message":
        return "llm_response", {
            "content": item.get("text"),
            "tool_calls": [],
            "usage": {},
        }
    if item_type == "command_execution":
        return "tool_observation", {
            "tool": "command_execution",
            "command": item.get("command"),
            "result": item.get("aggregated_output") or item.get("output"),
            "exit_code": item.get("exit_code"),
            "status": item.get("status"),
        }
    if item_type in {"file_change", "mcp_tool_call", "web_search"}:
        return "tool_observation", {
            "tool": item_type,
            "result": item,
            "status": item.get("status"),
        }
    return None


def run_codex_task(  # noqa: PLR0912, PLR0915 — linear process/stream adapter
    *,
    workspace: Path,
    prompt: str,
    model: str,
    priced_spec: str,
    max_turns: int,
    collector: _Collector,
    stream_log_path: Path | None = None,
    timeout_s: float | None = None,
    network: bool = False,
    max_run_cost: float | None = None,
    effort: str | None = None,
    codex_bin: str = "codex",
    env_overrides: dict[str, str] | None = None,
    preflight: HarnessPreflight | None = None,
) -> CliAgentOutcome:
    """Run one task through ``codex exec --json`` using ChatGPT auth."""
    del priced_spec, max_turns
    # The subprocess also uses this directory as cwd. Passing a relative path
    # to ``--cd`` would make Codex resolve it a second time from inside itself.
    workspace = workspace.resolve()
    if timeout_s is not None and timeout_s <= 0:
        raise ProviderError("run budget exhausted before CLI agent start")
    if max_run_cost is not None:
        raise ProviderError(
            "codex reports usage at turn completion, so --max-run-cost cannot be "
            "enforced live; use a wall-clock --timeout for subscription runs"
        )

    checked = preflight or _codex_preflight(codex_bin)
    _require_subscription(checked)
    cmd = [
        codex_bin,
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(workspace),
        "--model",
        model,
    ]
    if effort:
        cmd += ["--config", f'model_reasoning_effort="{effort}"']
    if network:
        cmd += ["--config", "sandbox_workspace_write.network_access=true"]
    cmd.append("-")

    collector.record(
        "cli_agent_start",
        {
            "harness": "codex",
            "argv": [*cmd[:-1], "<prompt via stdin>"],
            "harness_version": checked.version,
        },
    )
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=workspace,
            env=_subscription_env(env_overrides),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ProviderError(
            f"{codex_bin!r} not found on PATH; install Codex and run `codex login` "
            "with a ChatGPT subscription"
        ) from exc

    assert proc.stdin is not None
    proc.stdin.write(prompt)
    proc.stdin.close()
    stderr_chunks: list[str] = []

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for chunk in proc.stderr:
            stderr_chunks.append(chunk)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()
    outcome = CliAgentOutcome(
        harness="codex",
        execution_boundary="host-workspace; sandbox=workspace-write",
        requested_model=model,
        harness_version=checked.version,
        auth_method=checked.auth_mode,
        plan_name=checked.plan_name,
    )
    killed = {"timeout": False}

    def _kill_on_timeout() -> None:
        killed["timeout"] = True
        proc.kill()

    watchdog: threading.Timer | None = None
    if timeout_s is not None:
        watchdog = threading.Timer(timeout_s, _kill_on_timeout)
        watchdog.daemon = True
        watchdog.start()

    terminal_error: str | None = None
    saw_turn_completed = False
    stream_f = stream_log_path.open("w", encoding="utf-8") if stream_log_path else None
    try:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if stream_f:
                json.dump(sanitize(event), stream_f)
                stream_f.write("\n")
            event_type = event.get("type")
            if event_type == "thread.started":
                outcome.session_id = event.get("thread_id")
                collector.record(
                    "cli_agent_init",
                    {
                        "session_id": outcome.session_id,
                        "model": model,
                        "harness_version": outcome.harness_version,
                    },
                )
            elif event_type == "item.completed":
                translated = _codex_item_trace_data(event.get("item") or {})
                if translated:
                    collector.record(*translated)
            elif event_type == "turn.completed":
                saw_turn_completed = True
                usage = event.get("usage") or {}
                outcome.prompt_tokens = int(usage.get("input_tokens", 0) or 0)
                outcome.cached_input_tokens = int(usage.get("cached_input_tokens", 0) or 0)
                outcome.completion_tokens = int(usage.get("output_tokens", 0) or 0)
                outcome.reasoning_output_tokens = int(usage.get("reasoning_output_tokens", 0) or 0)
                outcome.subtype = "success"
                outcome.finished = True
            elif event_type in {"turn.failed", "error"}:
                payload = event.get("error") or event.get("message") or event
                terminal_error = str(payload)
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if stream_f:
            stream_f.close()

    proc.wait()
    stderr_thread.join(timeout=5)
    outcome.timed_out = killed["timeout"]
    if outcome.timed_out:
        return outcome
    if not saw_turn_completed or proc.returncode != 0:
        detail = terminal_error or "".join(stderr_chunks)[-500:].strip() or "no error detail"
        if _LIMIT_PATTERN.search(detail):
            raise SubscriptionQuotaError(
                "codex subscription limit hit — rerun after the window resets "
                f"(use --only-missing to resume): {detail[:300]}"
            )
        raise ProviderError(f"codex exec failed (exit {proc.returncode}): {detail[:500]}")
    collector.record("cli_agent_result", outcome.summary())
    return outcome


@dataclass(frozen=True)
class ClaudeCodeAdapter:
    harness_id: str = "claude-code"

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            harness=self.harness_id,
            display_name="Claude Code",
            executable="claude",
            structured_events=True,
            reports_tokens=True,
            reports_model=True,
            supports_effort=True,
            supports_live_cost_cap=True,
            sandbox="native-permission-auto; host workspace",
        )

    def preflight(self) -> HarnessPreflight:
        return _claude_preflight()

    def run_task(self, **kwargs: Any) -> CliAgentOutcome:
        return run_claude_code_task(**kwargs)


@dataclass(frozen=True)
class CodexAdapter:
    harness_id: str = "codex"

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            harness=self.harness_id,
            display_name="Codex CLI",
            executable="codex",
            structured_events=True,
            reports_tokens=True,
            reports_model=False,
            supports_effort=True,
            supports_live_cost_cap=False,
            sandbox="workspace-write",
        )

    def preflight(self) -> HarnessPreflight:
        return _codex_preflight()

    def run_task(self, **kwargs: Any) -> CliAgentOutcome:
        return run_codex_task(**kwargs)


@dataclass(frozen=True)
class CursorAdapter:
    harness_id: str = "cursor"

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            harness=self.harness_id,
            display_name="Cursor CLI",
            executable="cursor-agent",
            structured_events=True,
            # stream-json carries no usage or cost fields: token counts and
            # API-equivalent value are honestly unavailable for cursor runs.
            reports_tokens=False,
            reports_model=True,
            supports_effort=True,
            supports_live_cost_cap=False,
            sandbox="cursor-sandbox=enabled; force-allow",
        )

    def preflight(self) -> HarnessPreflight:
        return _cursor_preflight()

    def run_task(self, **kwargs: Any) -> CliAgentOutcome:
        return run_cursor_task(**kwargs)


@dataclass(frozen=True)
class GrokBuildAdapter:
    harness_id: str = "grok-build"

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            harness=self.harness_id,
            display_name="Grok Build",
            executable="grok",
            structured_events=True,
            # The trace reports a cumulative totalTokens with no
            # prompt/completion split, so priced token accounting is off.
            reports_tokens=False,
            reports_model=True,
            supports_effort=True,
            supports_live_cost_cap=False,
            sandbox="grok-sandbox=strict (Seatbelt/Landlock)",
        )

    def preflight(self) -> HarnessPreflight:
        return _grok_build_preflight()

    def run_task(self, **kwargs: Any) -> CliAgentOutcome:
        return run_grok_build_task(**kwargs)


_CLI_AGENT_ADAPTERS: dict[str, CliAgentAdapter] = {
    "claude-code": ClaudeCodeAdapter(),
    "codex": CodexAdapter(),
    "cursor": CursorAdapter(),
    "grok-build": GrokBuildAdapter(),
}


def get_cli_agent_adapter(spec_or_name: str) -> CliAgentAdapter:
    """Resolve a harness name or ``harness:model`` spec to its adapter."""
    name = spec_or_name.partition(":")[0].strip().lower()
    try:
        return _CLI_AGENT_ADAPTERS[name]
    except KeyError as exc:
        known = ", ".join(sorted(_CLI_AGENT_ADAPTERS))
        raise ValueError(f"unknown execution harness {name!r}; known: {known}") from exc


def list_cli_agent_adapters() -> list[CliAgentAdapter]:
    """All external harness adapters in stable display order."""
    return [_CLI_AGENT_ADAPTERS[name] for name in sorted(_CLI_AGENT_ADAPTERS)]


class ClaudeCodeProvider(LLMProvider):
    """Single-shot completions through Claude Code headless.

    Used for judge/grader calls when the run model is a ``claude-code:`` spec,
    so evaluation also bills the subscription. Tool calling is not supported —
    judges and graders are plain prompt-in/JSON-out completions.
    """

    @property
    def name(self) -> str:
        return "claude-code"

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_s: float | None = None,
        effort: str | None = None,
    ) -> LLMResponse:
        del tools, effort
        _require_subscription(_claude_preflight())
        system = "\n\n".join(
            str(m.get("content", "")) for m in messages if m.get("role") == "system"
        ).strip()
        prompt = "\n\n".join(
            str(m.get("content", "")) for m in messages if m.get("role") != "system"
        )
        cmd = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--model",
            self.model,
            "--max-turns",
            "1",
            "--permission-mode",
            "auto",
            "--safe-mode",
            "--no-session-persistence",
            "--setting-sources",
            "project",
            "--disallowedTools",
            _JUDGE_DISALLOWED_TOOLS,
        ]
        if system:
            cmd += ["--append-system-prompt", system]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s if timeout_s and timeout_s > 0 else 600,
                env=_subscription_env(),
                check=False,
            )
        except FileNotFoundError as e:
            raise ProviderError("'claude' not found on PATH for judge/grader call") from e
        except subprocess.TimeoutExpired as e:
            raise ProviderError("claude code judge/grader call timed out") from e
        if proc.returncode != 0:
            raise ProviderError(
                f"claude code judge call failed (exit {proc.returncode}): "
                f"{(proc.stderr or proc.stdout)[-300:]}"
            )
        try:
            body: dict[str, Any] = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ProviderError(f"claude code returned non-JSON output: {proc.stdout[:200]}") from e
        text = str(body.get("result") or "")
        if body.get("is_error"):
            if _LIMIT_PATTERN.search(text):
                raise SubscriptionQuotaError(f"claude code subscription limit hit: {text[:300]}")
            raise ProviderError(f"claude code judge call errored: {text[:300]}")
        p, c = _fold_usage(body.get("usage") or {})
        return LLMResponse(
            content=text or None,
            usage=TokenUsage(prompt_tokens=p, completion_tokens=c),
            raw=body,
        )
