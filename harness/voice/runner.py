"""Matrix runner for the voice suite: plan → render → ask → score → record.

Determinism
-----------
The condition matrix and its seeded subset are computed up front from a fixed
seed (default ``20260729``) so every run — including resumed runs — plans the
identical set of (model, mode, item, condition) work units. Sampling
parameters we control are pinned (temperature 0 where the API accepts it).

Resumability
------------
Results append to ``results.jsonl`` one row per completed unit. On start the
runner reads existing rows and skips finished units, so a crashed run is
resumed by re-invoking the same command.

Matrix (per model)
------------------
- text baseline: full item set
- audio clean/normal: full item set x each voice
- audio fast (primary voice, clean): seeded subset
- audio noise10db (primary voice, normal): seeded subset
"""

from __future__ import annotations

import json
import random
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness import __version__
from harness.agent.providers import LLMProvider, ProviderError, get_provider
from harness.voice.adapters import SYSTEM_PROMPT, VoiceAnswer, VoiceModel, get_voice_model
from harness.voice.audio import (
    MASTER_RATE_HZ,
    SNR_DB,
    TEXT_CONDITION_SLUG,
    AudioCache,
    Condition,
)
from harness.voice.items import VoiceItem, load_items, questions_sha256
from harness.voice.scorer import score_response
from harness.voice.stt import STT_MODEL
from harness.voice.tts import DEFAULT_VOICES, PRIMARY_VOICE, get_tts

DEFAULT_SEED = 20260729
DEFAULT_SUBSET_N = 60
DRY_RUN_N = 5
JUDGE_DEFAULT = "anthropic:claude-opus-5"


@dataclass(frozen=True)
class WorkUnit:
    model_spec: str
    mode: str  # "text" | "audio"
    item_id: str
    condition_slug: str
    condition: Condition | None  # None for the text baseline

    @property
    def key(self) -> str:
        return f"{self.model_spec}|{self.mode}|{self.item_id}|{self.condition_slug}"


@dataclass
class RunConfig:
    models: list[str]
    questions_path: Path
    out_dir: Path
    cache_dir: Path
    noise_dir: Path
    voices: tuple[str, ...] = DEFAULT_VOICES
    primary_voice: str = PRIMARY_VOICE
    subset_n: int = DEFAULT_SUBSET_N
    seed: int = DEFAULT_SEED
    dry_run: bool = False
    judge_model: str = JUDGE_DEFAULT
    tts_provider: str = "openai"
    max_retries: int = 3
    run_id: str = field(default_factory=lambda: datetime.now(UTC).strftime("voice-%Y%m%d-%H%M%S"))


def subset_ids(items: list[VoiceItem], n: int, seed: int) -> list[str]:
    """Deterministic subset used for the fast-rate and noise conditions."""
    ids = [it.id for it in items]
    rng = random.Random(seed)
    if n >= len(ids):
        return ids
    return sorted(rng.sample(ids, n))


def plan_units(cfg: RunConfig, items: list[VoiceItem]) -> list[WorkUnit]:
    if cfg.dry_run:
        items = items[:DRY_RUN_N]
    sub = set(subset_ids(items, cfg.subset_n, cfg.seed))
    units: list[WorkUnit] = []
    for model in cfg.models:
        for it in items:
            units.append(WorkUnit(model, "text", it.id, TEXT_CONDITION_SLUG, None))
        for voice in cfg.voices if not cfg.dry_run else (cfg.primary_voice,):
            cond = Condition(voice=voice, rate="normal", noise="clean")
            for it in items:
                units.append(WorkUnit(model, "audio", it.id, cond.slug, cond))
        if not cfg.dry_run:
            fast = Condition(voice=cfg.primary_voice, rate="fast", noise="clean")
            noisy = Condition(voice=cfg.primary_voice, rate="normal", noise="noise10db")
            for it in items:
                if it.id in sub:
                    units.append(WorkUnit(model, "audio", it.id, fast.slug, fast))
                    units.append(WorkUnit(model, "audio", it.id, noisy.slug, noisy))
    return units


def _completed_keys(results_path: Path) -> set[str]:
    done: set[str] = set()
    if not results_path.exists():
        return done
    for line in results_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("error") is None:
            done.add(f"{row['model']}|{row['mode']}|{row['question_id']}|{row['condition_slug']}")
    return done


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=False
        )
    except OSError:  # pragma: no cover - git missing entirely
        return None
    return out.stdout.strip() or None


