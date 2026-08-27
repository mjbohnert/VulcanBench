"""Tests for cursor-agent benchmark sessions."""

from __future__ import annotations

import json
from pathlib import Path

from harness.cursor_agent.session import finalize_session, prepare_session
from harness.cursor_agent.tokens import estimate_tokens_from_transcript


def test_estimate_tokens_from_transcript() -> None:
    transcript = {
        "messages": [
            {"role": "user", "text": "a" * 400},
            {"role": "assistant", "thinking": "b" * 200, "text": "c" * 100},
            {"role": "tool", "text": "d" * 80},
        ]
    }
    tokens = estimate_tokens_from_transcript(transcript)
    assert tokens["input_tokens"] == 120  # (400+80)/4
    assert tokens["reasoning_tokens"] == 50
    assert tokens["output_tokens"] == 25


def test_prepare_and_finalize_writes_summary(tmp_path: Path) -> None:
    manifest = prepare_session(
        task_id="oss-pflag-uintslice-hex",
        suite="v4",
        model="cursor-agent:composer-2.5",
        output_dir=tmp_path / "runs",
    )
    run_dir = Path(manifest["run_dir"])

    transcript = {
        "messages": [
            {"role": "user", "text": "fix"},
            {"role": "assistant", "thinking": "investigate", "text": "done"},
        ]
    }
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")

    session = json.loads((run_dir / "session.json").read_text(encoding="utf-8"))
    assert session["isolation_version"] >= 2
    prompt = (run_dir / "agent_prompt.md").read_text(encoding="utf-8")
    assert "Benchmark isolation rules" in prompt

    summary = finalize_session(
        run_dir=run_dir,
        transcript_path=transcript_path,
        agent_bc_id="bc-test",
    )
    assert summary["tokens"]["input"] >= 1
    assert summary["tokens"]["reasoning"] >= 1
    assert summary["tokens"]["output"] >= 1
    assert summary["cli_agent"]["harness"] == "cursor-agent"
    assert summary["integrity"]["passed"] is True
    assert summary["integrity"]["isolation_version"] >= 2
    assert (run_dir / "summary.json").is_file()
