"""Tests for Cursor cloud-agent Composer 2.5 sessions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from harness.cli import app
from harness.cursor_cloud.session import (
    apply_transcript,
    finalize_session,
    normalize_cloud_model,
    prepare_session,
)
from harness.cursor_cloud.shards import assign_shards, shard_tasks, worker_prompt
from harness.cursor_cloud.tokens import tokens_from_transcript
from harness.cursor_cloud.toolchains import (
    Requirements,
    ToolSnapshot,
    missing_from_snapshot,
    preflight_errors,
    requirements_for_shard,
    requirements_for_suite,
)
from harness.suite import load_suite
from harness.tasks import load_task

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
    assert "CURSOR_CONVERSATION_ID" in prompt
    assert "price-transcript" in prompt
    assert "bootstrap" in prompt
    assert "doctor" in prompt


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


def test_estimate_tokens_from_cursor_cloud_export() -> None:
    # Real Cursor cloud transcripts use thinking/tool_calls/tool_result, not content.
    transcript = {
        "messages": [
            {"role": "user", "text": "a" * 40},
            {"role": "assistant", "thinking": "b" * 20, "tool_calls": ["cc" * 20]},
            {"role": "tool", "tool_name": "Shell", "tool_result": "d" * 80},
            {"role": "assistant", "text": "e" * 8},
        ]
    }
    tokens = tokens_from_transcript(transcript)
    assert tokens["input_tokens"] == 30  # (40+80)/4
    assert tokens["reasoning_tokens"] == 5  # 20/4
    assert tokens["output_tokens"] == 12  # (40+8)/4
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


def test_prepare_and_finalize_v4_python_gold(tmp_path: Path) -> None:
    """Baseline suite v4 goes through cursor-cloud prepare/grade, not only hello-world."""
    task_id = "oss-more-itertools-interleave-empty"
    manifest = prepare_session(
        task_id=task_id,
        suite="v4",
        model="composer-2.5",
        output_dir=tmp_path / "runs",
        tasks_root=Path("tasks/v4"),
    )
    workspace = Path(manifest["workspace"])
    assert "/tasks/" not in str(workspace)
    assert not (workspace / "gold_patch.diff").exists()
    assert manifest["model"] == "cursor-cloud:composer-2.5"
    task = load_task(task_id, Path("tasks/v4"))
    assert task.gold_patch is not None
    applied = subprocess.run(
        ["git", "apply", str(task.gold_patch.resolve())],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert applied.returncode == 0, applied.stderr
    summary = finalize_session(run_dir=Path(manifest["run_dir"]))
    assert summary["scores"]["functional"] == 1.0
    assert summary["suite"] == "v4"


def test_apply_transcript_reprices_without_regrade(tmp_path: Path) -> None:
    manifest = prepare_session(
        task_id="hello-world",
        suite="v1",
        model="cursor-cloud:composer-2.5",
        output_dir=tmp_path / "runs",
        tasks_root=Path("tasks/v1"),
    )
    workspace = Path(manifest["workspace"])
    (workspace / "hello.py").write_text('print("hello from vulcanbench")\n', encoding="utf-8")
    summary = finalize_session(run_dir=Path(manifest["run_dir"]))
    assert summary["cost_usd"] is None

    transcript_path = tmp_path / "t.json"
    transcript_path.write_text(
        json.dumps({"messages": [{"role": "user", "text": "a" * 400}]}),
        encoding="utf-8",
    )
    updated = apply_transcript(run_dir=Path(manifest["run_dir"]), transcript_path=transcript_path)
    assert updated["scores"]["functional"] == 1.0
    assert updated["tokens"]["input"] == 100
    assert updated["cost_usd"] is not None


def test_price_transcript_cli(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text(
        json.dumps({"messages": [{"role": "user", "text": "a" * 400}]}), encoding="utf-8"
    )
    result = runner.invoke(app, ["cursor-cloud", "price-transcript", str(path)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["tokens"]["input_tokens"] == 100
    assert data["cost_usd"] is not None


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
    assert ".[dev,test]" in result.output
    assert "cursor-cloud bootstrap" in result.output


def test_v4_shard_toolchain_requirements() -> None:
    shard1 = requirements_for_shard("v4", 8, 1)
    assert shard1.need_tsx
    assert not shard1.need_go
    assert not shard1.need_rustc_190
    assert not shard1.need_pennylane
    assert "oss-hono-url-param-prefix" in shard1.task_ids

    shard5 = requirements_for_shard("v4", 8, 5)
    assert shard5.need_rustc_190
    assert shard5.need_go
    assert "oss-time-strftime-truncated-padding" in shard5.task_ids

    shard6 = requirements_for_shard("v4", 8, 6)
    assert shard6.need_pennylane
    assert shard6.need_tsx
    assert shard6.need_go


def test_bootstrap_all_skips_pennylane_jax() -> None:
    req = requirements_for_suite("v4", include_pennylane=False)
    assert not req.need_pennylane
    assert req.need_tsx
    assert req.need_go
    assert req.need_rustc_190
    assert requirements_for_suite("v4").need_pennylane


def test_missing_from_snapshot_names_host_gaps() -> None:
    req = Requirements(need_go=True, need_rustc_190=True, need_tsx=True, need_python=True)
    snap = ToolSnapshot(
        python=False,
        node=True,
        tsx=False,
        npm=True,
        go=(1, 22, 2),
        rustc=(1, 83, 0),
        rustup=True,
        pennylane_deps=False,
    )
    missing = missing_from_snapshot(req, snap)
    joined = " ".join(missing)
    assert "python" in joined
    assert "tsx" in joined
    assert "1.23" in joined
    assert "1.90" in joined


def test_preflight_rust_2024_needs_190() -> None:
    task = load_task("oss-time-strftime-truncated-padding", Path("tasks/v4"))
    snap = ToolSnapshot(
        python=True,
        node=True,
        tsx=True,
        npm=True,
        go=(1, 23, 4),
        rustc=(1, 83, 0),
        rustup=True,
        pennylane_deps=True,
    )
    errors = preflight_errors(task, snap)
    assert any("1.90" in item for item in errors)


def test_doctor_cli_shard1_json() -> None:
    result = runner.invoke(app, ["cursor-cloud", "doctor", "--shard", "1", "--suite", "v4"])
    data = json.loads(result.output)
    assert data["shard_index"] == 1
    assert "oss-hono-url-param-prefix" in data["task_ids"]
    assert "typescript" in data["languages"]


def test_bootstrap_dry_run_shard1() -> None:
    result = runner.invoke(
        app, ["cursor-cloud", "bootstrap", "--shard", "1", "--suite", "v4", "--dry-run"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is True
    assert data["ok"] is True
