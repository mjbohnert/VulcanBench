"""Benchmark integrity checks for cursor-agent sessions.

Agents run with host filesystem access, so we cannot fully prevent reads of
``tasks/<suite>/<id>/gold_patch.diff`` or hidden ``tests/``.  These helpers
detect and remediate the two contamination modes we can enforce at grade time:

1. Hidden tests copied into the workspace before finalize (strip before verify).
2. Transcript evidence that the agent read gold patches or the tasks tree.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from harness.tasks import Task

ISOLATION_VERSION = 2

_ISOLATION_ECHO = re.compile(
    r"do not read|benchmark isolation|CRITICAL:|reference solution patches",
    re.I,
)


def _agent_message_text(messages: list[Any]) -> str:
    """Concatenate assistant/tool text, dropping echoed isolation-rule lines."""
    chunks: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") not in ("assistant", "tool"):
            continue
        for key in ("text", "thinking"):
            raw = msg.get(key)
            if not isinstance(raw, str) or not raw:
                continue
            kept = [
                line
                for line in raw.splitlines()
                if not _ISOLATION_ECHO.search(line)
            ]
            chunks.append("\n".join(kept))
    return "\n".join(chunks)


def find_leaked_hidden_tests(task: Task, workspace: Path) -> list[Path]:
    """Paths under ``workspace`` that match this task's hidden ``tests/`` tree."""
    hidden = task.hidden_tests_dir
    if hidden is None or not hidden.is_dir():
        return []
    leaked: list[Path] = []
    for src in hidden.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(hidden)
        dest = workspace / rel
        if dest.is_file():
            leaked.append(dest)
    return leaked


def strip_leaked_hidden_tests(task: Task, workspace: Path) -> list[str]:
    """Remove hidden tests the agent copied into the workspace; return rel paths."""
    removed: list[str] = []
    for path in find_leaked_hidden_tests(task, workspace):
        path.unlink()
        removed.append(path.relative_to(workspace).as_posix())
    return removed


def audit_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    """Heuristic audit of a cloud-agent transcript for benchmark leakage."""
    messages = transcript.get("messages") or []
    agent_blob = _agent_message_text(messages if isinstance(messages, list) else [])
    flags = {
        "gold_patch": bool(re.search(r"gold_patch\.diff|/gold_patch", agent_blob, re.I)),
        "tasks_tree": bool(re.search(r"tasks/v\d+/", agent_blob)),
        "hidden_tests": bool(re.search(r"/tests/oss_tests|\"vb_", agent_blob)),
    }
    return {
        "contaminated": any(flags.values()),
        "flags": flags,
    }


def assess_integrity(
    *,
    task: Task,
    workspace: Path,
    transcript: dict[str, Any],
) -> dict[str, Any]:
    """Strip leaked tests and audit the transcript; ``passed`` is False if contaminated."""
    removed = strip_leaked_hidden_tests(task, workspace)
    transcript_audit = audit_transcript(transcript)
    return {
        "passed": not removed and not transcript_audit["contaminated"],
        "isolation_version": ISOLATION_VERSION,
        "leaked_tests_removed": removed,
        "transcript": transcript_audit,
    }
