"""Tests for the Cursor agent-CLI runner (``cursor:`` specs).

A fake ``agent`` binary on PATH emits canned stream-json events (and writes
the hello-world solution), so the full run_agent pipeline — workspace, diff,
verifier, scoring, Cursor list-price cost — is exercised offline.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from harness.agent.cli_agents import is_cli_agent_spec, run_cursor_task
from harness.agent.loop import run_agent
from harness.agent.providers import ProviderError, get_provider
from harness.pricing import cost_usd, is_priced
from harness.sandbox.docker_executor import SandboxError

# Result usage: 200 uncached + 100 cache-read (0.1x) + 10 cache-write
# folds to round(200 + 10 + 10) = 220 effective prompt tokens; output 40.
FAKE_AGENT = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
mode = os.environ.get("FAKE_CURSOR_MODE", "success")
usage = {"inputTokens": 200, "outputTokens": 40,
         "cacheReadTokens": 100, "cacheWriteTokens": 10}

if "stream-json" in args:
    print(json.dumps({"type": "system", "subtype": "init",
                      "session_id": "cur1", "model": "composer-2.5"}))
    if mode == "success":
        with open("hello.py", "w") as f:
            f.write('print("hello from vulcanbench")\\n')
    print(json.dumps({"type": "assistant", "message": {
        "role": "assistant",
        "content": [{"type": "text", "text": "Writing the file"}]}}))
    print(json.dumps({"type": "tool_call", "subtype": "completed",
                      "call_id": "c1",
                      "tool_call": {"writeToolCall": {
                          "args": {"path": "hello.py"},
                          "result": {"success": {"linesCreated": 1, "fileSize": 32}}}}}))
    if mode == "limit":
        print(json.dumps({"type": "result", "subtype": "error", "is_error": True,
                          "result": "You've hit your usage limit. Try again later.",
                          "session_id": "cur1", "usage": usage}))
        sys.exit(1)
    if mode == "fail":
        print(json.dumps({"type": "result", "subtype": "error", "is_error": True,
                          "result": "model exploded", "session_id": "cur1"}))
        sys.exit(1)
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                      "result": "Done", "session_id": "cur1",
                      "total_cost_usd": 0.00021, "usage": usage}))
else:
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                      "result": json.dumps({"score": 80, "rationale": "fake judge"}),
                      "session_id": "cur2", "usage": usage}))
"""


class _Collector:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def record(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))


@pytest.fixture()
def fake_agent(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path_factory.mktemp("fakebin")
    script = bin_dir / "agent"
    script.write_text(FAKE_AGENT, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("FAKE_CURSOR_MODE", raising=False)
    monkeypatch.delenv("CURSOR_AGENT_BIN", raising=False)
    return script


def test_spec_detection() -> None:
    assert is_cli_agent_spec("cursor:composer-2.5")
    assert is_cli_agent_spec("cursor:composer-2.5-fast")
    assert not is_cli_agent_spec("openai:composer-2.5")


def test_composer_list_prices() -> None:
    assert is_priced("cursor:composer-2.5")
    assert is_priced("cursor:composer-2.5-fast")
    assert cost_usd("cursor:composer-2.5", 1_000_000, 1_000_000) == 3.0
    assert cost_usd("cursor:composer-2.5-fast", 1_000_000, 1_000_000) == 18.0
    # Folded usage from the fake CLI: 220 prompt + 40 completion at standard rates.
    assert cost_usd("cursor:composer-2.5", 220, 40) == pytest.approx(
        (220 * 0.50 + 40 * 2.50) / 1_000_000
    )


def test_run_cursor_task_success(tmp_path: Path, fake_agent: Path) -> None:
    collector = _Collector()
    ws = tmp_path / "ws"
    ws.mkdir()
    outcome = run_cursor_task(
        workspace=ws,
        prompt="do the thing",
        model="composer-2.5",
        priced_spec="cursor:composer-2.5",
        collector=collector,
        stream_log_path=tmp_path / "stream.jsonl",
    )
    assert outcome.finished
    assert outcome.harness == "cursor"
    assert outcome.billing == "cursor-usage"
    assert outcome.cost_basis == "cursor-list-price"
    assert outcome.session_id == "cur1"
    assert (outcome.prompt_tokens, outcome.completion_tokens) == (220, 40)
    assert outcome.cli_reported_cost_usd == pytest.approx(0.00021)
    assert (ws / "hello.py").exists()
    kinds = [k for k, _ in collector.events]
    assert "cli_agent_start" in kinds
    assert "llm_response" in kinds
    assert "tool_observation" in kinds
    assert (tmp_path / "stream.jsonl").read_text().count("\n") >= 4


def test_usage_limit_raises_provider_error(
    tmp_path: Path, fake_agent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CURSOR_MODE", "limit")
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(ProviderError, match="usage limit"):
        run_cursor_task(
            workspace=ws,
            prompt="p",
            model="composer-2.5",
            priced_spec="cursor:composer-2.5",
            collector=_Collector(),
        )


def test_run_failure_raises_provider_error(
    tmp_path: Path, fake_agent: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CURSOR_MODE", "fail")
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(ProviderError):
        run_cursor_task(
            workspace=ws,
            prompt="p",
            model="composer-2.5",
            priced_spec="cursor:composer-2.5",
            collector=_Collector(),
        )


def test_run_agent_via_cursor(tmp_path: Path, fake_agent: Path) -> None:
    result = run_agent(
        task_id="hello-world",
        model="cursor:composer-2.5",
        output_dir=tmp_path / "runs",
        sandbox="local",
        judges=False,
    )
    summary = result["summary"]
    assert summary["scores"]["functional"] == 1.0
    assert summary["tokens"]["prompt"] == 220
    assert summary["tokens"]["completion"] == 40
    assert summary["cost_usd"] == pytest.approx((220 * 0.50 + 40 * 2.50) / 1_000_000)
    cli = summary["cli_agent"]
    assert cli["harness"] == "cursor"
    assert cli["billing"] == "cursor-usage"
    assert cli["cost_basis"] == "cursor-list-price"
    assert cli["cli_reported_cost_usd"] == pytest.approx(0.00021)


def test_cursor_requires_local_sandbox(tmp_path: Path, fake_agent: Path) -> None:
    with pytest.raises(SandboxError, match="--sandbox local"):
        run_agent(
            task_id="hello-world",
            model="cursor:composer-2.5",
            output_dir=tmp_path / "runs",
            sandbox="docker",
            judges=False,
        )


def test_cursor_judge_provider_single_shot(fake_agent: Path) -> None:
    provider = get_provider("cursor:composer-2.5")
    assert provider.name == "cursor"
    response = provider.complete(
        [{"role": "user", "content": "rate this"}],
        tools=[],
    )
    assert response.content is not None
    assert json.loads(response.content) == {"score": 80, "rationale": "fake judge"}
    assert response.usage.prompt_tokens == 220
    assert response.usage.completion_tokens == 40
