"""Pinned STT used only when a model answers in audio with no text channel.

All three launch adapters request text output, so this is a fallback path.
Whenever it runs, the results row records ``transcribed_by`` so the report
can surface how many answers passed through STT.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from harness.agent.providers import ProviderError

STT_MODEL = "gpt-4o-transcribe"


def transcribe(wav_path: Path, model: str = STT_MODEL) -> str:
    """Transcribe a WAV file via OpenAI's transcription endpoint."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ProviderError("OPENAI_API_KEY is not set (required for STT fallback)")
    boundary = uuid.uuid4().hex
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="model"\r\n\r\n',
            model.encode(),
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{wav_path.name}"\r\n'.encode(),
            b"Content-Type: audio/wav\r\n\r\n",
            wav_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise ProviderError(f"STT HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"STT request failed: {exc.reason}") from exc
    text = data.get("text")
    if not isinstance(text, str):
        raise ProviderError(f"STT returned no text: {json.dumps(data)[:200]}")
    return text
