"""VulcanBench suite v3, one metric per 16:9 card, sized for X.

The four-panel rankings composite (``make_chart.py``) is 2560x4800; X scales
it down until the labels are unreadable. These cards split it: one metric per
image (2560x2080, 12 rows with room to breathe) with large horizontal labels, so a post can carry all of
them (rankings, speed, cost, plus the effort-curve card from
``make_efforts.py``) and each one reads at timeline size.

Each card shows one bar per model at its best-scoring effort level (ties
break to the cheaper run), the same rule as the composite's bar panels;
per-level detail lives in the effort-curve card.

    python scripts/rankings-chart/make_cards.py
"""

import matplotlib.pyplot as plt
import numpy as np
from _common import (
    BRAND,
    BRAND_MED,
    HERE,
    INK,
    INK2,
    LAB_COLOR,
    MUTED,
    SANS,
    SURFACE,
    load_rows,
    register_fonts,
    top_per_model,
)
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import FancyBboxPatch
from PIL import Image, ImageDraw

register_fonts()

DATE = "2026-08-13"
SUBTITLE = (
    "23 frontier-hard software-engineering tasks from real merged OSS PRs  ·  "
    "one bar per model at its best-scoring reasoning effort  ·  " + DATE
)
L = 0.062
W_IN, H_IN = 16.0, 13.0  # tall enough that 12 rows breathe; X crops the preview, not the file


def ytop(inches: float) -> float:
    """Figure-fraction y for a point ``inches`` below the top edge."""
    return 1 - inches / H_IN


LOGO = plt.imread(str(HERE / "vb_logo_rounded.png"))


def make_chip(lab: str, size: int = 128) -> np.ndarray:
    """Rounded lab-colored square with the white logo silhouette centred on it."""
    chip = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(chip).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * 0.22), fill=LAB_COLOR[lab]
    )
    logo = Image.open(HERE / f"logos/{lab}.png").convert("RGBA")
    box = int(size * 0.60)
    logo.thumbnail((box, box), Image.LANCZOS)
    chip.alpha_composite(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
    return np.asarray(chip)


CHIPS = {lab: make_chip(lab) for lab in LAB_COLOR}

pts = top_per_model(load_rows())


def header(fig, title: str, headline: str):
    fig.add_artist(
        AnnotationBbox(
            OffsetImage(
                LOGO, zoom=min(44 / LOGO.shape[1], 44 / LOGO.shape[0]), interpolation="lanczos"
            ),
            (L, ytop(0.62)),
            xycoords="figure fraction",
            frameon=False,
            box_alignment=(0, 0.5),
        )
    )
    fig.text(
        L + 0.040, ytop(0.62), "VulcanBench", fontsize=26, color=INK, family=BRAND, va="center"
    )
    fig.text(
        L + 0.228, ytop(0.62), title, fontsize=26, color=MUTED, family=BRAND_MED, va="center"
    )
    fig.text(L, ytop(1.22), SUBTITLE, fontsize=12.5, color=INK2, family=SANS, va="center")
    fig.text(L, ytop(1.85), headline, fontsize=17, color=INK, family=BRAND_MED, va="center")


def footnote(fig, text: str):
    fig.text(
        L,
        ytop(H_IN - 0.95),
        text,
        fontsize=11,
        color=MUTED,
        family=SANS,
        linespacing=1.45,
        va="top",
    )


def bar_card(
    *,
    ordered: list[dict],
    value,
    fmt,
    xmax: float,
    xticks: list[float],
    xlabel: str,
    title: str,
    headline: str,
    cols: list[tuple[str, callable]],
    note: str,
    out: str,
    err=None,
):
    """Horizontal bar card: chip + model name at left, value at bar end, a few
    text columns at right. Everything sized to read at timeline scale."""
    fig = plt.figure(figsize=(W_IN, H_IN), facecolor=SURFACE)
    ax_top, ax_bottom = 2.55, H_IN - 2.35  # inches from top
    ax = fig.add_axes([0.34, ytop(ax_bottom), 0.40, (ax_bottom - ax_top) / H_IN])
    ax.set_facecolor(SURFACE)
    header(fig, title, headline)

    n = len(ordered)
    ys = list(range(n))[::-1]
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.7, n - 0.3)
    ax.grid(axis="x", color="#ebe9e3", linewidth=1, zorder=0)
    ax.set_xticks(xticks)
    ax.set_xticklabels([fmt(v) for v in xticks], fontsize=13, color=MUTED, family=SANS)
    ax.tick_params(axis="x", length=0, pad=8)
    ax.set_yticks([])
    ax.set_xlabel(xlabel, fontsize=14, color=INK2, family=SANS, labelpad=14)
    for s in ax.spines.values():
        s.set_visible(False)

    for y, p in zip(ys, ordered, strict=True):
        color = LAB_COLOR[p["lab"]]
        v = value(p)
        ax.barh(y, v, height=0.46, color=color, zorder=3)
        if err is not None and err(p):
            ax.errorbar(
                v, y, xerr=err(p), fmt="none", ecolor="white", elinewidth=1.8, capsize=4,
                capthick=1.8, zorder=4, alpha=0.85,
            )
        # Value label at the bar end (outside whisker if present).
        vx = v + (err(p) if err is not None and err(p) else 0) + xmax * 0.012
        ax.text(
            vx, y, fmt(v), fontsize=19, color=INK, family=SANS, fontweight="bold",
            va="center", ha="left", zorder=5,
        )

        # Chip + "Name (effort)" at left.
        flag = "*" if p["partial"] else ("†" if p["external"] else "")
        ax.text(
            -0.02, y, f"{p['label']} ({p['effort']}){flag}",
            transform=ax.get_yaxis_transform(),
            fontsize=17, color=INK, family=SANS, fontweight="bold", ha="right", va="center",
        )
        ab = AnnotationBbox(
            OffsetImage(CHIPS[p["lab"]], zoom=0.27, interpolation="lanczos"),
            (-0.63, y),
            xycoords=ax.get_yaxis_transform(),
            frameon=False, box_alignment=(0.5, 0.5), annotation_clip=False,
        )
        ab.set_zorder(7)
        ax.add_artist(ab)

        # Right-hand text columns.
        for i, (_, col_fn) in enumerate(cols):
            ax.text(
                1.18 + 0.16 * i, y, col_fn(p), transform=ax.get_yaxis_transform(),
                fontsize=13.5, color=INK2, family=SANS, ha="right", va="center",
            )
    for i, (col_name, _) in enumerate(cols):
        ax.text(
            1.18 + 0.16 * i, n + 0.15, col_name, transform=ax.get_yaxis_transform(),
            fontsize=12, color=MUTED, family=SANS, ha="right", va="center",
        )

    footnote(fig, note)
    path = HERE / out
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    print(f"saved {path}")


