"""Agent prompts for isolated cursor-agent benchmark sessions."""

from __future__ import annotations

from pathlib import Path


def build_cursor_agent_prompt(*, issue: str, workspace: Path) -> str:
    """Prompt handed to the cloud agent, with explicit isolation rules."""
    ws = workspace.resolve()
    rules = f"""## Benchmark isolation rules (mandatory)

- Work ONLY inside this workspace: `{ws}`
- Do NOT read, grep, list, or access any path outside that directory.
- Do NOT read `tasks/`, `gold_patch.diff`, or benchmark hidden tests anywhere on disk.
- Do NOT copy test files into the workspace.
- Verify using only the project's existing public tests/commands inside the workspace.
- Leave your changes uncommitted in the working tree — do not create git commits."""

    return f"# Issue\n\n{issue}\n\n{rules}"


def build_solve_instructions(manifest: dict[str, object]) -> str:
    """Instructions for a Task subagent solving one prepared run."""
    workspace = Path(str(manifest["workspace"]))
    run_dir = Path(str(manifest["run_dir"]))
    prompt_path = run_dir / "agent_prompt.md"
    return (
        "VulcanBench cursor-agent benchmark (isolated).\n\n"
        f"Read and follow: {prompt_path}\n"
        f"Workspace (ONLY directory you may edit): {workspace}\n\n"
        "Do not access /workspace/tasks, gold_patch.diff, or hidden tests.\n"
        "Solve, verify with in-repo tests only, leave uncommitted.\n"
        "Return: task_id, tests passed?, PASS/FAIL, whether you accessed paths outside workspace."
    )
