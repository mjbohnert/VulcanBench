"""Prepare and finalize Cursor cloud-agent benchmark sessions."""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness.agent.cli_agents import build_cli_prompt
from harness.cursor_agent.tokens import estimate_tokens_from_transcript, load_transcript
from harness.pricing import cost_usd
from harness.suite import load_suite
from harness.tasks import load_task, prepare_workspace, task_hash
from harness.verifier import host_runner, run_declarative_verifier

DEFAULT_TASKS_BASE = Path("tasks")
MODEL_PREFIX = "cursor-agent:"


def _git_init(workspace: Path) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "vulcanbench",
        "GIT_AUTHOR_EMAIL": "bot@vulcanbench",
        "GIT_COMMITTER_NAME": "vulcanbench",
        "GIT_COMMITTER_EMAIL": "bot@vulcanbench",
    }
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=False, env=env)
    subprocess.run(["git", "add", "-A"], cwd=workspace, capture_output=True, check=False, env=env)


def _git_diff(workspace: Path) -> str:
    proc = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stdout.strip():
        return proc.stdout
    proc2 = subprocess.run(
        ["git", "diff"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc2.stdout


def prepare_session(
    *,
    task_id: str,
    model: str = "cursor-agent:composer-2.5",
    suite: str = "v4",
    output_dir: Path = Path("runs"),
    tasks_root: Path | None = None,
    repeat_index: int = 1,
) -> dict[str, Any]:
    """Materialize a task workspace for a Cursor cloud agent to solve.

    Returns a manifest with ``run_dir``, ``workspace``, and the agent prompt.
    """
    if not model.startswith(MODEL_PREFIX):
        raise ValueError(f"model must start with {MODEL_PREFIX!r}, got {model!r}")

    if tasks_root is None:
        suite_obj = load_suite(suite, DEFAULT_TASKS_BASE)
        tasks_root = suite_obj.tasks_root

    task = load_task(task_id, tasks_root)
    run_id = f"{task_id}-{uuid.uuid4().hex[:8]}"
    run_dir = output_dir / run_id
    workspace = run_dir / "workspace"
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
        "run_dir": str(run_dir),
        "workspace": str(workspace),
        "tasks_root": str(tasks_root),
        "started_at": started_at.isoformat(),
        "agent_prompt": prompt,
        "harness": "cursor-agent",
        "billing": "subscription",
        "cost_basis": "estimated-from-transcript",
    }
    (run_dir / "session.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def finalize_session(
    *,
    run_dir: Path,
    transcript_path: Path | None = None,
    agent_bc_id: str | None = None,
    duration_s: float | None = None,
) -> dict[str, Any]:
    """Grade a prepared session and write ``summary.json``.

    Token counts are estimated from the cloud-agent transcript (input / reasoning /
    output). ``cost_usd`` uses Composer list rates on input+output only; reasoning
    is reported separately for your own pricing model.
    """
    session_path = run_dir / "session.json"
    if not session_path.is_file():
        raise FileNotFoundError(f"missing session.json in {run_dir}")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    task_id = str(session["task_id"])
    model = str(session["model"])
    tasks_root = Path(session["tasks_root"])
    workspace = run_dir / "workspace"

    if transcript_path is None:
        raise ValueError("transcript_path is required to estimate token usage")

    transcript = load_transcript(transcript_path)
    tokens = estimate_tokens_from_transcript(transcript)
    (run_dir / "transcript.json").write_text(
        json.dumps(transcript, indent=2), encoding="utf-8"
    )

    patch = _git_diff(workspace)
    (run_dir / "final.patch").write_text(patch, encoding="utf-8")

    task = load_task(task_id, tasks_root)
    started = datetime.fromisoformat(str(session["started_at"]))
    if duration_s is None:
        duration_s = (datetime.now(UTC) - started).total_seconds()

    t0 = time.monotonic()
    verifier_payload = run_declarative_verifier(task, workspace, runner=host_runner)
    verify_s = round(time.monotonic() - t0, 3)

    functional = float((verifier_payload.get("scores") or {}).get("functional", 0.0))
    scores = {
        "functional": functional,
        "quality": None,
        "security": None,
        "human_like": None,
        "total": functional,
    }

    # Price input + output at Composer standard rates; reasoning reported separately.
    prompt_tokens = tokens["input_tokens"]
    completion_tokens = tokens["output_tokens"] + tokens["reasoning_tokens"]
    estimated_cost = cost_usd(model.replace(MODEL_PREFIX, "composer:"), prompt_tokens, completion_tokens)

    summary: dict[str, Any] = {
        "run_id": session["run_id"],
        "task_id": task_id,
        "model": model,
        "suite": session.get("suite"),
        "repeat_index": session.get("repeat_index"),
        "steps": len(transcript.get("messages") or []),
        "scores": scores,
        "duration_s": round(duration_s, 3),
        "verify_duration_s": verify_s,
        "tokens": {
            "input": tokens["input_tokens"],
            "reasoning": tokens["reasoning_tokens"],
            "output": tokens["output_tokens"],
            "total": tokens["total_tokens"],
            "estimation": tokens["estimation"],
            "chars": {
                "input": tokens["input_chars"],
                "reasoning": tokens["reasoning_chars"],
                "output": tokens["output_chars"],
            },
        },
        "cost_usd": estimated_cost,
        "cost_detail": {
            "agent": estimated_cost,
            "total": estimated_cost,
            "model_priced": estimated_cost is not None,
            "note": "estimated from transcript; reasoning billed as output at list rate",
        },
        "task_hash": task_hash(task),
        "finished_at": datetime.now(UTC).isoformat(),
        "verifier": verifier_payload,
        "cli_agent": {
            "harness": "cursor-agent",
            "billing": "subscription",
            "cost_basis": "estimated-from-transcript",
            "agent_bc_id": agent_bc_id,
            "transcript_path": str(transcript_path),
        },
        "artifacts": {
            "workspace": str(workspace),
            "final_patch": str(run_dir / "final.patch"),
            "transcript": str(run_dir / "transcript.json"),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
