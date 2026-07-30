"""``vulcanbench voice`` sub-commands: render, run, report."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from harness.voice.audio import AudioCache, Condition
from harness.voice.items import load_items
from harness.voice.report import build_report, to_markdown
from harness.voice.runner import (
    DEFAULT_SEED,
    DEFAULT_SUBSET_N,
    JUDGE_DEFAULT,
    RunConfig,
    plan_units,
    run_suite,
    subset_ids,
)
from harness.voice.tts import DEFAULT_VOICES, PRIMARY_VOICE, get_tts

voice_app = typer.Typer(help="Voice Eval Suite: text-vs-audio delta measurement")
console = Console()

QUESTIONS = Path("tasks/voice-v1/questions.jsonl")
NOISE_DIR = Path("tasks/voice-v1/noise")
CACHE_DIR = Path("audio_cache/voice-v1")
OUT_DIR = Path("runs")


@voice_app.command()
def render(
    questions: Path = typer.Option(QUESTIONS, "--questions"),  # noqa: B008
    cache_dir: Path = typer.Option(CACHE_DIR, "--cache-dir"),  # noqa: B008
    noise_dir: Path = typer.Option(NOISE_DIR, "--noise-dir"),  # noqa: B008
    subset_n: int = typer.Option(DEFAULT_SUBSET_N, "--subset-n"),
    seed: int = typer.Option(DEFAULT_SEED, "--seed"),
    tts_provider: str = typer.Option("openai", "--tts"),
) -> None:
    """Pre-render the audio cache (idempotent; reuses fresh files)."""
    items = load_items(questions)
    cache = AudioCache(cache_dir, noise_dir=noise_dir)
    tts = get_tts(tts_provider)
    sub = set(subset_ids(items, subset_n, seed))
    rendered = reused = 0
    conditions_full = [Condition(v, "normal", "clean") for v in DEFAULT_VOICES]
    conditions_sub = [
        Condition(PRIMARY_VOICE, "fast", "clean"),
        Condition(PRIMARY_VOICE, "normal", "noise10db"),
    ]
    for it in items:
        conds = list(conditions_full) + (conditions_sub if it.id in sub else [])
        for cond in conds:
            if cache.is_fresh(it, cond):
                reused += 1
            else:
                cache.ensure(it, cond, tts)
                rendered += 1
    console.print(f"[green]rendered {rendered}, reused {reused}[/green] → {cache_dir}")


@voice_app.command()
def run(
    models: str = typer.Option(
        ...,
        "--models",
        "-m",
        help="Comma-separated adapters, e.g. openai-realtime,gemini-live,qwen-omni "
        "(optionally adapter:model)",
    ),
    questions: Path = typer.Option(QUESTIONS, "--questions"),  # noqa: B008
    out_dir: Path = typer.Option(OUT_DIR, "--output-dir", "-o"),  # noqa: B008
    cache_dir: Path = typer.Option(CACHE_DIR, "--cache-dir"),  # noqa: B008
    noise_dir: Path = typer.Option(NOISE_DIR, "--noise-dir"),  # noqa: B008
    judge_model: str = typer.Option(JUDGE_DEFAULT, "--judge-model"),
    subset_n: int = typer.Option(DEFAULT_SUBSET_N, "--subset-n"),
    seed: int = typer.Option(DEFAULT_SEED, "--seed"),
    dry_run: bool = typer.Option(False, "--dry-run", help="First 5 items, one voice, clean only"),
    run_id: str | None = typer.Option(None, "--run-id", help="Resume an existing run directory"),
) -> None:
    """Run the suite (resumable: re-invoke with --run-id to skip finished units)."""
    cfg = RunConfig(
        models=[m.strip() for m in models.split(",") if m.strip()],
        questions_path=questions,
        out_dir=out_dir,
        cache_dir=cache_dir,
        noise_dir=noise_dir,
        subset_n=subset_n,
        seed=seed,
        dry_run=dry_run,
        judge_model=judge_model,
    )
    if run_id:
        cfg.run_id = run_id
    units = plan_units(cfg, load_items(questions))
    console.print(
        f"run [bold]{cfg.run_id}[/bold]: {len(units)} planned units "
        f"({'dry-run, ' if dry_run else ''}judge {judge_model})"
    )
    run_dir = run_suite(cfg)
    console.print(f"[green]done[/green] → {run_dir}/results.jsonl")


@voice_app.command()
def report(
    run_dir: Path = typer.Argument(..., help="runs/voice-<id> directory"),  # noqa: B008
    output: Path | None = typer.Option(None, "--output", "-o"),  # noqa: B008
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Aggregate a run into voice-tax tables (markdown by default)."""
    data = build_report(run_dir)
    rendered = json.dumps(data, indent=1) if as_json else to_markdown(data)
    if output:
        output.write_text(rendered)
        console.print(f"[green]wrote[/green] {output}")
    else:
        console.print(rendered)
