"""Run models inside their vendor's own agent CLI (subscription / usage billing).

``claude-code:<model>`` runs a task with Claude Code headless (``claude -p``),
``codex:<model>`` with OpenAI Codex headless (``codex exec``), and
``cursor:<model>`` with the Cursor Agent CLI (``agent -p`` / ``cursor-agent``),
in the prepared workspace instead of the VulcanBench agent loop. The CLI edits
files directly in the workspace; everything downstream (git diff, verifier,
evaluator, scoring) is unchanged.

Why this exists: vendor CLIs authenticate with a subscription or usage key
(Claude Pro/Max, ChatGPT, Cursor), so runs bill that account instead of a
generic API — and they are also legitimate benchmark targets, since most
people use the model *through* its vendor harness. Two honesty rules follow:

- Results measure **model + vendor harness**, not the VulcanBench uniform
  loop. A ``claude-code:claude-opus-4-8`` column is not comparable to an
  ``anthropic:claude-opus-4-8`` column; the summary records the harness so
  the leaderboard can't silently mix them.
- ``cost_usd`` is computed from the CLI's reported token usage at
  ``harness.pricing`` rates. For ``claude-code:`` / ``codex:`` that is the
  *hypothetical* API cost of the same tokens (``cli_agent.billing =
  "subscription"``). For ``cursor:`` it is Cursor list-price spend
  (``billing = "cursor-usage"``). The CLI's own estimate, when present, is
  kept alongside as ``cli_reported_cost_usd``.

Subscription / usage-limit hits raise
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
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from harness.agent.providers import (
    LLMProvider,
    LLMResponse,
    ProviderError,
    TokenUsage,
)
from harness.pricing import cost_usd
from harness.redaction import sanitize

CLI_AGENT_PROVIDERS = frozenset({"claude-code", "codex", "cursor"})

# Claude Code's headless result text when a subscription window is exhausted
# (e.g. "Claude AI usage limit reached|...", "5-hour limit reached ∙ resets 3am").
_LIMIT_PATTERN = re.compile(r"usage limit|rate limit|limit reached|limit will reset", re.I)

# The VulcanBench loop has no web tools, so parity default is web-off; the
# ``--network`` flag opts back in (the CLI runs host-side, so this only gates
# the agent's tools, not the host's connectivity).
_WEB_TOOLS = "WebSearch,WebFetch"

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


def is_cli_agent_spec(spec: str) -> bool:
    """True when ``spec`` selects a vendor agent CLI (e.g. ``claude-code:...``)."""
    provider = spec.partition(":")[0].strip().lower()
    return provider in CLI_AGENT_PROVIDERS


def build_cli_prompt(issue: str) -> str:
    """The kickoff prompt handed to the agent CLI for a task."""
    return f"# Issue\n\n{issue}{_ISSUE_SUFFIX}"


def _subscription_env() -> dict[str, str]:
    """Subprocess env forcing subscription auth.

    With ``ANTHROPIC_API_KEY`` set, Claude Code bills the API — which defeats
    the point of CLI-agent mode and silently double-spends. Strip it so the
    CLI uses the logged-in subscription (or ``CLAUDE_CODE_OAUTH_TOKEN``).
    """
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
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


@dataclass
class CliAgentOutcome:
    """What a CLI-agent run produced, in the loop's accounting terms."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    finished: bool = False
    cost_capped: bool = False
    timed_out: bool = False
    session_id: str | None = None
    subtype: str | None = None
    num_turns: int | None = None
    cli_reported_cost_usd: float | None = None

    harness: str = "claude-code"
    billing: str = "subscription"
    cost_basis: str = "hypothetical-api-pricing"

    def summary(self) -> dict[str, Any]:
        """Provenance block persisted into the run summary."""
        return {
            "harness": self.harness,
            "billing": self.billing,
            "cost_basis": self.cost_basis,
            "session_id": self.session_id,
            "subtype": self.subtype,
            "num_turns": self.num_turns,
            "cli_reported_cost_usd": self.cli_reported_cost_usd,
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
    claude_bin: str = "claude",
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
        "--dangerously-skip-permissions",
        # Hermetic runs: don't let the operator's user-level config/memory
        # leak instructions into the benchmark.
        "--setting-sources",
        "project",
    ]
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
            env=_subscription_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise ProviderError(
            f"{claude_bin!r} not found on PATH; install Claude Code and sign in "
            "with your subscription (run `claude` once, or set CLAUDE_CODE_OAUTH_TOKEN)"
        ) from e

    stderr_chunks: list[str] = []

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for chunk in proc.stderr:
            stderr_chunks.append(chunk)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    outcome = CliAgentOutcome()
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
                collector.record(
                    "cli_agent_init",
                    {"session_id": outcome.session_id, "model": event.get("model")},
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
            raise ProviderError(
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
                raise ProviderError(f"claude code subscription limit hit: {text[:300]}")
            raise ProviderError(f"claude code judge call errored: {text[:300]}")
        p, c = _fold_usage(body.get("usage") or {})
        return LLMResponse(
            content=text or None,
            usage=TokenUsage(prompt_tokens=p, completion_tokens=c),
            raw=body,
        )


# --------------------------------------------------------------------------
# OpenAI Codex (`codex exec`)
# --------------------------------------------------------------------------


# Codex usage fields -> effective tokens. OpenAI bills cached input at ~0.1x;
# `input_tokens` INCLUDES the cached portion, unlike Anthropic's split fields.
def _fold_codex_usage(usage: dict[str, Any]) -> tuple[int, int]:
    total_in = int(usage.get("input_tokens", 0) or 0)
    cached = min(int(usage.get("cached_input_tokens", 0) or 0), total_in)
    prompt = round((total_in - cached) + cached * 0.1)
    return prompt, int(usage.get("output_tokens", 0) or 0)


def _codex_env() -> dict[str, str]:
    """Subprocess env forcing subscription auth.

    With ``OPENAI_API_KEY`` set, Codex bills the API — which defeats the point
    of CLI-agent mode. Strip it so the CLI uses the ChatGPT-subscription login
    (``codex login``).
    """
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    return env


# Codex reasoning-effort values (config key `model_reasoning_effort`).
_CODEX_EFFORT_VALUES = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "extra-high": "xhigh",
}


def run_codex_task(  # noqa: PLR0912, PLR0915 — linear stream-parse loop
    *,
    workspace: Path,
    prompt: str,
    model: str,
    priced_spec: str,
    collector: _Collector,
    stream_log_path: Path | None = None,
    timeout_s: float | None = None,
    network: bool = False,
    max_run_cost: float | None = None,
    effort: str | None = None,
    codex_bin: str = "codex",
) -> CliAgentOutcome:
    """Run one task with Codex headless (``codex exec --json``) in ``workspace``.

    Mirrors :func:`run_claude_code_task`: streams JSONL events into the trace,
    enforces the wall-clock budget with a kill timer, and enforces
    ``max_run_cost`` against the cumulative hypothetical API cost. Codex has no
    turn cap, so the wall-clock budget is the binding limit. The CLI runs in
    its ``workspace-write`` sandbox (writes confined to the workspace; network
    off unless ``--network``), which matches the loop's parity defaults.
    """
    if timeout_s is not None and timeout_s <= 0:
        raise ProviderError("run budget exhausted before CLI agent start")

    cmd = [
        codex_bin,
        "exec",
        "--json",
        "--model",
        model,
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
    ]
    if network:
        cmd += ["-c", "sandbox_workspace_write.network_access=true"]
    effort_value = _CODEX_EFFORT_VALUES.get(effort or "")
    if effort_value:
        cmd += ["-c", f"model_reasoning_effort={effort_value}"]
    cmd.append(prompt)

    collector.record(
        "cli_agent_start",
        {"harness": "codex", "argv": [*cmd[:-1], "<prompt omitted>"]},
    )

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=workspace,
            env=_codex_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise ProviderError(
            f"{codex_bin!r} not found on PATH; install Codex (npm install -g "
            "@openai/codex) and sign in with your ChatGPT subscription "
            "(`codex login`)"
        ) from e

    stderr_chunks: list[str] = []

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for chunk in proc.stderr:
            stderr_chunks.append(chunk)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    outcome = CliAgentOutcome(harness="codex")
    killed = {"timeout": False, "cost": False}

    def _kill_on_timeout() -> None:
        killed["timeout"] = True
        proc.kill()

    watchdog: threading.Timer | None = None
    if timeout_s is not None:
        watchdog = threading.Timer(timeout_s, _kill_on_timeout)
        watchdog.daemon = True
        watchdog.start()

    prompt_total = completion_total = 0
    turns = 0
    error_text: str | None = None
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
            etype = str(event.get("type") or "")
            if etype == "thread.started":
                outcome.session_id = event.get("thread_id")
                collector.record("cli_agent_init", {"session_id": outcome.session_id})
            elif etype in ("item.completed", "item.updated"):
                item = event.get("item") or {}
                itype = str(item.get("item_type") or item.get("type") or "")
                if etype == "item.completed" and itype in ("assistant_message", "agent_message"):
                    collector.record(
                        "llm_response",
                        {"content": item.get("text"), "tool_calls": [], "usage": {}},
                    )
                elif etype == "item.completed" and itype == "command_execution":
                    collector.record(
                        "tool_observation",
                        {
                            "tool": "run_command",
                            "result": str(item.get("aggregated_output") or "")[:2000],
                            "error": None if item.get("exit_code") in (0, None) else "tool error",
                        },
                    )
                elif itype == "error":
                    error_text = str(item.get("message") or item.get("text") or "")
            elif etype == "turn.completed":
                turns += 1
                usage = event.get("usage") or {}
                p, c = _fold_codex_usage(usage)
                prompt_total += p
                completion_total += c
                if max_run_cost is not None:
                    run_cost = cost_usd(priced_spec, prompt_total, completion_total)
                    if run_cost is not None and run_cost >= max_run_cost:
                        collector.record(
                            "cost_cap_exceeded",
                            {"cost_usd": run_cost, "max_run_cost": max_run_cost},
                        )
                        outcome.cost_capped = True
                        killed["cost"] = True
                        proc.kill()
                        break
            elif etype == "turn.failed":
                error_text = str((event.get("error") or {}).get("message") or "turn failed")
            elif etype == "error":
                error_text = str(event.get("message") or "error")
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if stream_f:
            stream_f.close()

    proc.wait()
    stderr_thread.join(timeout=5)
    outcome.timed_out = killed["timeout"]
    outcome.prompt_tokens = prompt_total
    outcome.completion_tokens = completion_total
    outcome.num_turns = turns or None

    if killed["timeout"] or killed["cost"]:
        # Partial work still counts; the caller diffs and verifies it.
        return outcome

    if error_text and _LIMIT_PATTERN.search(error_text):
        raise ProviderError(
            "codex subscription limit hit — rerun after the window resets "
            f"(use --only-missing to resume): {error_text[:300]}"
        )
    if proc.returncode != 0:
        tail = (error_text or "".join(stderr_chunks)[-500:]).strip()
        if tail and _LIMIT_PATTERN.search(tail):
            raise ProviderError(
                "codex subscription limit hit — rerun after the window resets "
                f"(use --only-missing to resume): {tail[:300]}"
            )
        raise ProviderError(f"codex exited with {proc.returncode}: {tail[:300] or 'no stderr'}")
    if error_text:
        raise ProviderError(f"codex run failed: {error_text[:300]}")

    outcome.finished = True
    outcome.subtype = "success"
    collector.record("cli_agent_result", outcome.summary())
    return outcome


class CodexProvider(LLMProvider):
    """Single-shot completions through Codex headless.

    Used for judge/grader calls when the run model is a ``codex:`` spec, so
    evaluation also bills the subscription. Runs in the read-only sandbox;
    tool calling is not supported — judges and graders are plain
    prompt-in/text-out completions.
    """

    @property
    def name(self) -> str:
        return "codex"

    def complete(  # noqa: PLR0912 — linear stream-parse over event kinds
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_s: float | None = None,
        effort: str | None = None,
    ) -> LLMResponse:
        del tools, effort
        prompt = "\n\n".join(str(m.get("content", "")) for m in messages)
        cmd = [
            "codex",
            "exec",
            "--json",
            "--model",
            self.model,
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            prompt,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s if timeout_s and timeout_s > 0 else 600,
                env=_codex_env(),
                check=False,
            )
        except FileNotFoundError as e:
            raise ProviderError("'codex' not found on PATH for judge/grader call") from e
        except subprocess.TimeoutExpired as e:
            raise ProviderError("codex judge/grader call timed out") from e

        text = ""
        prompt_tokens = completion_tokens = 0
        error_text: str | None = None
        for raw_line in proc.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = str(event.get("type") or "")
            if etype == "item.completed":
                item = event.get("item") or {}
                itype = str(item.get("item_type") or item.get("type") or "")
                if itype in ("assistant_message", "agent_message"):
                    text = str(item.get("text") or "")
                elif itype == "error":
                    error_text = str(item.get("message") or "")
            elif etype == "turn.completed":
                p, c = _fold_codex_usage(event.get("usage") or {})
                prompt_tokens += p
                completion_tokens += c
            elif etype in ("turn.failed", "error"):
                error_text = str(
                    (event.get("error") or {}).get("message") or event.get("message") or "error"
                )
        if error_text and _LIMIT_PATTERN.search(error_text):
            raise ProviderError(f"codex subscription limit hit: {error_text[:300]}")
        if proc.returncode != 0:
            raise ProviderError(
                f"codex judge call failed (exit {proc.returncode}): "
                f"{(error_text or proc.stderr or proc.stdout)[-300:]}"
            )
        if error_text:
            raise ProviderError(f"codex judge call errored: {error_text[:300]}")
        return LLMResponse(
            content=text or None,
            usage=TokenUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
            raw={"stdout_tail": proc.stdout[-1000:]},
        )


# --------------------------------------------------------------------------
# Cursor Agent CLI (`agent -p` / `cursor-agent`)
# --------------------------------------------------------------------------


def _usage_int(usage: dict[str, Any], *keys: str) -> int:
    """First present numeric field among ``keys``, else 0."""
    for key in keys:
        if key not in usage or usage[key] is None:
            continue
        try:
            return int(usage[key] or 0)
        except (TypeError, ValueError):
            continue
    return 0


def _fold_cursor_usage(usage: dict[str, Any]) -> tuple[int, int]:
    """Cursor CLI usage -> (effective prompt tokens, completion tokens).

    The CLI emits camelCase (``inputTokens``) and sometimes snake_case.
    Cache reads bill ~0.1x and cache writes at the input rate; both are
    folded into prompt tokens so ``cost_usd`` tracks list-price spend.
    """
    uncached = _usage_int(usage, "input_tokens", "inputTokens")
    cache_read = _usage_int(
        usage, "cache_read_tokens", "cacheReadTokens", "cache_read_input_tokens"
    )
    cache_write = _usage_int(
        usage, "cache_write_tokens", "cacheWriteTokens", "cache_creation_input_tokens"
    )
    output = _usage_int(usage, "output_tokens", "outputTokens")
    prompt = round(uncached + cache_read * 0.1 + cache_write)
    return prompt, output


def _extract_usage(event: dict[str, Any]) -> dict[str, Any] | None:
    usage = event.get("usage")
    if isinstance(usage, dict):
        return usage
    msg = event.get("message")
    if isinstance(msg, dict):
        nested = msg.get("usage")
        if isinstance(nested, dict):
            return nested
    return None


def _cursor_reported_cost(event: dict[str, Any]) -> float | None:
    for key in ("total_cost_usd", "totalCostUsd", "cost_usd"):
        value = event.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    usage = _extract_usage(event) or {}
    for key in ("total_cost_usd", "totalCostUsd"):
        value = usage.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _cursor_assistant_text(event: dict[str, Any]) -> str | None:
    msg = event.get("message") or {}
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts = [
            str(block.get("text") or "")
            for block in content
            if isinstance(block, dict) and block.get("text")
        ]
        text = "".join(parts).strip()
        return text or None
    raw = event.get("result") or event.get("text")
    return str(raw) if raw else None


def _cursor_tool_trace(event: dict[str, Any]) -> dict[str, Any]:
    """Map a Cursor ``tool_call`` event into the loop's tool_observation shape."""
    tool_call = event.get("tool_call") or {}
    name = "tool"
    result = ""
    if isinstance(tool_call, dict):
        fn = tool_call.get("function")
        if isinstance(fn, dict):
            name = str(fn.get("name") or "function")
            result = str(fn.get("result") or fn.get("arguments") or "")
        else:
            for key, payload in tool_call.items():
                if not isinstance(payload, dict):
                    continue
                name = str(key).removesuffix("ToolCall")
                nested = payload.get("result")
                if isinstance(nested, dict):
                    result = str(nested.get("success") or nested)[:2000]
                else:
                    result = str(nested or payload.get("args") or "")[:2000]
                break
    return {"tool": name, "result": result[:2000], "error": None}


def _resolve_cursor_bin(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("CURSOR_AGENT_BIN")
    if env:
        return env
    for name in ("agent", "cursor-agent"):
        found = shutil.which(name)
        if found:
            return found
    return "agent"


def _cursor_env() -> dict[str, str]:
    """Subprocess env for the Cursor CLI.

    Auth is ``CURSOR_API_KEY`` (or an interactive login). Leave that in place;
    it is how Cursor usage is billed.
    """
    return dict(os.environ)


def run_cursor_task(  # noqa: PLR0912, PLR0915 — linear stream-parse loop
    *,
    workspace: Path,
    prompt: str,
    model: str,
    priced_spec: str,
    collector: _Collector,
    stream_log_path: Path | None = None,
    timeout_s: float | None = None,
    network: bool = False,
    max_run_cost: float | None = None,
    cursor_bin: str | None = None,
) -> CliAgentOutcome:
    """Run one task with the Cursor Agent CLI in ``workspace``.

    Streams ``--output-format stream-json`` events into the trace, enforces
    the wall-clock budget with a kill timer, and enforces ``max_run_cost``
    against the cumulative Cursor list-price cost of reported usage.
    ``--force`` / ``--trust`` are required so headless runs actually edit
    files. The CLI runs host-side (requires ``--sandbox local``).
    """
    del network  # Cursor CLI has no web-tool denylist; host network is unchanged.
    if timeout_s is not None and timeout_s <= 0:
        raise ProviderError("run budget exhausted before CLI agent start")

    bin_name = _resolve_cursor_bin(cursor_bin)
    cmd = [
        bin_name,
        "-p",
        "--output-format",
        "stream-json",
        "--model",
        model,
        "--force",
        "--trust",
        "--workspace",
        str(workspace),
        prompt,
    ]

    collector.record(
        "cli_agent_start",
        {"harness": "cursor", "argv": [*cmd[:-1], "<prompt omitted>"]},
    )

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=workspace,
            env=_cursor_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise ProviderError(
            f"{bin_name!r} not found on PATH; install the Cursor CLI "
            "(https://cursor.com/docs/cli/installation) and set CURSOR_API_KEY, "
            "or point CURSOR_AGENT_BIN at the `agent` / `cursor-agent` binary"
        ) from e

    stderr_chunks: list[str] = []

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for chunk in proc.stderr:
            stderr_chunks.append(chunk)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    outcome = CliAgentOutcome(
        harness="cursor",
        billing="cursor-usage",
        cost_basis="cursor-list-price",
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

    prompt_total = completion_total = 0
    turns = 0
    error_text: str | None = None
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
            etype = str(event.get("type") or "")
            subtype = str(event.get("subtype") or "")
            if etype == "system" and subtype == "init":
                outcome.session_id = event.get("session_id") or event.get("sessionId")
                collector.record(
                    "cli_agent_init",
                    {"session_id": outcome.session_id, "model": event.get("model")},
                )
            elif etype == "assistant":
                collector.record(
                    "llm_response",
                    {
                        "content": _cursor_assistant_text(event),
                        "tool_calls": [],
                        "usage": _extract_usage(event) or {},
                    },
                )
                usage = _extract_usage(event)
                if usage:
                    p, c = _fold_cursor_usage(usage)
                    prompt_total += p
                    completion_total += c
                    turns += 1
                    if max_run_cost is not None:
                        run_cost = cost_usd(priced_spec, prompt_total, completion_total)
                        if run_cost is not None and run_cost >= max_run_cost:
                            collector.record(
                                "cost_cap_exceeded",
                                {"cost_usd": run_cost, "max_run_cost": max_run_cost},
                            )
                            outcome.cost_capped = True
                            killed["cost"] = True
                            proc.kill()
                            break
            elif etype == "tool_call" and subtype == "completed":
                collector.record("tool_observation", _cursor_tool_trace(event))
            elif etype in ("usage",):
                usage = _extract_usage(event) or event
                if isinstance(usage, dict):
                    p, c = _fold_cursor_usage(usage)
                    prompt_total += p
                    completion_total += c
            elif etype == "result":
                result_msg = event
                usage = _extract_usage(event)
                if usage:
                    prompt_total, completion_total = _fold_cursor_usage(usage)
                reported = _cursor_reported_cost(event)
                if reported is not None:
                    outcome.cli_reported_cost_usd = reported
                if event.get("is_error") or subtype not in ("", "success"):
                    error_text = str(event.get("result") or event.get("message") or subtype)
            elif etype == "error":
                error_text = str(event.get("message") or event.get("result") or "error")
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if stream_f:
            stream_f.close()

    proc.wait()
    stderr_thread.join(timeout=5)
    outcome.timed_out = killed["timeout"]
    outcome.prompt_tokens = prompt_total
    outcome.completion_tokens = completion_total
    outcome.num_turns = turns or None
    if result_msg:
        outcome.subtype = str(result_msg.get("subtype") or "") or None
        outcome.session_id = (
            result_msg.get("session_id") or result_msg.get("sessionId") or outcome.session_id
        )

    if killed["timeout"] or killed["cost"]:
        return outcome

    if error_text and _LIMIT_PATTERN.search(error_text):
        raise ProviderError(
            "cursor usage limit hit — rerun after the window resets "
            f"(use --only-missing to resume): {error_text[:300]}"
        )
    if proc.returncode != 0:
        tail = (error_text or "".join(stderr_chunks)[-500:]).strip()
        if tail and _LIMIT_PATTERN.search(tail):
            raise ProviderError(
                "cursor usage limit hit — rerun after the window resets "
                f"(use --only-missing to resume): {tail[:300]}"
            )
        raise ProviderError(
            f"cursor agent exited with {proc.returncode}: {tail[:300] or 'no stderr'}"
        )
    if error_text:
        raise ProviderError(f"cursor agent run failed: {error_text[:300]}")
    if result_msg is None:
        tail = "".join(stderr_chunks)[-500:].strip()
        raise ProviderError(
            f"cursor agent exited without a result (exit {proc.returncode}): {tail or 'no stderr'}"
        )

    outcome.finished = True
    outcome.subtype = outcome.subtype or "success"
    collector.record("cli_agent_result", outcome.summary())
    return outcome


class CursorProvider(LLMProvider):
    """Single-shot completions through the Cursor Agent CLI.

    Used for judge/grader calls when the run model is a ``cursor:`` spec.
    Runs in ``--mode ask`` so the judge cannot edit the workspace.
    """

    @property
    def name(self) -> str:
        return "cursor"

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_s: float | None = None,
        effort: str | None = None,
    ) -> LLMResponse:
        del tools, effort
        prompt = "\n\n".join(str(m.get("content", "")) for m in messages)
        bin_name = _resolve_cursor_bin()
        cmd = [
            bin_name,
            "-p",
            "--output-format",
            "json",
            "--model",
            self.model,
            "--mode",
            "ask",
            "--trust",
            prompt,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s if timeout_s and timeout_s > 0 else 600,
                env=_cursor_env(),
                check=False,
            )
        except FileNotFoundError as e:
            raise ProviderError(f"{bin_name!r} not found on PATH for judge/grader call") from e
        except subprocess.TimeoutExpired as e:
            raise ProviderError("cursor agent judge/grader call timed out") from e
        if proc.returncode != 0:
            raise ProviderError(
                f"cursor agent judge call failed (exit {proc.returncode}): "
                f"{(proc.stderr or proc.stdout)[-300:]}"
            )
        try:
            body: dict[str, Any] = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ProviderError(
                f"cursor agent returned non-JSON output: {proc.stdout[:200]}"
            ) from e
        text = str(body.get("result") or "")
        if body.get("is_error"):
            if _LIMIT_PATTERN.search(text):
                raise ProviderError(f"cursor usage limit hit: {text[:300]}")
            raise ProviderError(f"cursor agent judge call errored: {text[:300]}")
        p, c = _fold_cursor_usage(_extract_usage(body) or {})
        return LLMResponse(
            content=text or None,
            usage=TokenUsage(prompt_tokens=p, completion_tokens=c),
            raw=body,
        )
