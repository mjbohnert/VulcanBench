"""VulcanBench suite v3, one-row-per-model leaderboard, 16:9.

The published rankings card ranks 33 model/effort columns. This ranks the 12
models instead, each at its best-scoring effort, and marks the statistical tie
band: models whose gap to the leader is smaller than the pair's combined
+/-1 stderr sit in a shaded region and carry no meaningful rank against
each other.

Bars start at zero (a truncated bar baseline exaggerates differences), which
makes the flatness visible: that flatness is the finding, not a rendering
problem. Cost rides alongside as text, never as a second encoded axis.

    python scripts/rankings-chart/make_rows.py
"""

import matplotlib.pyplot as plt
from _common import (
    BRAND,
    BRAND_MED,
    GRID,
    HERE,
    INK,
    INK2,
    LAB_COLOR,
    MUTED,
    SANS,
    SURFACE,
    best_per_model,
    load_rows,
    register_fonts,
)
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import FancyBboxPatch, Rectangle

register_fonts()

pts = best_per_model(load_rows())
leader = pts[0]
# Tie band: the gap to the leader is smaller than the two scores' combined
# uncertainty, sqrt(se_leader^2 + se^2). "Do the error bars overlap?" is the
# tempting test and it is wrong in the conservative direction, it calls the
# entire field tied here, including models 16 points back.
for p in pts:
    combined = (leader["se"] ** 2 + p["se"] ** 2) ** 0.5
    p["tied"] = (leader["pass1"] - p["pass1"]) <= combined
n_tied = sum(p["tied"] for p in pts)

L = 0.062
fig = plt.figure(figsize=(16, 9), facecolor=SURFACE)
ax = fig.add_axes([0.185, 0.215, 0.455, 0.525])
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
    "Eval Suite 3, model leaderboard",
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
    0.822,
    f"First place is a crowd, {n_tied} of {len(pts)} models sit within the noise of the lead.",
    fontsize=15,
    color=INK,
    family=BRAND_MED,
)
fig.text(
    L,
    0.784,
    "Shaded band = the gap to the leader is smaller than the pair's combined ±1 stderr. Ranking "
    "within it is not supported by the data; cost is where these models actually differ.",
    fontsize=11.5,
    color=INK2,
    family=SANS,
)

# ---------------- Bars ----------------
# Table columns, in bar-axis data units (the plot itself only spans 0-100).
COL_VALUE, COL_SE, COL_EFFORT, COL_COST, COL_RUNS = 108, 122, 128, 154, 165

ys = list(range(len(pts)))[::-1]
ax.set_xlim(0, 100)
ax.set_ylim(-0.85, len(pts) - 0.15)

# The tie band spans the full plot height behind the rows it covers.
band_top = ys[0] + 0.62
band_bottom = ys[n_tied - 1] - 0.42
ax.add_patch(
    Rectangle(
        (0, band_bottom),
        100,
        band_top - band_bottom,
        facecolor="#f0efe9",
        edgecolor="none",
        zorder=0,
    )
)
ax.text(
    1.6,
    band_bottom + 0.28,
    f"within noise of the lead, top {n_tied} of {len(pts)}",
    fontsize=10.5,
    color=MUTED,
    family=SANS,
    style="italic",
    va="bottom",
    zorder=2,
)

