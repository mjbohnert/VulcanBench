"""Estimate token usage from a Cursor cloud-agent transcript export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _chars_to_tokens(chars: int) -> int:
    """Rough token estimate (≈4 chars/token). Not provider-exact; good for cost bands."""
    return max(0, round(chars / 4))


def _text_len(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(_text_len(v) for v in value)
    if isinstance(value, dict):
        return sum(_text_len(v) for v in value.values())
    return len(str(value))


def estimate_tokens_from_transcript(transcript: dict[str, Any]) -> dict[str, int]:
    """Return input / reasoning / output token estimates from a transcript JSON object.

  - **input_tokens**: user prompts + tool results the model consumed
  - **reasoning_tokens**: assistant ``thinking`` blocks (inference / chain-of-thought)
  - **output_tokens**: assistant visible ``text`` replies
    """
    input_chars = reasoning_chars = output_chars = 0
    for msg in transcript.get("messages") or []:
        role = str(msg.get("role") or "")
        if role == "user":
            input_chars += _text_len(msg.get("text"))
        elif role == "tool":
            input_chars += _text_len(msg.get("text")) + _text_len(msg.get("content"))
        elif role == "assistant":
            reasoning_chars += _text_len(msg.get("thinking"))
            output_chars += _text_len(msg.get("text"))

    return {
        "input_tokens": _chars_to_tokens(input_chars),
        "reasoning_tokens": _chars_to_tokens(reasoning_chars),
        "output_tokens": _chars_to_tokens(output_chars),
        "total_tokens": _chars_to_tokens(input_chars + reasoning_chars + output_chars),
        "input_chars": input_chars,
        "reasoning_chars": reasoning_chars,
        "output_chars": output_chars,
        "estimation": "chars/4 from cloud-agent transcript (not provider-reported)",
    }


def load_transcript(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
