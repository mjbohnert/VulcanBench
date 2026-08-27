"""Prepare and finalize Cursor cloud-agent benchmark sessions."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness.agent.cli_agents import build_cli_prompt
from harness.cursor_cloud.shards import (
    DEFAULT_MODEL,
    DEFAULT_SHARDS,
    DEFAULT_SUITE,
    suite_shard,
)
from harness.cursor_cloud.tokens import load_transcript, tokens_from_transcript
from harness.economics import EconomicsReceipt, subscription_receipt
from harness.evaluator.scorer import run_verifier
from harness.pricing import cost_usd, has_cached_input_price
from harness.suite import load_suite
from harness.task_metadata import resolve_verifier_timeout_s
from harness.tasks import Task, load_task, prepare_workspace, task_hash
from harness.verifier import (
    DEFAULT_TIMEOUT,
    RunnerOutcome,
    VerifierInfrastructureError,
    run_declarative_verifier,
)

MODEL_PREFIXES = ("cursor-cloud:", "cursor-agent:", "cursor:")
_WORKSPACE_GITIGNORE = (
    ".coverage\n__pycache__/\n.pytest_cache/\n.ruff_cache/\n*.pyc\n.cursor/\n"
    "target/\nnode_modules/\ndist/\nbuild/\n.gocache/\n*.egg-info/\n"
)


def _git_env(extra: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(extra)
    return env


def _git_init(workspace: Path) -> None:
    (workspace / ".gitignore").write_text(_WORKSPACE_GITIGNORE, encoding="utf-8")
    ident = {
        "GIT_AUTHOR_NAME": "vulcanbench",
        "GIT_AUTHOR_EMAIL": "bot@vulcanbench",
        "GIT_COMMITTER_NAME": "vulcanbench",
        "GIT_COMMITTER_EMAIL": "bot@vulcanbench",
    }
    for args in (
        ["init", "-q"],
        ["add", "-A"],
        ["commit", "-q", "--allow-empty", "-m", "base"],
    ):
        subprocess.run(
            ["git", *args],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
            env=_git_env(ident),
        )


def _git_diff(workspace: Path) -> str:
    subprocess.run(["git", "add", "-A"], cwd=workspace, capture_output=True, text=True, check=False)
    proc = subprocess.run(
        ["git", "diff", "--cached"],
        cwd=workspace,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.stdout


def _isolated_host_runner(cmd: str, workspace: Path, timeout: int) -> RunnerOutcome:
    """Host tests that ignore the parent repo's pytest addopts and caches."""
    env = os.environ.copy()
    env["PYTEST_ADDOPTS"] = "-o addopts="
    env.setdefault("GOCACHE", str(workspace / ".gocache"))
    env.setdefault("CARGO_TARGET_DIR", str(workspace / "target"))
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return RunnerOutcome(124, str(exc.stdout or ""), str(exc.stderr or ""))
    return RunnerOutcome(proc.returncode, proc.stdout, proc.stderr)


def normalize_cloud_model(model: str) -> str:
    """Accept ``cursor-cloud:composer-2.5`` or a bare Composer id."""
    if model.startswith(MODEL_PREFIXES):
        return model
    if ":" not in model:
        return f"cursor-cloud:{model}"
    raise ValueError(
        f"model must start with one of {MODEL_PREFIXES} or be a bare id "
        f"(e.g. composer-2.5), got {model!r}."
    )


