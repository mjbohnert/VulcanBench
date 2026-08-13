"""VulcanBench suite v3 — cost/accuracy frontier, one shareable 16:9 card.

Why this exists: on suite v3, pass@1 barely separates the field (30 of 33
model x effort columns sit within 1 stderr of the leader) while cost per task
run spans 13x. A ranked bar chart therefore sorts noise; this plots the
tradeoff that does separate, and marks the Pareto frontier.

One point per model at its best-scoring effort level. Frontier points are
emphasised; dominated points recede. Direct labels on every point are
mandatory, not decorative: with six lab hues on an all-pairs form (and two of
them brand-mandated near-neutrals), color alone cannot carry identity.

    python scripts/rankings-chart/make_frontier.py
"""

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent

for w in (400, 500, 600, 700):
    font_manager.fontManager.addfont(str(HERE / f"geist-{w}.ttf"))
for w in (400, 500, 600):
    font_manager.fontManager.addfont(str(HERE / f"chakra-{w}.ttf"))
matplotlib.rcParams["font.family"] = "Geist"
SANS = "Geist"
BRAND = "Chakra Petch SemiBold"
BRAND_MED = "Chakra Petch Medium"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a897f"
GRID = "#e7e6e1"

# Same per-lab hues as the rankings card (see CLAUDE.md). Note for future
# edits: this set FAILS the generic categorical checks — xAI black and
# Moonshot slate are below the chroma floor, and OpenAI green vs Anthropic
# clay is ΔE 6.8 under protanopia. That is legal only because every point is
# directly labelled; do not remove the labels to "clean up" the chart.
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


with open(HERE / "v3_rankings.json") as f:
    all_rows = [r for r in json.load(f) if r["model"] not in EXCLUDED]

unknown = {r["model"] for r in all_rows} - set(NAME)
if unknown:
    raise SystemExit(f"models missing from NAME (add or exclude explicitly): {unknown}")

# One point per model: its best-scoring effort. Ties break to the cheaper run,
# so a model is never flattered by an expensive coin-flip.
best: dict[str, dict] = {}
for r in all_rows:
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
            x=r["cost"] / max(r["n_runs"], 1),
            y=r["pass1"] * 100,
            se=(r["se"] or 0) * 100,
            n_runs=r["n_runs"],
            partial=r["n_tasks"] < N_TASKS_FULL,
            external=model in EXTERNAL,
        )
    )

# Pareto frontier: no other point is both cheaper AND at least as accurate.
for p in pts:
    p["frontier"] = not any(
        q is not p
        and q["x"] <= p["x"]
        and q["y"] >= p["y"]
        and (q["x"], -q["y"]) != (p["x"], -p["y"])
        for q in pts
    )
front = sorted([p for p in pts if p["frontier"]], key=lambda p: p["x"])

L = 0.062  # shared left margin
fig = plt.figure(figsize=(16, 9), facecolor=SURFACE)
ax = fig.add_axes([L, 0.225, 0.925, 0.525])
ax.set_facecolor(SURFACE)

# ---------------- Header ----------------
logo = plt.imread(str(HERE / "vb_logo_rounded.png"))
fig.add_artist(
    AnnotationBbox(
        OffsetImage(
            logo, zoom=min(44 / logo.shape[1], 44 / logo.shape[0]), interpolation="lanczos"
        ),
        (L, 0.947),
        xycoords="figure fraction",
        frameon=False,
        box_alignment=(0, 0.5),
    )
)
fig.text(L + 0.040, 0.947, "VulcanBench", fontsize=26, color=INK, family=BRAND, va="center")
fig.text(
    L + 0.228,
    0.947,
    "Eval Suite 3 — cost vs. accuracy",
    fontsize=26,
    color=MUTED,
    family=BRAND_MED,
    va="center",
)
fig.text(
    L,
    0.884,
    "23 frontier-hard software-engineering tasks from real merged OSS PRs  ·  "
    "each model at its best-scoring reasoning effort  ·  2026-08-13",
    fontsize=11.5,
    color=INK2,
    family=SANS,
)
fig.text(
    L,
    0.826,
    "Accuracy is nearly flat across the field — cost is not.",
    fontsize=15,
    color=INK,
    family=BRAND_MED,
)
fig.text(
    L,
    0.788,
    "30 of 33 model/effort columns sit within 1 stderr of the leader, while cost per task "
    "run spans 13x. The line marks the frontier: no model is both cheaper and better.",
    fontsize=11.5,
    color=INK2,
    family=SANS,
)

