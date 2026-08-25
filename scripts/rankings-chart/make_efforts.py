"""VulcanBench suite v3, effort-curve small multiples, 16:9.

The one thing the leaderboard and frontier cards cannot show: what happens
inside a model when you turn its reasoning effort up. Every panel shares one
y-scale, so the shapes are comparable at a glance; the x-axis is each
provider's own documented ladder, which is not a shared scale between them.

    python scripts/rankings-chart/make_efforts.py
"""

from itertools import pairwise

import matplotlib.pyplot as plt
from _common import (
    BRAND,
    BRAND_MED,
    HERE,
    INK,
    INK2,
    LAB_COLOR,
    MUTED,
    NAME,
    SANS,
    SURFACE,
    eff_display,
    load_rows,
    model_efforts,
    register_fonts,
)
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import FancyBboxPatch

register_fonts()

rows = load_rows()
by_model: dict[str, dict[str, dict]] = {}
for r in rows:
    if r["effort"] in model_efforts(r["model"]):
        by_model.setdefault(r["model"], {})[r["effort"]] = r
swept = {m: e for m, e in by_model.items() if len(e) >= 2}


def shape(model: str, effs: dict[str, dict]) -> str:
    """Classify the curve on the SAME rounded values the card prints.

    Classifying on raw floats labelled Grok 4.5 a dip on an 0.2-point wobble
    the reader cannot see (85.7 -> 85.5 -> 89.9 both print as 86, 86, 90).
    """
    ladder = [e for e in model_efforts(model) if e in effs]
    vals = [round(effs[e]["pass1"] * 100) for e in ladder]
    if all(b >= a for a, b in pairwise(vals)):
        return "rises"
    if all(b <= a for a, b in pairwise(vals)):
        return "falls"
    # Not monotone: a valley is not a peak, so name them separately.
    return "peaks" if vals.index(max(vals)) not in (0, len(vals) - 1) else "dips"


order = sorted(swept, key=lambda m: -max(e["pass1"] for e in swept[m].values()))
shapes = {m: shape(m, swept[m]) for m in order}
n_rises = sum(s == "rises" for s in shapes.values())

L = 0.062
fig = plt.figure(figsize=(16, 9), facecolor=SURFACE)

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
    "Eval Suite 3, effort curves",
    fontsize=26,
    color=MUTED,
    family=BRAND_MED,
    va="center",
)
fig.text(
    L,
    0.888,
    "23 frontier-hard software-engineering tasks from real merged OSS PRs  ·  "
    "pass@1 vs. each provider's own reasoning-effort ladder  ·  2026-08-25",
    fontsize=11.5,
    color=INK2,
    family=SANS,
)
fig.text(
    L,
    0.830,
    f"More reasoning is not reliably better, only {n_rises} of {len(order)} models improve all "
    "the way up.",
    fontsize=15,
    color=INK,
    family=BRAND_MED,
)
fig.text(
    L,
    0.792,
    "Panels share one y-scale, so the shapes compare directly. Each x-axis is that provider's "
    "documented enum, not a common scale, the same word means different compute at different labs.",
    fontsize=11.5,
    color=INK2,
    family=SANS,
)

# ---------------- Cards ----------------
Y0, Y1 = 50, 96
COLS, GUT_X, GUT_Y = 6, 0.0145, 0.105
CARD_W = (0.938 - L - (COLS - 1) * GUT_X) / COLS
CARD_H = 0.205
TOP = 0.509  # bottom edge of the top row; each card's two-line header sits above it
NAME_DY, SHAPE_DY = 0.038, 0.017

SHAPE_INK = {"rises": "#3f7d5c", "peaks": "#7a6a3f", "dips": "#6b5f7a", "falls": "#a8543c"}
partial_models: list[str] = []

