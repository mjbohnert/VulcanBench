"""Tests for the vendor agent-CLI runner (``claude-code:`` specs).

A fake ``claude`` binary on PATH emits canned ``stream-json`` output (and
writes the hello-world solution), so the full run_agent pipeline — workspace,
diff, verifier, scoring, hypothetical-API pricing — is exercised offline.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from harness.agent.cli_agents import (
    SubscriptionQuotaError,
    is_cli_agent_spec,
    run_claude_code_task,
    run_codex_task,
    run_cursor_task,
)
from harness.agent.loop import run_agent
from harness.agent.providers import ProviderError, get_provider
from harness.pricing import cost_usd, is_priced
from harness.sandbox.docker_executor import SandboxError

# Result usage: 150 uncached + 50 cache-read (0.1x) + 10 cache-write (1.25x)
# folds to round(167.5) = 168 effective prompt tokens.
FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
mode = os.environ.get("FAKE_CLAUDE_MODE", "success")
api_key_present = "ANTHROPIC_API_KEY" in os.environ
usage = {"input_tokens": 150, "output_tokens": 30,
         "cache_read_input_tokens": 50, "cache_creation_input_tokens": 10}

if "--version" in args:
    print("2.1.198 (Claude Code)")
elif args[:3] == ["auth", "status", "--json"]:
    print(json.dumps({"loggedIn": True, "authMethod": "claude.ai",
                      "subscriptionType": "max"}))
elif "stream-json" in args:
    if mode == "success":
        with open("hello.py", "w") as f:
            f.write('print("hello from vulcanbench")\\n')
    print(json.dumps({"type": "system", "subtype": "init", "session_id": "s1",
                      "model": "claude-opus-4-8", "api_key_present": api_key_present}))
    print(json.dumps({"type": "assistant", "message": {
        "id": "m1",
        "content": [{"type": "text", "text": "Writing the file"},
                    {"type": "tool_use", "id": "t1", "name": "Write",
                     "input": {"file_path": "hello.py"}}],
        "usage": {"input_tokens": 100, "output_tokens": 20,
                  "cache_read_input_tokens": 50, "cache_creation_input_tokens": 10}}}))
    print(json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}}))
    if mode == "limit":
        print(json.dumps({"type": "result", "subtype": "error_during_execution",
                          "is_error": True, "result": "Claude AI usage limit reached|123",
                          "session_id": "s1", "num_turns": 1, "usage": usage}))
    elif mode == "max_turns":
        print(json.dumps({"type": "result", "subtype": "error_max_turns",
                          "is_error": True, "result": "", "session_id": "s1",
                          "num_turns": 2, "total_cost_usd": 0.01, "usage": usage}))
    else:
        print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                          "result": "Done", "session_id": "s1", "num_turns": 2,
                          "total_cost_usd": 0.0123, "usage": usage}))
else:
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                      "result": json.dumps({"score": 80, "rationale": "fake judge"}),
                      "session_id": "s2", "num_turns": 1, "total_cost_usd": 0.001,
                      "usage": usage}))
"""

FAKE_CODEX = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
if "--version" in args:
    print("codex-cli 0.139.0")
elif args[:2] == ["login", "status"]:
    print("Logged in using ChatGPT")
elif args and args[0] == "exec":
    prompt = sys.stdin.read()
    with open("hello.py", "w") as f:
        f.write('print("hello from vulcanbench")\\n')
    print(json.dumps({"type": "thread.started", "thread_id": "thread-1",
                      "api_key_present": "OPENAI_API_KEY" in os.environ or
                                         "CODEX_API_KEY" in os.environ}))
    print(json.dumps({"type": "item.completed", "item": {
        "id": "item-1", "type": "agent_message", "text": "Implemented and tested"}}))
    print(json.dumps({"type": "turn.completed", "usage": {
        "input_tokens": 120, "cached_input_tokens": 80,
        "output_tokens": 30, "reasoning_output_tokens": 10}}))
else:
    print("unsupported", file=sys.stderr)
    sys.exit(1)
