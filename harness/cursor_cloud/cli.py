"""CLI for Cursor cloud-agent Composer 2.5 sessions."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from harness.cursor_cloud.session import (
    apply_transcript,
    finalize_session,
    finalize_shard,
    prepare_session,
    prepare_shard,
)
from harness.cursor_cloud.shards import (
    DEFAULT_MODEL,
    DEFAULT_SHARDS,
    DEFAULT_SUITE,
    assign_shards,
    worker_prompt,
)
from harness.cursor_cloud.tokens import load_transcript, priced_transcript
from harness.suite import load_suite

console = Console()
cursor_cloud_app = typer.Typer(
    name="cursor-cloud",
    help="Benchmark Composer 2.5 in Cursor cloud agents (no API key)",
    no_args_is_help=True,
)


@cursor_cloud_app.command("shards")
def shards_cmd(
    suite: str = typer.Option(DEFAULT_SUITE, "--suite"),
    n_shards: int = typer.Option(DEFAULT_SHARDS, "--shards", min=1),
) -> None:
    """Print the 8-way (or N-way) task assignment for a suite."""
    task_ids = list(load_suite(suite).task_ids)
    buckets = assign_shards(task_ids, n_shards)
    payload = {
        "suite": suite,
        "n_shards": n_shards,
        "n_tasks": len(task_ids),
        "shards": [
            {"shard": i + 1, "n_tasks": len(bucket), "tasks": bucket}
            for i, bucket in enumerate(buckets)
        ],
    }
    console.print_json(json.dumps(payload, indent=2))


@cursor_cloud_app.command("print-prompt")
def print_prompt_cmd(
    shard: int | None = typer.Option(None, "--shard", min=1, help="1-based shard index"),
    n_shards: int = typer.Option(DEFAULT_SHARDS, "--shards", min=1),
    suite: str = typer.Option(DEFAULT_SUITE, "--suite"),
    model: str = typer.Option(DEFAULT_MODEL, "--model"),
    all_shards: bool = typer.Option(False, "--all", help="Print every shard prompt"),
) -> None:
    """Print a paste-ready prompt for one Composer 2.5 cloud-agent window."""
    if all_shards:
        for index in range(1, n_shards + 1):
            console.print(f"===== SHARD {index}/{n_shards} =====")
            console.print(
                worker_prompt(shard_index=index, n_shards=n_shards, suite=suite, model=model)
            )
            console.print("")
        return
    if shard is None:
        raise typer.BadParameter("pass --shard N or --all")
    console.print(worker_prompt(shard_index=shard, n_shards=n_shards, suite=suite, model=model))


@cursor_cloud_app.command("prepare")
def prepare_cmd(
    task: str = typer.Option(..., "--task", help="Task id"),
    suite: str = typer.Option(DEFAULT_SUITE, "--suite"),
    model: str = typer.Option(DEFAULT_MODEL, "--model"),
    output_dir: Path = typer.Option(Path("runs"), "--output-dir"),  # noqa: B008
    repeat: int = typer.Option(1, "--repeat", min=1),
) -> None:
    """Prepare one isolated workspace for a Cursor cloud agent to solve."""
    manifest = prepare_session(
        task_id=task,
        model=model,
        suite=suite,
        output_dir=output_dir,
        repeat_index=repeat,
    )
    console.print_json(json.dumps(manifest, indent=2))


@cursor_cloud_app.command("prepare-shard")
def prepare_shard_cmd(
    shard: int = typer.Option(..., "--shard", min=1),
    n_shards: int = typer.Option(DEFAULT_SHARDS, "--shards", min=1),
    suite: str = typer.Option(DEFAULT_SUITE, "--suite"),
    model: str = typer.Option(DEFAULT_MODEL, "--model"),
    output_dir: Path = typer.Option(Path("runs/cursor-cloud"), "--output-dir"),  # noqa: B008
    repeats: int = typer.Option(1, "--repeats", min=1),
) -> None:
    """Prepare every task in one shard (round-robin over the suite)."""
    payload = prepare_shard(
        shard_index=shard,
        n_shards=n_shards,
        suite=suite,
        model=model,
        output_dir=output_dir,
        repeats=repeats,
    )
    console.print_json(json.dumps(payload, indent=2))


@cursor_cloud_app.command("finalize")
def finalize_cmd(
    run_dir: Path = typer.Argument(..., help="Run directory from prepare"),  # noqa: B008
    transcript: Path | None = typer.Option(  # noqa: B008
        None, "--transcript", help="Optional cloud-agent transcript.json"
    ),
    bc_id: str | None = typer.Option(None, "--bc-id", help="Cloud agent bcId for provenance"),
) -> None:
    """Grade a prepared session and write summary.json with token estimates."""
    summary = finalize_session(
        run_dir=run_dir,
        transcript_path=transcript,
        agent_bc_id=bc_id,
    )
    console.print_json(json.dumps(summary, indent=2))


@cursor_cloud_app.command("finalize-shard")
def finalize_shard_cmd(
    shard: int = typer.Option(..., "--shard", min=1),
    n_shards: int = typer.Option(DEFAULT_SHARDS, "--shards", min=1),
    suite: str = typer.Option(DEFAULT_SUITE, "--suite"),
    output_dir: Path = typer.Option(Path("runs/cursor-cloud"), "--output-dir"),  # noqa: B008
    transcript_dir: Path | None = typer.Option(  # noqa: B008
        None, "--transcript-dir", help="Optional dir of <run_id>.json transcripts"
    ),
) -> None:
    """Grade every prepared run in a shard and write shard-summary.json."""
    report = finalize_shard(
        shard_index=shard,
        n_shards=n_shards,
        suite=suite,
        output_dir=output_dir,
        transcript_dir=transcript_dir,
    )
    # Keep stdout readable: drop nested verifier payloads from the rollup.
    slim = {
        "suite": report["suite"],
        "shard_index": report["shard_index"],
        "n_shards": report["n_shards"],
        "n_runs": report["n_runs"],
        "n_pass": report["n_pass"],
        "runs": [
            {
                "task_id": s["task_id"],
                "functional": (s.get("scores") or {}).get("functional"),
                "cost_usd": s.get("cost_usd"),
                "tokens": s.get("tokens"),
            }
            for s in report["summaries"]
        ],
    }
    console.print_json(json.dumps(slim, indent=2))


@cursor_cloud_app.command("price-transcript")
def price_transcript_cmd(
    transcript: Path = typer.Argument(..., help="Cloud-agent transcript.json"),  # noqa: B008
    model: str = typer.Option(DEFAULT_MODEL, "--model"),
) -> None:
    """Price a Cursor cloud-agent transcript (provider usage or chars/4)."""
    payload = priced_transcript(load_transcript(transcript), model)
    console.print_json(json.dumps(payload, indent=2))


@cursor_cloud_app.command("apply-transcript")
def apply_transcript_cmd(
    run_dir: Path = typer.Argument(..., help="Finalized run directory"),  # noqa: B008
    transcript: Path = typer.Option(..., "--transcript"),  # noqa: B008
) -> None:
    """Re-price a finalized run from a transcript without re-running tests."""
    summary = apply_transcript(run_dir=run_dir, transcript_path=transcript)
    console.print_json(
        json.dumps(
            {
                "task_id": summary.get("task_id"),
                "cost_usd": summary.get("cost_usd"),
                "tokens": summary.get("tokens"),
            },
            indent=2,
        )
    )
