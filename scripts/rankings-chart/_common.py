"""Shared config + data loading for the suite-v3 result cards.

``make_chart.py`` (the four-panel rankings card) predates this module and keeps
its own copy deliberately — it is the published card, and refactoring it is a
separate change from prototyping alternatives. New cards import from here.
"""

import json
from pathlib import Path

import matplotlib
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent


def register_fonts() -> None:
    """Load the brand faces (see CLAUDE.md) into matplotlib's font manager."""
    for w in (400, 500, 600, 700):
        font_manager.fontManager.addfont(str(HERE / f"geist-{w}.ttf"))
    for w in (400, 500, 600):
        font_manager.fontManager.addfont(str(HERE / f"chakra-{w}.ttf"))
    matplotlib.rcParams["font.family"] = "Geist"


SANS = "Geist"
BRAND = "Chakra Petch SemiBold"  # vulcanbench.com wordmark face
BRAND_MED = "Chakra Petch Medium"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a897f"
GRID = "#e7e6e1"

# Per-lab hues, matching the rankings card (see CLAUDE.md). Note for future
# edits: this set FAILS the generic categorical checks — xAI black and Moonshot
# slate are below the chroma floor, and OpenAI green vs Anthropic clay is
# dE 6.8 under protanopia. That is legal only because every mark is directly
# labelled with its model name; do not drop those labels to "clean up" a card.
LAB_COLOR = {
    "Anthropic": "#D97757",
    "OpenAI": "#10A37F",
    "xAI": "#0A0A0A",
    "Moonshot": "#44445E",
    "DeepSeek": "#5786FE",
    "Alibaba": "#9333EA",
}

NAME = {
    "xai:grok-4.6": ("Grok 4.6", "xAI"),
    "openai:grok-4.5": ("Grok 4.5", "xAI"),
    "openai:gpt-5.6-luna": ("GPT-5.6 Luna", "OpenAI"),
    "openai:gpt-5.6-sol": ("GPT-5.6 Sol", "OpenAI"),
    "openai:gpt-5.6-terra": ("GPT-5.6 Terra", "OpenAI"),
    "anthropic:claude-fable-5": ("Claude Fable 5", "Anthropic"),
    "anthropic:claude-haiku-4-5": ("Claude Haiku 4.5", "Anthropic"),
    "anthropic:claude-opus-5": ("Claude Opus 5", "Anthropic"),
    "deepseek:deepseek-v4-flash": ("DeepSeek V4-Flash", "DeepSeek"),
    "deepseek:deepseek-v4-pro": ("DeepSeek V4 Pro", "DeepSeek"),
    "kimi:kimi-k3": ("Kimi K3", "Moonshot"),
    "qwen:qwen3.8-max": ("Qwen3.8-Max", "Alibaba"),
}

EXCLUDED = {
    "anthropic:claude-opus-4-8",  # 5/23 task coverage
    "meta:muse-spark-1.2",  # OpenRouter-routed; needs its own column treatment
}
# Externally sourced (vulcanbench.com Report 10), not run in this checkout.
EXTERNAL = {"anthropic:claude-opus-5"}
N_TASKS_FULL = 23


def eff_display(model: str, eff: str) -> str:
    """Label an effort with the provider's own name for it."""
    if eff == "—":
        return "default"
    if eff == "extra-high":
        if model.startswith("deepseek:"):
            return "max"
        if model.startswith(("qwen:", "xai:")):
            return "xhigh"
    return eff


def load_rows() -> list[dict]:
    """Every (model, effort) column, minus deliberate exclusions."""
    with open(HERE / "v3_rankings.json") as f:
        rows = [r for r in json.load(f) if r["model"] not in EXCLUDED]
    unknown = {r["model"] for r in rows} - set(NAME)
    if unknown:
        raise SystemExit(f"models missing from NAME (add or exclude explicitly): {unknown}")
    return rows


def best_per_model(rows: list[dict]) -> list[dict]:
    """One point per model at its best-scoring effort.

    Ties break to the cheaper run, so a model is never flattered by an
    expensive coin-flip.
    """
    best: dict[str, dict] = {}
    for r in rows:
        cur = best.get(r["model"])
        cand = (r["pass1"], -r["cost"] / max(r["n_runs"], 1))
        if cur is None or cand > (cur["pass1"], -cur["cost"] / max(cur["n_runs"], 1)):
            best[r["model"]] = r

    pts = []
    for model, r in best.items():
        disp, lab = NAME[model]
        pts.append(
            dict(
                model=model,
                label=disp,
                lab=lab,
                effort=eff_display(model, r["effort"]),
                cost_per_run=r["cost"] / max(r["n_runs"], 1),
                pass1=r["pass1"] * 100,
                se=(r["se"] or 0) * 100,
                n_runs=r["n_runs"],
                n_tasks=r["n_tasks"],
                partial=r["n_tasks"] < N_TASKS_FULL,
                external=model in EXTERNAL,
            )
        )
    return sorted(pts, key=lambda p: -p["pass1"])