COMMON_NOTE = (
    "* partial task coverage (Claude Fable 5 19/23 at low, safety-filter refusals; Kimi K3 19/23; "
    "Claude Haiku 4.5 21/23).   † Claude Opus 5 is from vulcanbench.com Report 10 (single runs, "
    "2026-07-26).\n"
    "Each model is shown at its best-scoring full-coverage effort level; every tested level is "
    "on the effort-curve card.   "
    "github.com/morganlinton/VulcanBench"
)

# ---------------- Card 1: pass@1 rankings ----------------
leader = pts[0]
within = sum(1 for p in pts if leader["pass1"] - p["pass1"] <= (leader["se"] ** 2 + p["se"] ** 2) ** 0.5)
bar_card(
    ordered=pts,
    value=lambda p: p["pass1"],
    fmt=lambda v: f"{v:.0f}",
    xmax=100,
    xticks=[0, 20, 40, 60, 80, 100],
    xlabel="pass@1 (%)",
    title="Eval Suite 3, model rankings",
    headline=f"Rankings by pass@1: {within} of {len(pts)} models sit within one stderr of the lead.",
    cols=[("$/task run", lambda p: f"${p['cost_per_run']:.2f}"), ("runs", lambda p: f"n={p['n_runs']}")],
    note="Whiskers are ±1 stderr. Cost = list-price API spend ÷ runs in the column.\n" + COMMON_NOTE,
    out="vulcanbench_suite3_card_rankings.png",
    err=lambda p: p["se"],
)

# ---------------- Card 2: speed ----------------
by_speed = sorted(pts, key=lambda p: p["minutes"])
tmax = max(p["minutes"] for p in by_speed)
tstep = 5 if tmax > 12 else 2
tticks = list(range(0, int(tmax) + tstep, tstep))
bar_card(
    ordered=by_speed,
    value=lambda p: p["minutes"],
    fmt=lambda v: f"{v:.1f}m" if 0 < v < 10 else f"{v:.0f}m",
    xmax=tmax * 1.14,
    xticks=tticks,
    xlabel="avg wall-clock minutes per task",
    title="Eval Suite 3, speed",
    headline=f"Speed: {by_speed[0]['label']} finishes a task in {by_speed[0]['minutes']:.1f} min, "
    f"{by_speed[-1]['label']} takes {by_speed[-1]['minutes']:.0f}.",
    cols=[("pass@1", lambda p: f"{p['pass1']:.0f}%"), ("runs", lambda p: f"n={p['n_runs']}")],
    note="Time = sandbox wall-clock per task run, averaged across the column's runs.\n" + COMMON_NOTE,
    out="vulcanbench_suite3_card_speed.png",
)

# ---------------- Card 3: cost ----------------
by_cost = sorted(pts, key=lambda p: p["cost_per_run"])
cmax = max(p["cost_per_run"] for p in by_cost)
cticks = [x * 0.5 for x in range(0, int(cmax / 0.5) + 2)]
bar_card(
    ordered=by_cost,
    value=lambda p: p["cost_per_run"],
    fmt=lambda v: f"${v:.2f}",
    xmax=cmax * 1.16,
    xticks=cticks,
    xlabel="avg API spend per task run ($, list prices)",
    title="Eval Suite 3, cost",
    headline=f"Cost: {by_cost[0]['label']} at \\${by_cost[0]['cost_per_run']:.2f}/task vs "
    f"{by_cost[-1]['label']} at \\${by_cost[-1]['cost_per_run']:.2f}, a "
    f"{by_cost[-1]['cost_per_run'] / by_cost[0]['cost_per_run']:.0f}x spread.",
    cols=[("pass@1", lambda p: f"{p['pass1']:.0f}%"), ("runs", lambda p: f"n={p['n_runs']}")],
    note="Cost = list-price API spend ÷ runs in the column; negotiated, cached, and batch rates "
    "differ.\n" + COMMON_NOTE,
    out="vulcanbench_suite3_card_cost.png",
)