# ---------------- Axes ----------------
ax.set_xscale("log")
# Right of ~$0.9 is deliberate empty space: eight of twelve models crowd
# $0.42-$0.85, so their labels live in a leader-lined column out there rather
# than fighting each other on top of the points.
ax.set_xlim(0.048, 3.4)
LABEL_COL_X = 1.05
ax.set_ylim(66, 96)
ax.grid(axis="both", color=GRID, linewidth=0.9, linestyle=(0, (1, 4)), zorder=0)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
for side in ("left", "bottom"):
    ax.spines[side].set_color(GRID)
ax.set_xticks([0.05, 0.1, 0.2, 0.4, 0.8])
ax.set_xticklabels(
    ["$0.05", "$0.10", "$0.20", "$0.40", "$0.80"], fontsize=11, color=INK2, family=SANS
)
ax.minorticks_off()
ax.set_yticks(range(70, 96, 5))
ax.set_yticklabels([f"{v}" for v in range(70, 96, 5)], fontsize=11, color=INK2, family=SANS)
ax.tick_params(length=0, colors=MUTED)
ax.set_xlabel(
    "average cost per task run (USD, log scale — list API prices)",
    fontsize=12,
    color=INK2,
    family=SANS,
    labelpad=10,
)
ax.set_ylabel("pass@1 (%)", fontsize=12, color=INK2, family=SANS, labelpad=8)

# ---------------- Frontier ----------------
# Staircase: from each frontier point, right at its accuracy until the next
# one improves on it. Reads as "everything above-left of this is unoccupied".
step_x, step_y = [], []
for i, p in enumerate(front):
    step_x.append(p["x"])
    step_y.append(p["y"])
    if i + 1 < len(front):
        step_x.append(front[i + 1]["x"])
        step_y.append(p["y"])
# Line only, no shaded region: filling under the staircase drew a hard vertical
# edge at the last frontier point that read as a second axis.
ax.plot(step_x, step_y, color=INK, linewidth=2.0, zorder=2, solid_capstyle="round")
ax.text(
    front[0]["x"] * 1.06,
    front[0]["y"] - 3.6,
    "cost/accuracy frontier",
    fontsize=10.5,
    color=INK2,
    family=SANS,
    style="italic",
)

# ---------------- Points ----------------
INLINE_CUTOFF = 0.30  # cheap, well-separated models label in place
# Terra and V4 Pro label downward: the frontier line runs just above them.
# V4-Flash clears the frontier line it sits on; the other two label downward
# because the line runs just above them.
INLINE_NUDGE = {"DeepSeek V4-Flash": 3.7, "DeepSeek V4 Pro": -2.8, "GPT-5.6 Terra": -2.8}

for p in pts:
    c = LAB_COLOR[p["lab"]]
    on = p["frontier"]
    # Whiskers stay thin and translucent: they must be readable as overlap
    # without out-inking the points they belong to.
    ax.errorbar(
        p["x"],
        p["y"],
        yerr=p["se"],
        fmt="none",
        ecolor=c,
        elinewidth=1.3,
        capsize=0,
        alpha=0.55 if on else 0.28,
        zorder=3,
    )
    ax.scatter(
        [p["x"]],
        [p["y"]],
        s=230 if on else 115,
        color=c,
        edgecolors=SURFACE,  # 2px surface ring keeps overlapping marks readable
        linewidths=2.2,
        alpha=1.0 if on else 0.62,
        zorder=5 if on else 4,
    )


