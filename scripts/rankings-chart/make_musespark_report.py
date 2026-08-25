"""Report No. 19 chart: Muse Spark 1.2 across the effort knob.

Two panels in VulcanBench branding:
  1. Effort curve, pass@1 by effort (inverted: low leads xhigh by 34.8 pts).
  2. Failure composition, solved / wrong / unfinished per effort (higher
     effort converts wrong answers into wall-clock timeouts).

Reads docs/results/v3-musespark-2026-08/v3-musespark-2026-08.json and writes
vulcanbench-v3-musespark-chart.png next to it.

Usage: python scripts/rankings-chart/make_musespark_report.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import BRAND, BRAND_MED, GRID, INK, INK2, MUTED, SANS, SURFACE, register_fonts

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent.parent / "docs" / "results" / "v3-musespark-2026-08"
DATA = REPORT / "v3-musespark-2026-08.json"
OUT = REPORT / "vulcanbench-v3-musespark-chart.png"
LOGO = HERE / "vb_logo_rounded.png"

LINE = "#0866ff"  # Meta blue
SOLVED = "#10b981"
WRONG = "#c9a24a"
TIMEOUT = "#c2554d"
EFFORTS = ["low", "high", "extra-high"]
EFF_LABEL = {"low": "low", "high": "high", "extra-high": "xhigh"}


def main() -> None:  # noqa: PLR0915 (single linear chart layout)
    register_fonts()
    cols = json.loads(DATA.read_text())["efforts"]

    fig = plt.figure(figsize=(16, 9), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    gs = fig.add_gridspec(
        2,
        2,
        height_ratios=[0.16, 1.0],
        hspace=0.28,
        wspace=0.18,
        left=0.065,
        right=0.965,
        top=0.96,
        bottom=0.11,
    )

    # ---- header ----
    hax = fig.add_subplot(gs[0, :])
    hax.axis("off")
    try:
        logo = plt.imread(str(LOGO))
        hax.imshow(
            logo, extent=(0.0, 0.052, 0.05, 0.95), transform=hax.transAxes, aspect="auto", zorder=5
        )
        tx = 0.066
    except Exception:
        tx = 0.0
    hax.text(
        tx,
        0.62,
        "VulcanBench",
        family=BRAND,
        fontsize=26,
        color=INK,
        va="center",
        transform=hax.transAxes,
    )
    hax.text(
        tx,
        0.14,
        "Report No. 19   ·   Muse Spark 1.2 across the effort knob   ·   suite v3   ·   "
        "23 tasks   ·   1 attempt/cell",
        family=BRAND_MED,
        fontsize=12.5,
        color=INK2,
        va="center",
        transform=hax.transAxes,
    )
    hax.text(
        0.999,
        0.62,
        "pass@1 by reasoning effort",
        family=SANS,
        fontsize=13,
        color=MUTED,
        va="center",
        ha="right",
        transform=hax.transAxes,
    )

    # ---- panel 1: effort curve ----
    ax = fig.add_subplot(gs[1, 0])
    _style(ax)
    x = list(range(3))
    y = [cols[e]["pass1"] for e in EFFORTS]
    ax.plot(x, y, "-o", color=LINE, lw=3.2, ms=11, zorder=4)
    for xi, yi in zip(x, y, strict=True):
        ax.text(
            xi, yi + 2.4, f"{yi:.1f}%", ha="center", family=BRAND_MED, fontsize=13.5, color=LINE
        )
    for xi, e in zip(x, EFFORTS, strict=True):
        ax.text(
            xi,
            y[xi] - 5.2,
            f"${cols[e]['cost_per_solved']:.2f}/solved",
            ha="center",
            family=SANS,
            fontsize=10.5,
            color=MUTED,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([EFF_LABEL[e] for e in EFFORTS], family=SANS, fontsize=13, color=INK2)
    ax.set_ylim(40, 97)
    ax.set_yticks([50, 60, 70, 80, 90])
    ax.set_yticklabels(["50", "60", "70", "80", "90"], family=SANS, fontsize=11, color=MUTED)
    ax.set_ylabel("pass@1  (%)", family=SANS, fontsize=12, color=INK2)
    ax.set_xlabel("reasoning effort", family=SANS, fontsize=12, color=INK2)
    ax.set_title(
        "The knob runs backwards: -34.8 pts from low to xhigh",
        family=BRAND_MED,
        fontsize=15,
        color=INK,
        pad=12,
        loc="left",
    )
    ax.annotate(
        "",
        xy=(2, y[0]),
        xytext=(2, y[2]),
        arrowprops=dict(arrowstyle="<->", color=MUTED, lw=1.3),
    )
    ax.text(
        1.86,
        (y[0] + y[2]) / 2,
        f"-{y[0] - y[2]:.1f} pts",
        ha="right",
        va="center",
        family=BRAND_MED,
        fontsize=12,
        color=INK2,
    )

    # ---- panel 2: failure composition ----
    ax2 = fig.add_subplot(gs[1, 1])
    _style(ax2)
    xs = list(range(3))
    for pos, e in zip(xs, EFFORTS, strict=True):
        s, w, t = cols[e]["solved"], cols[e]["wrong"], cols[e]["timeout"]
        ax2.bar(pos, s, 0.6, color=SOLVED, zorder=3)
        ax2.bar(pos, w, 0.6, bottom=s, color=WRONG, zorder=3)
        ax2.bar(pos, t, 0.6, bottom=s + w, color=TIMEOUT, zorder=3)
        ax2.text(
            pos,
            s - 0.8,
            f"{s}",
            ha="center",
            va="top",
            family=BRAND_MED,
            fontsize=12.5,
            color="#ffffff",
        )
        if t:
            ax2.text(
                pos,
                s + w + t + 0.35,
                f"{t} timeouts",
                ha="center",
                family=SANS,
                fontsize=10.5,
                color=TIMEOUT,
            )
    ax2.set_xticks(xs)
    ax2.set_xticklabels([EFF_LABEL[e] for e in EFFORTS], family=SANS, fontsize=13, color=INK2)
    ax2.set_xlabel("reasoning effort", family=SANS, fontsize=12, color=INK2)
    ax2.set_ylim(0, 25.5)
    ax2.set_yticks([0, 5, 10, 15, 20, 23])
    ax2.set_yticklabels(["0", "5", "10", "15", "20", "23"], family=SANS, fontsize=11, color=MUTED)
    ax2.set_ylabel("runs (of 23)", family=SANS, fontsize=12, color=INK2)
    ax2.set_title(
        "Effort converts wrong answers into timeouts",
        family=BRAND_MED,
        fontsize=15,
        color=INK,
        pad=26,
        loc="left",
    )
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=SOLVED),
        plt.Rectangle((0, 0), 1, 1, color=WRONG),
        plt.Rectangle((0, 0), 1, 1, color=TIMEOUT),
    ]
    ax2.legend(
        handles,
        ["solved", "wrong answer", "unfinished (timeout)"],
        loc="lower right",
        bbox_to_anchor=(1.0, 1.005),
        ncol=3,
        frameon=False,
        fontsize=11,
        handlelength=1.2,
        columnspacing=1.4,
    )

    fig.text(
        0.065,
        0.035,
        "meta:muse-spark-1.2, 23 real post-cutoff PRs, hidden-test grading in a "
        "network-isolated Docker sandbox. One attempt per task per effort; 56.36 USD "
        "total; 0 contaminated runs.",
        family=SANS,
        fontsize=10,
        color=MUTED,
        va="center",
    )
    fig.savefig(OUT, facecolor=SURFACE)
    print(f"wrote {OUT}")


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, lw=1)


if __name__ == "__main__":
    main()
