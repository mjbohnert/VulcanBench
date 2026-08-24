"""Question set loading and validation for the voice suite.

Items live in ``tasks/voice-v1/questions.jsonl``: one JSON object per line.
The set is held out by construction (written for this suite, never copied
from public benchmarks) and is reviewed in-repo like any other task source.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal[
    "arithmetic",
    "multi-step-reasoning",
    "general-knowledge",
    "instruction-following",
    "numeric-extraction",
]

CATEGORIES: tuple[str, ...] = (
    "arithmetic",
    "multi-step-reasoning",
    "general-knowledge",
    "instruction-following",
    "numeric-extraction",
)


class VoiceItem(BaseModel):
    """One short-form question with an objectively checkable answer."""

    id: str
    category: Category
    question: str
    answer: str
    #: Alternative surface forms accepted as correct verbatim (post-normalization).
    accept: list[str] = Field(default_factory=list)

    @field_validator("question", "answer")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must be non-empty")
        return v.strip()


def load_items(path: Path) -> list[VoiceItem]:
    """Load and validate ``questions.jsonl``; IDs must be unique."""
    items: list[VoiceItem] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = VoiceItem.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{path}:{lineno}: invalid item: {exc}") from exc
        if item.id in seen:
            raise ValueError(f"{path}:{lineno}: duplicate item id {item.id!r}")
        seen.add(item.id)
        items.append(item)
    if not items:
        raise ValueError(f"{path}: no items found")
    return items


def questions_sha256(path: Path) -> str:
    """Content hash of the question file, recorded in run manifests."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def item_text_sha256(item: VoiceItem) -> str:
    """Hash of the spoken text; used to invalidate cached audio on edits."""
    return hashlib.sha256(item.question.encode()).hexdigest()
