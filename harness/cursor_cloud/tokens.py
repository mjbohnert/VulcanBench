"""Token usage from a Cursor cloud-agent transcript export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.agent.cli_agents import cursor_usage_payload, fold_cursor_usage


def _chars_to_tokens(chars: int) -> int:
    """Rough token estimate (~4 chars/token). Not provider-exact."""
    return max(0, round(chars / 4))


def _text_len(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(_text_len(item) for item in value)
    if isinstance(value, dict):
        return sum(_text_len(item) for item in value.values())
    return len(str(value))


def estimate_tokens_from_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    """Chars/4 fallback when the transcript has no provider usage block.

    - input: user prompts + tool results
    - reasoning: assistant thinking blocks
    - output: assistant visible text
    """
    input_chars = reasoning_chars = output_chars = 0
    for msg in transcript.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "")
        if role in {"user", "tool"}:
            input_chars += _text_len(msg.get("text")) + _text_len(msg.get("content"))
        elif role == "assistant":
            reasoning_chars += _text_len(msg.get("thinking"))
            output_chars += _text_len(msg.get("text")) + _text_len(msg.get("content"))
    return {
        "input_tokens": _chars_to_tokens(input_chars),
        "reasoning_tokens": _chars_to_tokens(reasoning_chars),
        "output_tokens": _chars_to_tokens(output_chars),
        "cached_input_tokens": 0,
        "total_tokens": _chars_to_tokens(input_chars + reasoning_chars + output_chars),
        "input_chars": input_chars,
        "reasoning_chars": reasoning_chars,
        "output_chars": output_chars,
        "estimation": "chars/4 from cloud-agent transcript (not provider-reported)",
    }


def _official_usage(transcript: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer a provider-reported usage object if the export includes one."""
    direct = transcript.get("usage") or transcript.get("tokenUsage")
    if isinstance(direct, dict) and direct:
        prompt, completion, cached, reasoning = fold_cursor_usage(direct)
        output = completion - reasoning
        return {
            "input_tokens": prompt,
            "reasoning_tokens": reasoning,
            "output_tokens": max(0, output),
            "cached_input_tokens": cached,
            "total_tokens": prompt + completion,
            "estimation": "provider-reported",
        }
    prompt = completion = cached = reasoning = 0
    found = False
    for msg in transcript.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        payload = cursor_usage_payload(msg) or (
            msg.get("usage") if isinstance(msg.get("usage"), dict) else None
        )
        if not isinstance(payload, dict):
            continue
        p, c, ch, r = fold_cursor_usage(payload)
        prompt += p
        completion += c
        cached += ch
        reasoning += r
        found = True
    if not found:
        return None
    return {
        "input_tokens": prompt,
        "reasoning_tokens": reasoning,
        "output_tokens": max(0, completion - reasoning),
        "cached_input_tokens": cached,
        "total_tokens": prompt + completion,
        "estimation": "provider-reported",
    }


def tokens_from_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    """Official usage when present, otherwise a chars/4 estimate."""
    official = _official_usage(transcript)
    return official if official is not None else estimate_tokens_from_transcript(transcript)


def load_transcript(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"transcript must be a JSON object, got {type(payload).__name__}")
    return payload