"""


FAKE_CURSOR = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
mode = os.environ.get("FAKE_CURSOR_MODE", "success")
if "--version" in args or "-v" in args:
    print("2026.06.19-fake")
elif args[:1] == ["status"]:
    if mode == "logged_out":
        print("Not logged in")
    else:
        print("Logged in as morgan@example.com")
        print("Plan: Pro")
elif "-p" in args:
    model = args[args.index("--model") + 1]
    if mode == "limit":
        print(json.dumps({"type": "result", "subtype": "error",
                          "is_error": True, "result": "Usage limit reached for your plan",
                          "session_id": "cur-1"}))
        sys.exit(0)
    with open("hello.py", "w") as f:
        f.write('print("hello from vulcanbench")\\n')
    print(json.dumps({"type": "system", "subtype": "init", "session_id": "cur-1",
                      "model": model,
                      "leaked_key": os.environ.get("XAI_API_KEY", "")}))
    print(json.dumps({"type": "assistant", "session_id": "cur-1", "message": {
        "role": "assistant", "content": [{"type": "text", "text": "Implemented."}]}}))
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                      "duration_ms": 1200, "duration_api_ms": 800,
                      "result": "done", "session_id": "cur-1"}))
else:
    print("unsupported", file=sys.stderr)
    sys.exit(1)
"""