for k, model in enumerate(order):
    effs = swept[model]
    disp, lab = NAME[model]
    c = LAB_COLOR[lab]
    ladder = model_efforts(model)
    present = [e for e in ladder if e in effs]

    col, row = k % COLS, k // COLS
    axc = fig.add_axes([L + col * (CARD_W + GUT_X), TOP - row * (CARD_H + GUT_Y), CARD_W, CARD_H])
    axc.set_facecolor("#f6f5f0")
    for side in ("top", "right", "left", "bottom"):
        axc.spines[side].set_visible(False)

    xs = [ladder.index(e) for e in present]
    ys = [effs[e]["pass1"] * 100 for e in present]
    ses = [(effs[e]["se"] or 0) * 100 for e in present]

    axc.plot(xs, ys, color=c, linewidth=2.0, zorder=3, solid_capstyle="round")
    axc.fill_between(xs, ys, Y0, color=c, alpha=0.10, zorder=2, linewidth=0)
    axc.errorbar(
        xs, ys, yerr=ses, fmt="none", ecolor=c, elinewidth=1.2, capsize=0, alpha=0.45, zorder=4
    )
    best_i = max(range(len(ys)), key=lambda i: ys[i])
    for i, (x, y) in enumerate(zip(xs, ys, strict=True)):
        axc.scatter(
            [x],
            [y],
            s=115 if i == best_i else 62,
            color=c,
            edgecolors=SURFACE,
            linewidths=2.0,
            zorder=5,
        )
        axc.annotate(
            f"{y:.0f}",
            (x, y + 3.6),
            fontsize=11.5 if i == best_i else 10.5,
            color=INK if i == best_i else INK2,
            family=SANS,
            fontweight="bold" if i == best_i else "normal",
            ha="center",
            va="bottom",
            zorder=6,
        )

    axc.set_xlim(-0.5, len(ladder) - 0.5)
    axc.set_ylim(Y0, Y1)
    axc.set_xticks(range(len(ladder)))
    axc.set_xticklabels(
        [
            {"low": "Low", "medium": "Med", "high": "High"}.get(
                e, eff_display(model, e).capitalize()
            )
            for e in ladder
        ],
        fontsize=9.5,
        color=INK2,
        family=SANS,
    )
    axc.grid(axis="y", color="#e2e0d8", linewidth=0.8, linestyle=(0, (1, 4)), zorder=0)
    axc.set_yticks(range(55, 96, 10))
    if col == 0:
        axc.set_yticklabels([f"{v}" for v in range(55, 96, 10)], fontsize=9, color=MUTED)
        axc.set_ylabel("pass@1 (%)", fontsize=10, color=INK2, family=SANS, labelpad=4)
    else:
        axc.set_yticklabels([])
    axc.tick_params(length=0, colors=MUTED)

    # Card header: lab chip + model, then the curve's shape in one word.
    partial = "*" if any(effs[e]["n_tasks"] < 23 for e in present) else ""
    if partial:
        partial_models.append(disp)
    ext = "†" if model == "anthropic:claude-opus-5" else ""
    fx = L + col * (CARD_W + GUT_X)
    fy = TOP - row * (CARD_H + GUT_Y) + CARD_H + NAME_DY
    fig.patches.append(
        FancyBboxPatch(
            (fx, fy - 0.008),
            0.0105,
            0.0155,
            boxstyle="round,pad=0,rounding_size=0.004",
            transform=fig.transFigure,
            facecolor=c,
            edgecolor="none",
            figure=fig,
        )
    )
    fig.text(
        fx + 0.0155,
        fy,
        f"{disp}{partial}{ext}",
        fontsize=11.5,
        color=INK,
        family=SANS,
        fontweight="bold",
        va="center",
    )
    sh = shapes[model]
    lo, hi = ys[0], ys[-1]
    # Low -> the top of the ladder, NOT low -> the peak: a model can rise to a
    # mid-ladder peak and still end below where it started.
    delta = f"{hi - lo:+.0f} pts vs. low" if len(ys) > 1 else ""
    fig.text(
        fx + 0.0155,
        fy - (NAME_DY - SHAPE_DY),
        f"{sh} · {delta}",
        fontsize=9.5,
        color=SHAPE_INK[sh],
        family=SANS,
        va="center",
    )

# ---------------- Legend ----------------
hx = L
for sh, word in (
    ("rises", "rises with effort"),
    ("peaks", "peaks mid-ladder"),
    ("dips", "dips mid-ladder"),
    ("falls", "falls with effort"),
):
    fig.patches.append(
        FancyBboxPatch(
            (hx, 0.1195),
            0.0105,
            0.0150,
            boxstyle="round,pad=0,rounding_size=0.004",
            transform=fig.transFigure,
            facecolor=SHAPE_INK[sh],
            edgecolor="none",
            figure=fig,
        )
    )
    n = sum(s == sh for s in shapes.values())
    fig.text(
        hx + 0.016,
        0.127,
        f"{word} ({n})",
        fontsize=11,
        color=INK2,
        family=SANS,
        va="center",
    )
    hx += 0.016 + 0.0077 * len(word) + 0.030

# ---------------- Footnote ----------------
fig.text(
    L,
    0.088,
    "Larger point = that model's best level. Whiskers are ±1 stderr; most within-model "
    "differences here are inside them, so read the shape, not single-point gaps.\n"
    "Effort names are each provider's own: DeepSeek is low/high/max, Qwen low/medium/xhigh "
    "(no 'high'), Grok 4.6 adds xhigh, GLM 5.3 is low/high/max, Muse Spark low/high/xhigh. "
    "Defaults: Grok high, Qwen xhigh, GLM max, Meta undocumented.\n"
    f"* partial task coverage at one or more levels ({', '.join(sorted(partial_models))}).   "
    "† Claude Opus 5 is from vulcanbench.com Report 10 (single runs, 2026-07-26), not run in "
    "this checkout.   github.com/morganlinton/VulcanBench",
    fontsize=9,
    color=MUTED,
    family=SANS,
    linespacing=1.42,
    va="top",
)

out = HERE / "vulcanbench_suite3_efforts.png"
fig.savefig(out, dpi=160, facecolor=SURFACE)
print(f"saved {out}  ({len(order)} swept models: {n_rises} rise)")
for m in order:
    effs = swept[m]
    ladder = [e for e in model_efforts(m) if e in effs]
    curve = " -> ".join(f"{effs[e]['pass1'] * 100:.0f}" for e in ladder)
    print(f"  {NAME[m][0]:20} {shapes[m]:6} {curve}")
