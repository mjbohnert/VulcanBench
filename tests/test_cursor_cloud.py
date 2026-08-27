"""Tests for Cursor cloud-agent Composer 2.5 sessions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from harness.cli import app
from harness.cursor_cloud.session import (
    finalize_session,
    normalize_cloud_model,
    prepare_session,
)
from harness.cursor_cloud.shards import assign_shards, shard_tasks, worker_prompt
from harness.cursor_cloud.tokens import tokens_from_transcript
from harness.suite import load_suite

runner = CliRunner()


def test_round_robin_shards_cover_every_task() -> None:
    task_ids = [f"t{i}" for i in range(23)]
    buckets = assign_shards(task_ids, 8)
    assert len(buckets) == 8
    assert buckets[-1] == ["t7", "t15"]
    assert {tid for bucket in buckets for tid in bucket} == set(task_ids)
    assert shard_tasks(task_ids, 8, 1) == buckets[0]


def test_v4_eight_shards_cover_suite() -> None:
    suite = load_suite("v4")
    buckets = assign_shards(list(suite.task_ids), 8)
    assert len(suite.task_ids) == 23
    assert sorted(tid for bucket in buckets for tid in bucket) == sorted(suite.task_ids)
    assert len(buckets[-1]) == 2


def test_normalize_bare_composer_id() -> None:
    assert normalize_cloud_model("composer-2.5") == "cursor-cloud:composer-2.5"
    assert normalize_cloud_model("cursor:composer-2.5") == "cursor:composer-2.5"


def test_normalize_rejects_other_providers() -> None:
    with pytest.raises(ValueError, match=r"composer-2\.5"):
        normalize_cloud_model("openai:gpt-4o")


def test_worker_prompt_lists_only_that_shard() -> None:
    prompt = worker_prompt(shard_index=1, n_shards=2, suite="v1", task_ids=["hello-world"])
    assert "shard 1/2" in prompt
    assert "`hello-world`" in prompt
    assert "never `cd ..`" in prompt
    assert "gold_patch.diff" in prompt
    assert "WebSearch" in prompt


def test_estimate_tokens_from_transcript_chars() -> None:
    transcript = {
        "messages": [
            {"role": "user", "text": "a" * 400},
            {"role": "assistant", "thinking": "b" * 200, "text": "c" * 100},
            {"role": "tool", "text": "d" * 80},
        ]
    }
    tokens = tokens_from_transcript(transcript)
    assert tokens["input_tokens"] == 120  # (400+80)/4
    assert tokens["reasoning_tokens"] == 50
    assert tokens["output_tokens"] == 25
    assert tokens["estimation"].startswith("chars/4")


def test_official_usage_wins_over_char_estimate() -> None:
    transcript = {
        "usage": {
            "inputTokens": 1000,
            "outputTokens": 200,
            "cacheReadTokens": 50,
            "reasoningTokens": 10,
        },
        "messages": [{"role": "user", "text": "hello"}],
    }
    tokens = tokens_from_transcript(transcript)
    assert tokens["estimation"] == "provider-reported"
    assert tokens["input_tokens"] == 1050
    assert tokens["output_tokens"] == 200
    assert tokens["reasoning_tokens"] == 10
    assert tokens["cached_input_tokens"] == 50


def test_prepare_and_finalize_hello_world(tmp_path: Path) -> None:
    manifest = prepare_session(
        task_id="hello-world",
        suite="v1",
        model="cursor-cloud:composer-2.5",
        output_dir=tmp_path / "runs",
        tasks_root=Path("tasks/v1"),
    )
    workspace = Path(manifest["workspace"])
    assert workspace.is_dir()
    assert "/tasks/" not in str(workspace)
    (workspace / "hello.py").write_text('print("hello from vulcanbench")\n', encoding="utf-8")

    transcript = {
        "usage": {"inputTokens": 800, "outputTokens": 100, "cacheReadTokens": 0},
        "messages": [{"role": "assistant", "text": "done"}],
    }
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")

    summary = finalize_session(
        run_dir=Path(manifest["run_dir"]),
        transcript_path=transcript_path,
        agent_bc_id="bc-test",
    )
    assert summary["scores"]["functional"] == 1.0
    assert summary["tokens"]["input"] == 800
    assert summary["tokens"]["output"] == 100
    assert summary["cost_usd"] is not None
    assert summary["economics"]["billing_mode"] == "subscription-included"
    assert summary["economics"]["measurement_quality"]["api_equivalent_cost_usd"] == (
        "estimated-from-reported-tokens"
    )
    assert summary["cli_agent"]["harness"] == "cursor-cloud"
    assert (Path(manifest["run_dir"]) / "summary.json").is_file()


def test_shards_cli_v4() -> None:
    result = runner.invoke(app, ["cursor-cloud", "shards", "--suite", "v4"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["n_tasks"] == 23
    assert data["n_shards"] == 8
    assert data["shards"][-1]["n_tasks"] == 2


def test_print_prompt_requires_shard_or_all() -> None:
    result = runner.invoke(app, ["cursor-cloud", "print-prompt", "--suite", "v4"])
    assert result.exit_code != 0


def test_print_prompt_all_v4() -> None:
    result = runner.invoke(app, ["cursor-cloud", "print-prompt", "--all", "--suite", "v4"])
    assert result.exit_code == 0
    assert "SHARD 1/8" in result.output
    assert "SHARD 8/8" in result.output
    assert "oss-aiohttp-upgrade-deferred" in result.output