class _Collector:
    """Minimal TraceCollector stand-in for direct runner tests."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def record(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))


@pytest.fixture()
def fake_claude(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path_factory.mktemp("fakebin")
    script = bin_dir / "claude"
    script.write_text(FAKE_CLAUDE, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    # Must be stripped from the CLI subprocess env (subscription auth only).
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-should-be-stripped")
    monkeypatch.delenv("FAKE_CLAUDE_MODE", raising=False)
    return script


@pytest.fixture()
def fake_codex(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path_factory.mktemp("fake-codex-bin")
    script = bin_dir / "codex"
    script.write_text(FAKE_CODEX, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-should-not-reach-codex")
    monkeypatch.setenv("CODEX_API_KEY", "sk-test-should-not-reach-codex")
    return script


@pytest.fixture
def fake_cursor(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path_factory.mktemp("fake-cursor-bin")
    script = bin_dir / "cursor-agent"
    script.write_text(FAKE_CURSOR, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("XAI_API_KEY", "xai-secret-should-not-reach-cursor")
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.delenv("FAKE_CURSOR_MODE", raising=False)
    return script


def test_spec_detection() -> None:
    assert is_cli_agent_spec("claude-code:claude-opus-4-8")
    assert is_cli_agent_spec("codex:gpt-5.6-sol")
    assert is_cli_agent_spec("cursor:grok-4.6")
    assert not is_cli_agent_spec("anthropic:claude-opus-4-8")
    assert not is_cli_agent_spec("mock:synthetic")


def test_pricing_alias_maps_to_api_rates() -> None:
    assert is_priced("claude-code:claude-opus-4-8")
    assert cost_usd("claude-code:claude-opus-4-8", 1000, 100) == cost_usd(
        "anthropic:claude-opus-4-8", 1000, 100
    )


def test_run_agent_via_claude_code(tmp_path: Path, fake_claude: Path) -> None:
    res = run_agent(
        task_id="hello-world",
        model="claude-code:claude-opus-4-8",
        output_dir=tmp_path,
        tasks_root=Path("tasks/v1"),
        judges=False,
        sandbox="local",
    )
    summary = res["summary"]

    # The CLI's edits go through the same diff/verify/score pipeline.
    assert summary["scores"]["functional"] == 1.0
    assert summary["finished"] is True

    # Usage from the CLI's final result, cache-folded (150 + 5 + 12.5 -> 168).
    assert summary["tokens"]["prompt"] == 168
    assert summary["tokens"]["completion"] == 30

    # cost_usd is the hypothetical API cost at anthropic rates.
    assert summary["cost_usd"] == pytest.approx((168 * 5.00 + 30 * 25.00) / 1_000_000)

    cli = summary["cli_agent"]
    assert cli["harness"] == "claude-code"
    assert cli["billing"] == "subscription"
    assert cli["cost_basis"] == "api-equivalent"
    assert cli["cli_reported_cost_usd"] == 0.0123
    assert cli["session_id"] == "s1"
    assert cli["num_turns"] == 2
    economics = summary["economics"]
    assert economics["billing_mode"] == "subscription-included"
    assert economics["marginal_cash_usd"] is None
    assert economics["api_equivalent_cost_usd"] == summary["cost_usd"]
    assert economics["plan_name"] == "max"

    # Raw stream persisted for audit — and the API key never reached the CLI.
    stream_path = tmp_path / res["run_id"] / "cli-agent-stream.jsonl"
    events = [json.loads(line) for line in stream_path.read_text().splitlines()]
    init = next(e for e in events if e.get("type") == "system")
    assert init["api_key_present"] is False


def test_claude_code_requires_local_sandbox(tmp_path: Path, fake_claude: Path) -> None:
    with pytest.raises(SandboxError, match="--sandbox local"):
        run_agent(
            task_id="hello-world",
            model="claude-code:claude-opus-4-8",
            output_dir=tmp_path,
            tasks_root=Path("tasks/v1"),
            judges=False,
            sandbox="docker",
        )


def test_usage_limit_raises_provider_error(
    tmp_path: Path, fake_claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "limit")
    with pytest.raises(ProviderError, match="subscription limit"):
        run_claude_code_task(
            workspace=tmp_path,
            prompt="p",
            model="claude-opus-4-8",
            priced_spec="claude-code:claude-opus-4-8",
            max_turns=5,
            collector=_Collector(),
            env_overrides={"FAKE_CLAUDE_MODE": "limit"},
        )


def test_max_turns_is_a_scored_outcome_not_an_error(
    tmp_path: Path, fake_claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "max_turns")
    out = run_claude_code_task(
        workspace=tmp_path,
        prompt="p",
        model="claude-opus-4-8",
        priced_spec="claude-code:claude-opus-4-8",
        max_turns=5,
        collector=_Collector(),
        env_overrides={"FAKE_CLAUDE_MODE": "max_turns"},
    )
    assert out.finished is False
    assert out.subtype == "error_max_turns"
    assert out.prompt_tokens == 168
    assert out.completion_tokens == 30


def test_cost_cap_kills_run_and_keeps_partial_usage(tmp_path: Path, fake_claude: Path) -> None:
    collector = _Collector()
    out = run_claude_code_task(
        workspace=tmp_path,
        prompt="p",
        model="claude-opus-4-8",
        priced_spec="claude-code:claude-opus-4-8",
        max_turns=5,
        collector=collector,
        max_run_cost=0.0005,  # below the first assistant message's cost
    )
    assert out.cost_capped is True
    assert out.finished is False
    # Partial usage from the streamed assistant message (100 + 5 + 12.5 -> 118).
    assert out.prompt_tokens == 118
    assert out.completion_tokens == 20
    assert any(etype == "cost_cap_exceeded" for etype, _ in collector.events)


def test_claude_code_judge_provider_single_shot(fake_claude: Path) -> None:
    provider = get_provider("claude-code:claude-opus-4-8")
    assert provider.name == "claude-code"
    resp = provider.complete(
        [
            {"role": "system", "content": "You are a strict judge."},
            {"role": "user", "content": "Score this patch."},
        ],
        [],
    )
    assert resp.content is not None
    assert json.loads(resp.content) == {"score": 80, "rationale": "fake judge"}
    assert resp.usage.prompt_tokens == 168
    assert resp.usage.completion_tokens == 30


def test_run_agent_via_cursor_subscription(tmp_path: Path, fake_cursor: Path) -> None:
    res = run_agent(
        task_id="hello-world",
        model="cursor:grok-4.6",
        output_dir=tmp_path,
        tasks_root=Path("tasks/v1"),
        judges=False,
        sandbox="local",
        effort="high",
    )
    summary = res["summary"]
    assert summary["scores"]["functional"] == 1.0
    assert summary["finished"] is True
    # Cursor's stream reports no usage: token counts are honestly zero and the
    # API-equivalent value is unavailable rather than a fabricated $0.
    assert summary["tokens"]["total"] == 0
    assert summary["cost_usd"] is None
    assert summary["economics"]["billing_mode"] == "subscription-included"
    assert summary["economics"]["measurement_quality"]["api_equivalent_cost_usd"] == "unavailable"
    cli = summary["cli_agent"]
    assert cli["harness"] == "cursor"
    assert cli["auth_method"] == "subscription"
    assert cli["plan_name"] == "Pro"
    assert cli["session_id"] == "cur-1"
    assert cli["requested_model"] == "grok-4.6"
    # The loop resolved effort=high and the bracket syntax carried it.
    assert cli["reported_model"] == "grok-4.6[effort=high]"
    stream_path = tmp_path / res["run_id"] / "cli-agent-stream.jsonl"
    events = [json.loads(line) for line in stream_path.read_text().splitlines()]
    assert events[0]["leaked_key"] == ""  # provider keys never reach the CLI


def test_cursor_requires_local_sandbox(tmp_path: Path, fake_cursor: Path) -> None:
    with pytest.raises(SandboxError, match="host execution"):
        run_agent(
            task_id="hello-world",
            model="cursor:grok-4.6",
            output_dir=tmp_path,
            tasks_root=Path("tasks/v1"),
            judges=False,
            sandbox="docker",
        )


def test_cursor_logged_out_fails_closed(tmp_path: Path, fake_cursor: Path) -> None:
    # The preflight subprocess gets the minimal allowlisted env, so the mode
    # must be baked into the fake script rather than passed via os.environ.
    fake_cursor.write_text(
        FAKE_CURSOR.replace('os.environ.get("FAKE_CURSOR_MODE", "success")', '"logged_out"'),
        encoding="utf-8",
    )
    with pytest.raises(ProviderError, match=r"signed out|subscription"):
        run_cursor_task(
            workspace=tmp_path,
            prompt="fix",
            model="grok-4.6",
            priced_spec="cursor:grok-4.6",
            max_turns=10,
            collector=_Collector(),
        )


def test_cursor_api_key_auth_fails_closed(
    tmp_path: Path, fake_cursor: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "key-1")
    with pytest.raises(ProviderError, match="subscription"):
        run_cursor_task(
            workspace=tmp_path,
            prompt="fix",
            model="grok-4.6",
            priced_spec="cursor:grok-4.6",
            max_turns=10,
            collector=_Collector(),
        )


def test_cursor_usage_limit_raises_quota_error(
    tmp_path: Path, fake_cursor: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CURSOR_MODE", "limit")
    with pytest.raises(SubscriptionQuotaError, match="topping up credits"):
        run_cursor_task(
            workspace=tmp_path,
            prompt="fix",
            model="grok-4.6",
            priced_spec="cursor:grok-4.6",
            max_turns=10,
            collector=_Collector(),
            env_overrides={"FAKE_CURSOR_MODE": "limit"},
        )


def test_cursor_rejects_unenforceable_live_cost_cap(tmp_path: Path, fake_cursor: Path) -> None:
    with pytest.raises(ProviderError, match="max-run-cost"):
        run_cursor_task(
            workspace=tmp_path,
            prompt="fix",
            model="grok-4.6",
            priced_spec="cursor:grok-4.6",
            max_turns=10,
            collector=_Collector(),
            max_run_cost=1.0,
        )


def test_run_agent_via_codex_subscription(tmp_path: Path, fake_codex: Path) -> None:
    res = run_agent(
        task_id="hello-world",
        model="codex:gpt-5.6-sol",
        output_dir=tmp_path,
        tasks_root=Path("tasks/v1"),
        judges=False,
        sandbox="local",
        effort="high",
    )
    summary = res["summary"]
    assert summary["scores"]["functional"] == 1.0
    assert summary["finished"] is True
    assert summary["tokens"] == {
        "prompt": 120,
        "completion": 30,
        "total": 150,
        "cached_input": 80,
        "reasoning_output": 10,
    }
    cli = summary["cli_agent"]
    assert cli["harness"] == "codex"
    assert cli["auth_method"] == "subscription"
    assert cli["session_id"] == "thread-1"
    assert cli["requested_model"] == "gpt-5.6-sol"
    assert cli["reported_model"] is None
    assert cli["execution_boundary"] == "host-workspace; sandbox=workspace-write"
    assert summary["economics"]["billing_mode"] == "subscription-included"
    stream_path = tmp_path / res["run_id"] / "cli-agent-stream.jsonl"
    events = [json.loads(line) for line in stream_path.read_text().splitlines()]
    assert events[0]["api_key_present"] is False


def test_codex_rejects_unenforceable_live_cost_cap(tmp_path: Path, fake_codex: Path) -> None:
    with pytest.raises(ProviderError, match="cannot be enforced live"):
        run_codex_task(
            workspace=tmp_path,
            prompt="p",
            model="gpt-5.6-sol",
            priced_spec="codex:gpt-5.6-sol",
            max_turns=5,
            collector=_Collector(),
            max_run_cost=1.0,
        )


def test_codex_resolves_relative_workspace_before_passing_cd(
    tmp_path: Path,
    fake_codex: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("workspace").mkdir()
    collector = _Collector()
    run_codex_task(
        workspace=Path("workspace"),
        prompt="p",
        model="gpt-5.6-sol",
        priced_spec="codex:gpt-5.6-sol",
        max_turns=5,
        collector=collector,
    )
    start = next(data for event, data in collector.events if event == "cli_agent_start")
    cd_value = start["argv"][start["argv"].index("--cd") + 1]
    assert Path(cd_value).is_absolute()
