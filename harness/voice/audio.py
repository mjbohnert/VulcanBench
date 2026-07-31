"""Audio conditions, WAV utilities, noise mixing, and the render cache.

Format choice
-------------
Master renders are **24 kHz mono PCM16 WAV**: OpenAI TTS emits 24 kHz WAV
natively and the OpenAI Realtime API consumes 24 kHz PCM16, so the master
needs no resampling for that path. Gemini Live requires 16 kHz input, so
adapters that need it downsample from the master at send time. Both rates
and the conversion point are recorded in the run manifest.

Noise condition
---------------
The ``noise`` condition mixes an ambient clip (cafe or street, chosen
deterministically per item by hashing the item id) into the clean render at
a fixed **10 dB SNR**, computed from RMS over the speech segment. The clip
set and SNR are documented in ``tasks/voice-v1/noise/README.md``.

Everything here is stdlib-only (``wave`` + ``audioop``). ``audioop`` is
deprecated upstream but present on Python 3.12, which this repo pins; if the
project moves to 3.13 these helpers need a replacement (tracked in the
module docstring on purpose).
"""

from __future__ import annotations

import audioop
import hashlib
import json
import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from harness.voice.items import item_text_sha256

if TYPE_CHECKING:
    from harness.voice.items import VoiceItem
    from harness.voice.tts import TTSProvider

MASTER_RATE_HZ = 24_000
SNR_DB = 10.0
SAMPLE_WIDTH = 2  # PCM16
CHANNELS = 1

RATES: dict[str, float] = {"normal": 1.0, "fast": 1.25}
NOISES: tuple[str, ...] = ("clean", "noise10db")


@dataclass(frozen=True)
class Condition:
    """One cell of the audio rendering matrix."""

    voice: str
    rate: str  # "normal" | "fast"
    noise: str  # "clean" | "noise10db"

    @property
    def slug(self) -> str:
        return f"{self.voice}_{self.rate}_{self.noise}"


#: The text baseline is modeled as a pseudo-condition so results rows have a
#: uniform shape; it never touches the audio pipeline.
TEXT_CONDITION_SLUG = "text"


def read_wav(path: Path) -> tuple[bytes, int]:
    """Return (mono PCM16 frames, sample_rate). Stereo is downmixed."""
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        width = wf.getsampwidth()
        channels = wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
    if width != SAMPLE_WIDTH:
        frames = audioop.lin2lin(frames, width, SAMPLE_WIDTH)
    if channels == 2:
        frames = audioop.tomono(frames, SAMPLE_WIDTH, 0.5, 0.5)
    return frames, rate


def write_wav(path: Path, frames: bytes, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(rate)
        wf.writeframes(frames)


def resample(frames: bytes, from_hz: int, to_hz: int) -> bytes:
    """Linear resample of mono PCM16 frames."""
    if from_hz == to_hz:
        return frames
    converted, _ = audioop.ratecv(frames, SAMPLE_WIDTH, CHANNELS, from_hz, to_hz, None)
    return converted


def rms_dbfs(frames: bytes) -> float:
    """RMS level in dBFS (0 = full scale); -inf for silence."""
    rms = audioop.rms(frames, SAMPLE_WIDTH)
    if rms <= 0:
        return float("-inf")
    return 20.0 * math.log10(rms / 32768.0)


def _loop_to_length(noise: bytes, n_bytes: int) -> bytes:
    reps = (n_bytes // len(noise)) + 1
    return (noise * reps)[:n_bytes]


def mix_noise(speech: bytes, noise: bytes, snr_db: float = SNR_DB) -> bytes:
    """Mix ``noise`` under ``speech`` at ``snr_db`` (RMS-based), clip-guarded.

    The noise is looped/trimmed to the speech length and scaled so that
    ``speech_rms_db - noise_rms_db == snr_db``. Output is attenuated 3 dB
    before summing to keep headroom, identically for every item, so relative
    levels are preserved.
    """
    speech_rms = audioop.rms(speech, SAMPLE_WIDTH)
    noise = _loop_to_length(noise, len(speech))
    noise_rms = audioop.rms(noise, SAMPLE_WIDTH)
    if speech_rms <= 0 or noise_rms <= 0:
        raise ValueError("cannot mix silent speech or silent noise")
    target_noise_rms = speech_rms / (10.0 ** (snr_db / 20.0))
    scaled_noise = audioop.mul(noise, SAMPLE_WIDTH, target_noise_rms / noise_rms)
    headroom = 10.0 ** (-3.0 / 20.0)
    speech_att = audioop.mul(speech, SAMPLE_WIDTH, headroom)
    noise_att = audioop.mul(scaled_noise, SAMPLE_WIDTH, headroom)
    return audioop.add(speech_att, noise_att, SAMPLE_WIDTH)


def pick_noise_clip(item_id: str, clips: list[Path]) -> Path:
    """Deterministically assign one ambient clip to an item (stable across runs)."""
    if not clips:
        raise ValueError("no noise clips available")
    digest = hashlib.sha256(item_id.encode()).digest()
    return sorted(clips)[digest[0] % len(clips)]


class AudioCache:
    """Disk cache of rendered questions keyed by (item, voice, rate, noise).

    Layout: ``<root>/<item_id>/<voice>_<rate>_<noise>.wav`` with a sidecar
    ``manifest.json`` per item recording the sha256 of the question text each
    file was rendered from — editing a question invalidates its renders.
    """

    def __init__(self, root: Path, noise_dir: Path | None = None) -> None:
        self.root = root
        self.noise_dir = noise_dir

    def path_for(self, item_id: str, condition: Condition) -> Path:
        return self.root / item_id / f"{condition.slug}.wav"

    def _manifest_path(self, item_id: str) -> Path:
        return self.root / item_id / "manifest.json"

    def _load_manifest(self, item_id: str) -> dict[str, str]:
        p = self._manifest_path(item_id)
        if not p.exists():
            return {}
        data: dict[str, str] = json.loads(p.read_text())
        return data

    def _store_manifest_entry(self, item_id: str, slug: str, text_sha: str) -> None:
        manifest = self._load_manifest(item_id)
        manifest[slug] = text_sha
        p = self._manifest_path(item_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(manifest, indent=1, sort_keys=True))

    def is_fresh(self, item: VoiceItem, condition: Condition) -> bool:
        wav = self.path_for(item.id, condition)
        if not wav.exists():
            return False
        return self._load_manifest(item.id).get(condition.slug) == item_text_sha256(item)

    def noise_clips(self) -> list[Path]:
        if self.noise_dir is None:
            return []
        return sorted(self.noise_dir.glob("*.wav"))

    def ensure(self, item: VoiceItem, condition: Condition, tts: TTSProvider) -> Path:
        """Render (or reuse) the WAV for ``item`` under ``condition``."""
        out = self.path_for(item.id, condition)
        if self.is_fresh(item, condition):
            return out

        wav_bytes = tts.synthesize(item.question, condition.voice, RATES[condition.rate])
        tmp = out.with_suffix(".tmp.wav")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(wav_bytes)
        frames, rate = read_wav(tmp)
        tmp.unlink()
        frames = resample(frames, rate, MASTER_RATE_HZ)

        if condition.noise == "noise10db":
            clip_path = pick_noise_clip(item.id, self.noise_clips())
            noise_frames, noise_rate = read_wav(clip_path)
            noise_frames = resample(noise_frames, noise_rate, MASTER_RATE_HZ)
            frames = mix_noise(frames, noise_frames, SNR_DB)

        write_wav(out, frames, MASTER_RATE_HZ)
        self._store_manifest_entry(item.id, condition.slug, item_text_sha256(item))
        return out
