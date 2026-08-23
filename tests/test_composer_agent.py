"""Tests for the Composer agent runner (``composer:`` specs)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from harness.agent.cli_agents import is_cli_agent_spec, run_composer_task
from harness.agent.loop import run_agent
from harness.agent.providers import ProviderError
from harness.pricing import cost_usd, is_priced


class _Collector:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def record(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))


def _fake_usage(input_tokens: int = 100, output_tokens: int = 50) -> MagicMock:
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_read_tokens = 0
    usage.cache_write_tokens = 0
    return usage


def test_is_cli_agent_spec() -> None:
    assert is_cli_agent_spec("composer:composer-2.5")
    assert not is_cli_agent_spec("openai:gpt-4o")


def test_composer_is_priced() -> None:
    assert is_priced("composer:composer-2.5")
    assert cost_usd("composer:composer-2.5", 1_000_000, 1_000_000) == 3.0


def test_run_composer_task_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")

    class _Result:
        status = "finished"
        result = "done"
        usage = _fake_usage(200, 100)

    class _Run:
        usage = _fake_usage(200, 100)

        def messages(self):
            yield MagicMock(type="usage", usage=_fake_usage(200, 100))

        def wait(self):
            return _Result()

        def cancel(self) -> None:
            return None

    class _Agent:
        agent_id = "agent-test"

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def send(self, prompt: str) -> _Run:
            return _Run()

    with patch("cursor_sdk.Agent.create", return_value=_Agent()):
        collector = _Collector()
        outcome = run_composer_task(
            workspace=tmp_path,
            prompt="fix it",
            model="composer-2.5",
            priced_spec="composer:composer-2.5",
            collector=collector,
        )
    assert outcome.finished
    assert outcome.harness == "composer"
    assert outcome.billing == "api"
    assert outcome.prompt_tokens == 200
    assert outcome.completion_tokens == 100


def test_run_composer_task_missing_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="CURSOR_API_KEY"):
        run_composer_task(
            workspace=tmp_path,
            prompt="fix it",
            model="composer-2.5",
            priced_spec="composer:composer-2.5",
            collector=_Collector(),
        )


def test_run_agent_via_composer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")
    tasks_root = Path("tasks/v1")

    class _Result:
        status = "finished"
        result = "done"
        usage = _fake_usage(50, 25)

    class _Run:
        usage = _fake_usage(50, 25)

        def messages(self):
            yield MagicMock(type="usage", usage=_fake_usage(50, 25))

        def wait(self):
            return _Result()

        def cancel(self) -> None:
            return None

    captured: dict[str, Path] = {}

    class _Agent:
        agent_id = "agent-test"

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def send(self, prompt: str) -> _Run:
            ws = captured.get("workspace")
            if ws is not None:
                (ws / "hello.py").write_text('print("hello from vulcanbench")\n', encoding="utf-8")
            return _Run()

    def fake_create(*, local: Any, **kwargs: Any) -> _Agent:
        captured["workspace"] = Path(local.cwd)
        return _Agent()

    with patch("cursor_sdk.Agent.create", side_effect=fake_create):
        result = run_agent(
            task_id="hello-world",
            model="composer:composer-2.5",
            output_dir=tmp_path / "runs",
            tasks_root=tasks_root,
            judges=False,
            sandbox="local",
        )
    summary = result["summary"]
    assert summary["scores"]["functional"] == 1.0
    assert summary["cli_agent"]["harness"] == "composer"
    assert summary["cli_agent"]["billing"] == "api"
