"""Tests for cursor-agent benchmark integrity checks."""

from __future__ import annotations

import json
from pathlib import Path

from harness.cursor_agent.integrity import (
    ISOLATION_VERSION,
    assess_integrity,
    audit_transcript,
    find_leaked_hidden_tests,
    strip_leaked_hidden_tests,
)
from harness.cursor_agent.prompt import build_cursor_agent_prompt, build_solve_instructions
from harness.tasks import Task


def _fake_task(tmp_path: Path) -> Task:
    root = tmp_path / "task"
    hidden = root / "tests" / "osscheck"
    hidden.mkdir(parents=True)
    (hidden / "oss_test.go").write_text("package osscheck\n", encoding="utf-8")
    (root / "issue.md").write_text("# fix it\n", encoding="utf-8")
    return Task(
        task_id="fake-task",
        root=root,
        metadata={},
        issue="# fix it",
        verifier=None,
    )


def test_audit_transcript_clean() -> None:
    audit = audit_transcript({"messages": [{"role": "user", "text": "fix the bug in uint_slice.go"}]})
    assert audit["contaminated"] is False
    assert audit["flags"] == {
        "gold_patch": False,
        "tasks_tree": False,
        "hidden_tests": False,
    }


def test_audit_transcript_flags_gold_patch() -> None:
    audit = audit_transcript({"messages": [{"role": "assistant", "text": "read gold_patch.diff"}]})
    assert audit["contaminated"] is True
    assert audit["flags"]["gold_patch"] is True


def test_audit_transcript_ignores_isolation_rule_wording() -> None:
    audit = audit_transcript(
        {"messages": [{"role": "user", "text": "Do NOT read reference solution patches"}]}
    )
    assert audit["contaminated"] is False


def test_audit_transcript_flags_tasks_tree() -> None:
    audit = audit_transcript({"messages": [{"role": "tool", "text": "tasks/v4/oss-pflag/foo"}]})
    assert audit["contaminated"] is True
    assert audit["flags"]["tasks_tree"] is True


def test_audit_transcript_flags_hidden_tests() -> None:
    audit = audit_transcript(
        {"messages": [{"role": "assistant", "text": "copied tasks/v4/foo/tests/oss_tests.py"}]}
    )
    assert audit["contaminated"] is True
    assert audit["flags"]["hidden_tests"] is True


def test_find_and_strip_leaked_hidden_tests(tmp_path: Path) -> None:
    task = _fake_task(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    leaked = workspace / "osscheck" / "oss_test.go"
    leaked.parent.mkdir()
    leaked.write_text("leaked", encoding="utf-8")

    found = find_leaked_hidden_tests(task, workspace)
    assert len(found) == 1
    assert found[0] == leaked

    removed = strip_leaked_hidden_tests(task, workspace)
    assert removed == ["osscheck/oss_test.go"]
    assert not leaked.is_file()
    assert strip_leaked_hidden_tests(task, workspace) == []


def test_assess_integrity_passes_when_clean(tmp_path: Path) -> None:
    task = _fake_task(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    transcript = {"messages": [{"role": "user", "text": "solve in workspace only"}]}

    result = assess_integrity(task=task, workspace=workspace, transcript=transcript)
    assert result["passed"] is True
    assert result["isolation_version"] == ISOLATION_VERSION
    assert result["leaked_tests_removed"] == []
    assert result["transcript"]["contaminated"] is False


def test_assess_integrity_fails_on_leaked_tests(tmp_path: Path) -> None:
    task = _fake_task(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    leaked = workspace / "osscheck" / "oss_test.go"
    leaked.parent.mkdir()
    leaked.write_text("leaked", encoding="utf-8")
    transcript = {"messages": [{"role": "user", "text": "ok"}]}

    result = assess_integrity(task=task, workspace=workspace, transcript=transcript)
    assert result["passed"] is False
    assert result["leaked_tests_removed"] == ["osscheck/oss_test.go"]
    assert not leaked.is_file()


def test_assess_integrity_fails_on_contaminated_transcript(tmp_path: Path) -> None:
    task = _fake_task(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    transcript = {"messages": [{"role": "assistant", "text": "tasks/v4/foo/gold_patch.diff"}]}

    result = assess_integrity(task=task, workspace=workspace, transcript=transcript)
    assert result["passed"] is False
    assert result["transcript"]["contaminated"] is True


def test_build_cursor_agent_prompt_includes_isolation_rules(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prompt = build_cursor_agent_prompt(issue="# Bug\n\nfix it", workspace=workspace)
    assert "Benchmark isolation rules" in prompt
    assert str(workspace.resolve()) in prompt
    assert "Do NOT read `tasks/`" in prompt
    assert "reference solution patches" in prompt


def test_build_solve_instructions_points_at_agent_prompt(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True)
    manifest = {
        "workspace": str(workspace),
        "run_dir": str(run_dir),
    }
    instructions = build_solve_instructions(manifest)
    assert str(run_dir / "agent_prompt.md") in instructions
    assert str(workspace) in instructions
    assert "Do not access /workspace/tasks" in instructions
