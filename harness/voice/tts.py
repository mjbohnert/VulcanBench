"""TTS providers behind a swappable interface.

The default provider is OpenAI ``tts-1``: it emits 24 kHz WAV directly (the
suite's master format) and honours a numeric ``speed`` parameter, which makes
the ``fast`` (1.25x) condition well-defined rather than prompt-dependent.
Voices used by voice-v1: ``onyx`` (male), ``shimmer`` (female), ``fable``
(British-accented), gender plus one accent axis. Accent range on OpenAI TTS
is limited; a second provider can be added behind :class:`TTSProvider`
without touching the cache or runner.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from harness.agent.providers import ProviderError

DEFAULT_VOICES: tuple[str, ...] = ("onyx", "shimmer", "fable")
PRIMARY_VOICE = "onyx"


class TTSProvider(ABC):
    """Synthesize speech for a question. Returns WAV bytes."""

    name: str
    model: str

    @abstractmethod
    def synthesize(self, text: str, voice: str, speed: float) -> bytes:
        """Render ``text`` to WAV bytes at ``speed`` (1.0 = normal)."""


class OpenAITTS(TTSProvider):
    name = "openai"
    model = "tts-1"

    def __init__(self, model: str | None = None) -> None:
        if model:
            self.model = model

    def synthesize(self, text: str, voice: str, speed: float) -> bytes:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is not set (required for TTS)")
        payload = {
            "model": self.model,
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": "wav",
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return bytes(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:500]
            raise ProviderError(f"TTS HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"TTS request failed: {exc.reason}") from exc


_REGISTRY: dict[str, type[TTSProvider]] = {"openai": OpenAITTS}


def get_tts(name: str) -> TTSProvider:
    """Instantiate a TTS provider by registry name (e.g. ``openai``)."""
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise ProviderError(
            f"unknown TTS provider {name!r}; available: {sorted(_REGISTRY)}"
        ) from None