def prepare_session(
    *,
    task_id: str,
    model: str = DEFAULT_MODEL,
    suite: str = DEFAULT_SUITE,
    output_dir: Path = Path("runs"),
    tasks_root: Path | None = None,
    repeat_index: int = 1,
    shard_index: int | None = None,
) -> dict[str, Any]:
    """Materialize a task workspace outside the checkout for a cloud agent.

    Workspaces are created under a temp dir so the agent cannot walk up into
    ``tasks/`` and read gold patches or hidden tests.
    """
    model = normalize_cloud_model(model)
    if tasks_root is None:
        tasks_root = load_suite(suite).tasks_root

    task = load_task(task_id, tasks_root)
    run_id = f"{task_id}-{uuid.uuid4().hex[:8]}"
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    tmp_root = Path(tempfile.mkdtemp(prefix=f"vulcanbench-cursor-cloud-{task_id}-"))
    workspace = tmp_root / "workspace"
    prepare_workspace(task, workspace)
    _git_init(workspace)

    prompt = build_cli_prompt(task.issue)
    (run_dir / "agent_prompt.md").write_text(prompt, encoding="utf-8")

    started_at = datetime.now(UTC)
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "task_id": task_id,
        "model": model,
        "suite": suite,
        "repeat_index": repeat_index,
        "shard_index": shard_index,
        "run_dir": str(run_dir.resolve()),
        "workspace": str(workspace.resolve()),
        "tmp_root": str(tmp_root.resolve()),
        "tasks_root": str(Path(tasks_root).resolve()),
        "started_at": started_at.isoformat(),
        "agent_prompt": prompt,
        "harness": "cursor-cloud",
        "billing": "subscription",
        "cost_basis": "list-price-from-usage",
    }
    (run_dir / "session.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def prepare_shard(
    *,
    shard_index: int,
    n_shards: int = DEFAULT_SHARDS,
    suite: str = DEFAULT_SUITE,
    model: str = DEFAULT_MODEL,
    output_dir: Path = Path("runs/cursor-cloud"),
    repeats: int = 1,
) -> dict[str, Any]:
    """Prepare every task in one shard. Returns the shard manifest."""
    suite_obj = load_suite(suite)
    task_ids = suite_shard(suite, n_shards, shard_index)
    shard_dir = output_dir / f"shard-{shard_index:02d}"
    shard_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for repeat_index in range(1, repeats + 1):
        for task_id in task_ids:
            manifest = prepare_session(
                task_id=task_id,
                model=model,
                suite=suite,
                output_dir=shard_dir,
                tasks_root=suite_obj.tasks_root,
                repeat_index=repeat_index,
                shard_index=shard_index,
            )
            runs.append(
                {
                    "run_id": manifest["run_id"],
                    "task_id": manifest["task_id"],
                    "repeat_index": repeat_index,
                    "run_dir": manifest["run_dir"],
                    "workspace": manifest["workspace"],
                }
            )
    payload = {
        "suite": suite,
        "model": model,
        "shard_index": shard_index,
        "n_shards": n_shards,
        "task_ids": task_ids,
        "repeats": repeats,
        "runs": runs,
    }
    (shard_dir / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _reclaim_workspace(session: dict[str, Any], run_dir: Path) -> Path:
    workspace = Path(session["workspace"])
    dest = run_dir / "workspace"
    if workspace.resolve() != dest.resolve() and workspace.exists():
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(workspace), str(dest))
        tmp_root = session.get("tmp_root")
        if tmp_root:
            shutil.rmtree(tmp_root, ignore_errors=True)
        session["workspace"] = str(dest)
        (run_dir / "session.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
        return dest
    return workspace


def _session_tokens(run_dir: Path, transcript_path: Path | None) -> dict[str, Any]:
    if transcript_path is None:
        return {
            "input_tokens": 0,
            "reasoning_tokens": 0,
            "output_tokens": 0,
            "cached_input_tokens": 0,
            "total_tokens": 0,
            "estimation": "unavailable (no transcript; fill via --transcript)",
        }
    transcript = load_transcript(transcript_path)
    (run_dir / "transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    return tokens_from_transcript(transcript)


def _grade_workspace(task: Task, workspace: Path) -> tuple[dict[str, Any], float]:
    timeout = resolve_verifier_timeout_s(task.metadata, DEFAULT_TIMEOUT)
    t0 = time.monotonic()
    try:
        if task.tests_spec is not None:
            payload = run_declarative_verifier(
                task, workspace, runner=_isolated_host_runner, timeout=timeout
            )
        elif task.verifier is not None:
            payload = run_verifier(task.verifier, workspace, timeout=timeout)
        else:
            payload = {"scores": {"functional": 0.0, "error": "no tests_spec or verifier"}}
    except VerifierInfrastructureError as exc:
        payload = {"scores": {"functional": 0.0, "error": str(exc)}, "infrastructure_error": True}
    return payload, round(time.monotonic() - t0, 3)


def _priced_tokens(
    model: str, tokens: dict[str, Any]
) -> tuple[dict[str, Any], float | None, EconomicsReceipt]:
    prompt_tokens = int(tokens.get("input_tokens") or 0)
    completion_tokens = int(tokens.get("output_tokens") or 0) + int(
        tokens.get("reasoning_tokens") or 0
    )
    cached = int(tokens.get("cached_input_tokens") or 0)
    estimated_cost = None
    if prompt_tokens or completion_tokens:
        estimated_cost = cost_usd(
            model, prompt_tokens, completion_tokens, cached_input_tokens=cached
        )
    estimation = str(tokens.get("estimation") or "")
    if estimated_cost is None:
        api_quality = "unavailable"
    elif estimation == "provider-reported" and cached and has_cached_input_price(model):
        api_quality = "estimated-from-reported-tokens-with-cache-pricing"
    elif estimation == "provider-reported":
        api_quality = "estimated-from-reported-tokens"
    else:
        api_quality = "estimated-chars-per-4"
    token_block = {
        "input": prompt_tokens,
        "reasoning": int(tokens.get("reasoning_tokens") or 0),
        "output": int(tokens.get("output_tokens") or 0),
        "cached_input": cached,
        "total": int(tokens.get("total_tokens") or (prompt_tokens + completion_tokens)),
        "estimation": tokens.get("estimation"),
    }
    economics = subscription_receipt(
        api_equivalent_cost_usd=estimated_cost,
        grading_cash_usd=None,
        grading_api_equivalent_usd=None,
        plan_name="cursor-cloud",
        cli_reported_cost_usd=None,
        api_equivalent_quality=api_quality,
    )
    return token_block, estimated_cost, economics


def finalize_session(
    *,
    run_dir: Path,
    transcript_path: Path | None = None,
    agent_bc_id: str | None = None,
    duration_s: float | None = None,
) -> dict[str, Any]:
    """Grade a prepared session and write ``summary.json``."""
    if agent_bc_id is None:
        agent_bc_id = os.environ.get("CURSOR_CONVERSATION_ID") or None
    session_path = run_dir / "session.json"
    if not session_path.is_file():
        raise FileNotFoundError(f"missing session.json in {run_dir}")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    task_id = str(session["task_id"])
    model = str(session["model"])
    workspace = _reclaim_workspace(session, run_dir)
    tokens = _session_tokens(run_dir, transcript_path)
    (run_dir / "final.patch").write_text(_git_diff(workspace), encoding="utf-8")

    task = load_task(task_id, Path(session["tasks_root"]))
    started = datetime.fromisoformat(str(session["started_at"]))
    if duration_s is None:
        duration_s = (datetime.now(UTC) - started).total_seconds()
    verifier_payload, verify_s = _grade_workspace(task, workspace)
    functional = float((verifier_payload.get("scores") or {}).get("functional", 0.0))
    token_block, estimated_cost, economics = _priced_tokens(model, tokens)

    summary: dict[str, Any] = {
        "run_id": session["run_id"],
        "task_id": task_id,
        "model": model,
        "suite": session.get("suite"),
        "repeat_index": session.get("repeat_index"),
        "shard_index": session.get("shard_index"),
        "scores": {
            "functional": functional,
            "quality": None,
            "security": None,
            "human_like": None,
            "total": functional,
        },
        "duration_s": round(duration_s, 3),
        "verify_duration_s": verify_s,
        "tokens": token_block,
        "cost_usd": estimated_cost,
        "cost_detail": {
            "agent": estimated_cost,
            "total": estimated_cost,
            "model_priced": estimated_cost is not None,
            "note": tokens.get("estimation"),
        },
        "economics": economics.as_summary(),
        "task_hash": task_hash(task),
        "finished_at": datetime.now(UTC).isoformat(),
        "verifier": verifier_payload,
        "cli_agent": {
            "harness": "cursor-cloud",
            "billing": "subscription",
            "cost_basis": "list-price-from-usage",
            "agent_bc_id": agent_bc_id,
            "transcript_path": str(transcript_path) if transcript_path else None,
        },
        "artifacts": {
            "workspace": str(workspace),
            "final_patch": str(run_dir / "final.patch"),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def finalize_shard(
    *,
    shard_index: int,
    n_shards: int = DEFAULT_SHARDS,
    suite: str = DEFAULT_SUITE,
    output_dir: Path = Path("runs/cursor-cloud"),
    transcript_dir: Path | None = None,
) -> dict[str, Any]:
    """Finalize every prepared run in a shard directory."""
    shard_dir = output_dir / f"shard-{shard_index:02d}"
    manifest_path = shard_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing {manifest_path}; run prepare-shard first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summaries: list[dict[str, Any]] = []
    for entry in manifest.get("runs") or []:
        run_dir = Path(entry["run_dir"])
        transcript = None
        if transcript_dir is not None:
            candidate = transcript_dir / f"{entry['run_id']}.json"
            if candidate.is_file():
                transcript = candidate
        summaries.append(finalize_session(run_dir=run_dir, transcript_path=transcript))
    report = {
        "suite": suite,
        "shard_index": shard_index,
        "n_shards": n_shards,
        "n_runs": len(summaries),
        "n_pass": sum(1 for s in summaries if (s.get("scores") or {}).get("functional") == 1.0),
        "summaries": summaries,
    }
    (shard_dir / "shard-summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def apply_transcript(*, run_dir: Path, transcript_path: Path) -> dict[str, Any]:
    """Re-price an already-finalized run from a transcript without re-grading."""
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"missing summary.json in {run_dir}; finalize first")
    raw = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"summary.json must be an object, got {type(raw).__name__}")
    summary: dict[str, Any] = raw
    transcript = load_transcript(transcript_path)
    (run_dir / "transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    tokens = tokens_from_transcript(transcript)
    token_block, estimated_cost, economics = _priced_tokens(str(summary["model"]), tokens)
    summary["tokens"] = token_block
    summary["cost_usd"] = estimated_cost
    summary["cost_detail"] = {
        "agent": estimated_cost,
        "total": estimated_cost,
        "model_priced": estimated_cost is not None,
        "note": tokens.get("estimation"),
    }
    summary["economics"] = economics.as_summary()
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