def draw_label(p: dict, lx: float, ly: float, ha: str) -> None:
    star = "*" if p["partial"] else ""
    ext = "†" if p["external"] else ""
    on = p["frontier"]
    ax.annotate(
        f"{p['label']}{star}{ext}",
        (lx, ly),
        fontsize=12.5 if on else 11.5,
        color=INK if on else INK2,
        family=SANS,
        fontweight="bold" if on else "normal",
        ha=ha,
        va="center",
        zorder=7,
    )
    ax.annotate(
        f"{p['effort']} · {p['y']:.0f}% · ${p['x']:.3f} · n={p['n_runs']}",
        (lx, ly - 1.5),
        fontsize=9.5,
        color=MUTED,
        family=SANS,
        ha=ha,
        va="center",
        zorder=7,
    )


inline = [p for p in pts if p["x"] < INLINE_CUTOFF]
column = sorted((p for p in pts if p["x"] >= INLINE_CUTOFF), key=lambda p: -p["y"])

for p in inline:
    draw_label(p, p["x"] * (10**0.055), p["y"] + INLINE_NUDGE.get(p["label"], 1.2), "left")

# Evenly spaced label column + leader lines for the crowded right-hand cluster.
# Span the full plot height so every member fits; leaders stay faint because
# they are wayfinding, not data.
top, bottom = 94.0, 69.2  # bottom leaves room for the second label line
gap = (top - bottom) / max(len(column) - 1, 1)
for i, p in enumerate(column):
    ly = top - i * gap
    ax.annotate(
        "",
        xy=(p["x"] * (10**0.02), p["y"]),
        xytext=(LABEL_COL_X * (10**-0.012), ly),
        arrowprops=dict(
            arrowstyle="-",
            color=LAB_COLOR[p["lab"]],
            linewidth=0.9,
            alpha=0.32,
            shrinkA=2,
            shrinkB=6,
        ),
        zorder=2,
    )
    draw_label(p, LABEL_COL_X, ly, "left")

# ---------------- Legend ----------------
seen = [lab for lab in LAB_COLOR if any(p["lab"] == lab for p in pts)]
hx = L
for lab in seen:
    fig.patches.append(
        FancyBboxPatch(
            (hx, 0.1275),
            0.0115,
            0.0165,
            boxstyle="round,pad=0,rounding_size=0.004",
            transform=fig.transFigure,
            facecolor=LAB_COLOR[lab],
            edgecolor="none",
            figure=fig,
        )
    )
    fig.text(hx + 0.017, 0.1358, lab, fontsize=11, color=INK2, family=SANS, va="center")
    hx += 0.017 + 0.0079 * len(lab) + 0.020
fig.text(
    hx + 0.006,
    0.1358,
    "larger, solid points are on the frontier",
    fontsize=10.5,
    color=MUTED,
    family=SANS,
    va="center",
)

# ---------------- Footnote ----------------
fig.text(
    L,
    0.093,
    "Each model appears once, at its best-scoring effort level (labelled); ties break to the "
    "cheaper run. Whiskers are ±1 stderr on pass@1 — they overlap across nearly the whole field, "
    "which is the point.\n"
    "* partial task coverage: Claude Fable 5 19/23 (safety-filter refusals), Kimi K3 19/23, "
    "Claude Haiku 4.5 21/23, GPT-5.6 Luna 7/23.   † Claude Opus 5 is from vulcanbench.com "
    "Report 10 (single runs, 2026-07-26), not run in this checkout.\n"
    "Cost is total spend at list API prices ÷ runs in that column; negotiated, cached-input, "
    "and batch rates all differ. Full effort sweeps and per-level detail: the suite-3 rankings "
    "card.   github.com/morganlinton/VulcanBench",
    fontsize=9,
    color=MUTED,
    family=SANS,
    linespacing=1.5,
    va="top",
)

out = HERE / "vulcanbench_suite3_frontier.png"
fig.savefig(out, dpi=160, facecolor=SURFACE)
print(f"saved {out}  ({len(pts)} models, {len(front)} on frontier)")
for p in sorted(pts, key=lambda p: p["x"]):
    mark = "◆ frontier" if p["frontier"] else "  dominated"
    print(f"  {mark}  {p['label']:20} {p['effort']:10} {p['y']:5.1f}%  ${p['x']:.3f}/task")