def write_manifest(cfg: RunConfig, items: list[VoiceItem], run_dir: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "run_id": cfg.run_id,
        "suite": "voice-v1",
        "started_at": datetime.now(UTC).isoformat(),
        "harness_version": __version__,
        "git_commit": _git_commit(),
        "models": cfg.models,
        "tts": {
            "provider": cfg.tts_provider,
            "voices": list(cfg.voices),
            "primary_voice": cfg.primary_voice,
            "rates": {"normal": 1.0, "fast": 1.25},
        },
        "stt_fallback": STT_MODEL,
        "judge_model": cfg.judge_model,
        "system_prompt": SYSTEM_PROMPT,
        "audio": {"master_rate_hz": MASTER_RATE_HZ, "snr_db": SNR_DB},
        "seed": cfg.seed,
        "subset_n": cfg.subset_n,
        "subset_ids": subset_ids(items, cfg.subset_n, cfg.seed),
        "dry_run": cfg.dry_run,
        "questions_sha256": questions_sha256(cfg.questions_path),
        "n_items": len(items),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


class _RateLimiter:
    def __init__(self) -> None:
        self._last: dict[str, float] = {}

    def wait(self, key: str, min_interval_s: float) -> None:
        last = self._last.get(key)
        if last is not None:
            elapsed = time.monotonic() - last
            if elapsed < min_interval_s:
                time.sleep(min_interval_s - elapsed)
        self._last[key] = time.monotonic()


def _ask_with_retry(
    model: VoiceModel,
    unit: WorkUnit,
    wav: Path | None,
    max_retries: int,
) -> VoiceAnswer:
    last: ProviderError | None = None
    for attempt in range(max_retries):
        try:
            if unit.mode == "text":
                # The question text travels with the unit via the caller.
                raise AssertionError("text units are answered by the caller")
            assert wav is not None
            return model.answer_audio(wav)
        except ProviderError as exc:
            last = exc
            time.sleep(min(2**attempt, 20))
    raise last if last else ProviderError("unreachable")


def run_suite(cfg: RunConfig) -> Path:
    """Execute the run; returns the run directory."""
    items = load_items(cfg.questions_path)
    by_id = {it.id: it for it in items}
    run_dir = cfg.out_dir / cfg.run_id
    results_path = run_dir / "results.jsonl"
    manifest = write_manifest(cfg, items, run_dir)
    del manifest

    units = plan_units(cfg, items)
    done = _completed_keys(results_path)
    todo = [u for u in units if u.key not in done]

    cache = AudioCache(cfg.cache_dir, noise_dir=cfg.noise_dir)
    tts = get_tts(cfg.tts_provider)
    judge: LLMProvider = get_provider(cfg.judge_model)
    models = {spec: get_voice_model(spec) for spec in cfg.models}
    limiter = _RateLimiter()

    with results_path.open("a") as sink:
        for unit in todo:
            item = by_id[unit.item_id]
            model = models[unit.model_spec]
            row: dict[str, Any] = {
                "run_id": cfg.run_id,
                "ts": datetime.now(UTC).isoformat(),
                "model": unit.model_spec,
                "mode": unit.mode,
                "question_id": item.id,
                "category": item.category,
                "condition_slug": unit.condition_slug,
                "condition": (
                    {
                        "voice": unit.condition.voice,
                        "rate": unit.condition.rate,
                        "noise": unit.condition.noise,
                    }
                    if unit.condition
                    else None
                ),
                "error": None,
            }
            try:
                wav = (
                    cache.ensure(item, unit.condition, tts)
                    if unit.mode == "audio" and unit.condition
                    else None
                )
                limiter.wait(unit.model_spec, model.min_interval_s)
                if unit.mode == "text":
                    answer = _answer_text_with_retry(model, item.question, cfg.max_retries)
                else:
                    answer = _ask_with_retry(model, unit, wav, cfg.max_retries)
                verdict = score_response(item, answer.text, judge)
                row.update(
                    {
                        "response": answer.text,
                        "output_modality": answer.output_modality,
                        "transcribed_by": answer.transcribed_by,
                        "correct": verdict.correct,
                        "score_method": verdict.method,
                        "t_first_s": round(answer.t_first_s, 3),
                        "t_total_s": round(answer.t_total_s, 3),
                    }
                )
            except ProviderError as exc:
                row["error"] = str(exc)[:500]
            sink.write(json.dumps(row) + "\n")
            sink.flush()

    _finalize_manifest(run_dir)
    return run_dir


def _answer_text_with_retry(model: VoiceModel, question: str, max_retries: int) -> VoiceAnswer:
    last: ProviderError | None = None
    for attempt in range(max_retries):
        try:
            return model.answer_text(question)
        except ProviderError as exc:
            last = exc
            time.sleep(min(2**attempt, 20))
    raise last if last else ProviderError("unreachable")


def _finalize_manifest(run_dir: Path) -> None:
    path = run_dir / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["finished_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(manifest, indent=1))
