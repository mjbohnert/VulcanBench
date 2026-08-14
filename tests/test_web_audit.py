"""Tests for the CLI-harness web-leakage audit."""

from __future__ import annotations

import json
from pathlib import Path

from harness.agent.web_audit import audit_stream, upstream_refs

META = {
    "upstream": {
        "url": "https://github.com/PennyLaneAI/pennylane/pull/9459",
        "commit": "7bf1af3c952c11bd716f7859887eb17fe9a5f4de",
    }
}


def _stream(tmp_path: Path, lines: list[dict]) -> Path:
    p = tmp_path / "cli-agent-stream.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    return p


def _fetch(url: str) -> dict:
    return {
        "type": "tool_call",
        "subtype": "started",
        "tool_call": {"webFetchToolCall": {"args": {"url": url}}},
    }


def _search(term: str) -> dict:
    return {
        "type": "tool_call",
        "subtype": "started",
        "tool_call": {"webSearchToolCall": {"args": {"searchTerm": term}}},
    }


def test_upstream_refs_parses_provenance() -> None:
    refs = upstream_refs(META)
    assert refs == {"repo": "pennylaneai/pennylane", "pr": "9459", "commit": "7bf1af3c952c"}


def test_no_stream_is_no_web(tmp_path: Path) -> None:
    audit = audit_stream(tmp_path / "missing.jsonl", META)
    assert audit["verdict"] == "no_web"
    assert audit["contaminated"] is False


def test_unrelated_browsing_is_web_used(tmp_path: Path) -> None:
    p = _stream(tmp_path, [_search("python asyncio docs"), _fetch("https://docs.python.org/3/")])
    audit = audit_stream(p, META)
    assert audit["verdict"] == "web_used"
    assert audit["contaminated"] is False
    assert audit["web_fetches"] == 1
    assert "docs.python.org" in audit["hosts"]


def test_upstream_repo_fetch_is_contaminated(tmp_path: Path) -> None:
    # Post-fix sources on main contain the merged solution.
    p = _stream(
        tmp_path,
        [_fetch("https://raw.githubusercontent.com/PennyLaneAI/pennylane/master/pennylane/x.py")],
    )
    audit = audit_stream(p, META)
    assert audit["verdict"] == "upstream_access"
    assert audit["contaminated"] is True


def test_exact_pr_fetch_is_solution_retrieval(tmp_path: Path) -> None:
    p = _stream(tmp_path, [_fetch("https://github.com/PennyLaneAI/pennylane/pull/9459")])
    assert audit_stream(p, META)["verdict"] == "solution_retrieval"


def test_fix_commit_fetch_is_solution_retrieval(tmp_path: Path) -> None:
    p = _stream(
        tmp_path,
        [_fetch("https://github.com/PennyLaneAI/pennylane/commit/7bf1af3c952c11bd716f")],
    )
    assert audit_stream(p, META)["verdict"] == "solution_retrieval"


def test_upstream_diff_fetch_is_solution_retrieval(tmp_path: Path) -> None:
    p = _stream(
        tmp_path,
        [_fetch("https://github.com/PennyLaneAI/pennylane/compare/a...b.diff")],
    )
    assert audit_stream(p, META)["verdict"] == "solution_retrieval"


def test_pr_number_alone_on_other_repo_is_not_solution(tmp_path: Path) -> None:
    # /pull/9459 on an unrelated repo must not trip the tripwire.
    p = _stream(tmp_path, [_fetch("https://github.com/some/other-repo/pull/9459")])
    audit = audit_stream(p, META)
    assert audit["verdict"] == "web_used"


def test_task_without_upstream_never_flags_contamination(tmp_path: Path) -> None:
    p = _stream(tmp_path, [_fetch("https://github.com/PennyLaneAI/pennylane/pull/9459")])
    audit = audit_stream(p, {"id": "synthetic-task"})
    assert audit["verdict"] == "web_used"
    assert audit["contaminated"] is False