for y, p in zip(ys, pts, strict=True):
    c = LAB_COLOR[p["lab"]]
    ax.add_patch(
        FancyBboxPatch(
            (0, y - 0.27),
            p["pass1"],
            0.54,
            boxstyle="round,pad=0,rounding_size=0.26",
            mutation_aspect=0.06,  # keeps the 4px round only on the data end
            facecolor=c,
            edgecolor="none",
            alpha=1.0 if p["tied"] else 0.62,
            zorder=3,
        )
    )
    ax.errorbar(
        p["pass1"],
        y,
        xerr=p["se"],
        fmt="none",
        ecolor=SURFACE,
        elinewidth=1.8,
        capsize=3.5,
        capthick=1.8,
        alpha=0.9,
        zorder=4,
    )
    star = "*" if p["partial"] else ""
    ext = "†" if p["external"] else ""
    ax.text(
        -1.6,
        y,
        f"{p['label']}{star}{ext}",
        fontsize=12.5,
        color=INK,
        family=SANS,
        ha="right",
        va="center",
    )
    # Every number lives in the table zone right of the plot. Labels beside the
    # bar ends collided with the whisker caps, and cost as a second encoded
    # axis would invent a relationship the reader cannot verify.
    for x, txt, size, color, weight in (
        (COL_VALUE, f"{p['pass1']:.0f}", 12.5, INK, "bold"),
        (COL_SE, f"±{p['se']:.1f}", 10, MUTED, "normal"),
        (COL_EFFORT, p["effort"], 11, INK2, "normal"),
        (COL_COST, f"${p['cost_per_run']:.3f}", 11, INK2, "normal"),
        (COL_RUNS, f"n={p['n_runs']}", 11, MUTED, "normal"),
    ):
        ax.text(
            x,
            y,
            txt,
            fontsize=size,
            color=color,
            family=SANS,
            fontweight=weight,
            ha="left" if x == COL_EFFORT else "right",
            va="center",
        )

for col, x, ha in (
    ("pass@1", COL_VALUE, "right"),
    ("effort", COL_EFFORT, "left"),
    ("$/task run", COL_COST, "right"),
    ("runs", COL_RUNS, "right"),
):
    ax.text(
        x,
        len(pts) - 0.55,
        col,
        fontsize=10.5,
        color=MUTED,
        family=SANS,
        ha=ha,
        va="center",
    )

ax.set_xticks(range(0, 101, 20))
ax.set_xticklabels([f"{v}" for v in range(0, 101, 20)], fontsize=11, color=INK2, family=SANS)
ax.set_yticks([])
ax.grid(axis="x", color=GRID, linewidth=0.9, linestyle=(0, (1, 4)), zorder=1)
ax.set_axisbelow(False)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.tick_params(length=0, colors=MUTED)
ax.set_xlabel("pass@1 (%)", fontsize=12, color=INK2, family=SANS, labelpad=10)

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
    "faded bars fall outside the tie band",
    fontsize=10.5,
    color=MUTED,
    family=SANS,
    va="center",
)

# ---------------- Footnote ----------------
fig.text(
    L,
    0.104,
    "Each model appears once, at its best-scoring effort level; ties break to the cheaper run. "
    "Bars start at zero, the field really is this tightly packed. Whiskers are ±1 stderr; the "
    "tie test compares the gap to the leader against the pair's\n"
    "combined ±1 stderr, at ±2, every model in the field ties.\n"
    "* partial task coverage: Claude Fable 5 19/23 (safety-filter refusals), Kimi K3 19/23, "
    "Claude Haiku 4.5 21/23, GPT-5.6 Luna 7/23.   † Claude Opus 5 is from vulcanbench.com "
    "Report 10 (single runs, 2026-07-26), not run in this checkout.\n"
    "Cost is total spend at list API prices ÷ runs in that column; negotiated, cached-input, "
    "and batch rates all differ. Full effort sweeps and per-level detail: the suite-3 rankings "
    "card.   github.com/morganlinton/VulcanBench",
    fontsize=9,
    color=MUTED,
    family=SANS,
    linespacing=1.42,
    va="top",
)

out = HERE / "vulcanbench_suite3_rows.png"
fig.savefig(out, dpi=160, facecolor=SURFACE)
print(f"saved {out}  ({len(pts)} models, {n_tied} in the tie band)")
for p in pts:
    print(
        f"  {'tie ' if p['tied'] else '    '} {p['label']:20} {p['effort']:10} "
        f"{p['pass1']:5.1f}% ±{p['se']:.1f}  ${p['cost_per_run']:.3f}/task"
    )
