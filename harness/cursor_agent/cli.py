"""CLI for Cursor cloud-agent benchmark sessions."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from harness.cursor_agent.session import finalize_session, prepare_session
from harness.suite import load_suite

console = Console()
cursor_agent_app = typer.Typer(
    name="cursor-agent",
    help="Benchmark Cursor cloud agents (first-party tools; no API key)",
    no_args_is_help=True,
)


@cursor_agent_app.command("prepare")
def prepare_cmd(
    task: str = typer.Option(..., "--task", help="Task id"),
    suite: str = typer.Option("v4", "--suite"),
    model: str = typer.Option("cursor-agent:composer-2.5", "--model"),
    output_dir: Path = typer.Option(Path("runs"), "--output-dir"),  # noqa: B008
    repeat: int = typer.Option(1, "--repeat", min=1, help="Repeat index (metadata only)"),
) -> None:
    """Prepare a workspace for a Cursor cloud agent to solve."""
    manifest = prepare_session(
        task_id=task,
        model=model,
        suite=suite,
        output_dir=output_dir,
        repeat_index=repeat,
    )
    console.print_json(json.dumps(manifest, indent=2))


@cursor_agent_app.command("finalize")
def finalize_cmd(
    run_dir: Path = typer.Argument(..., help="Run directory from prepare"),  # noqa: B008
    transcript: Path = typer.Option(..., "--transcript", help="Cloud-agent transcript.json path"),  # noqa: B008
    bc_id: str | None = typer.Option(None, "--bc-id", help="Cloud agent bcId for provenance"),
) -> None:
    """Grade a prepared session and write summary.json with token estimates."""
    summary = finalize_session(
        run_dir=run_dir,
        transcript_path=transcript,
        agent_bc_id=bc_id,
    )
    console.print_json(json.dumps(summary, indent=2))


@cursor_agent_app.command("list-tasks")
def list_tasks_cmd(suite: str = typer.Option("v4", "--suite")) -> None:
    """List task ids in a suite."""
    s = load_suite(suite)
    for task_id in s.task_ids:
        console.print(task_id)
