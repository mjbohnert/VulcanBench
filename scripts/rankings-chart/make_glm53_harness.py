"""Report No. 18 chart: GLM 5.3 raw API vs the ZCode harness.

Two panels in VulcanBench branding:
  1. Effort curves, pass@1 by effort for each harness (inverted vs flat).
  2. Failure composition, solved / wrong / unfinished per harness x effort
     (the raw API fails by timeout, ZCode by wrong answer).

Reads docs/results/v3-glm53-2026-08/v3-glm53-2026-08.json and writes
vulcanbench-v3-glm53-harness.png next to it.

Usage: python scripts/rankings-chart/make_glm53_harness.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from _common import BRAND, BRAND_MED, GRID, INK, INK2, MUTED, SANS, SURFACE, register_fonts

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent.parent / "docs" / "results" / "v3-glm53-2026-08"
DATA = REPORT / "v3-glm53-2026-08.json"
OUT = REPORT / "vulcanbench-v3-glm53-harness.png"
LOGO = HERE / "vb_logo_rounded.png"

API_COLOR = INK  # raw API, VulcanBench uniform loop
ZC_COLOR = "#10b981"  # ZCode harness (emerald, the dashboard accent)
SOLVED = "#10b981"
WRONG = "#c9a24a"
TIMEOUT = "#c2554d"
EFFORTS = ["low", "high", "extra-high"]
EFF_LABEL = {"low": "low", "high": "high", "extra-high": "max"}


def main() -> None:
    register_fonts()
    data = json.loads(DATA.read_text())
    api, zc = data["api"], data["zcode"]
    n = data["n_tasks"]

    fig = plt.figure(figsize=(16, 9), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    # Header band + two panels.
    gs = fig.add_gridspec(
        2, 2, height_ratios=[0.16, 1.0], hspace=0.28, wspace=0.18,
        left=0.065, right=0.965, top=0.96, bottom=0.11,
    )

    # ---- header ----
    hax = fig.add_subplot(gs[0, :])
    hax.axis("off")
    try:
        logo = plt.imread(str(LOGO))
        hax.imshow(logo, extent=(0.0, 0.052, 0.05, 0.95), transform=hax.transAxes, aspect="auto", zorder=5)
        tx = 0.066
    except Exception:
        tx = 0.0
    hax.text(tx, 0.62, "VulcanBench", family=BRAND, fontsize=26, color=INK, va="center")
    hax.text(
        tx, 0.14,
        "Report No. 18   ·   GLM 5.3: model versus harness   ·   suite v3   ·   23 tasks   ·   1 attempt/cell",
        family=BRAND_MED, fontsize=12.5, color=INK2, va="center",
    )
    hax.text(
        0.999, 0.62, "pass@1 by reasoning effort",
        family=SANS, fontsize=13, color=MUTED, va="center", ha="right",
    )

    # ---- panel 1: effort curves ----
    ax = fig.add_subplot(gs[1, 0])
    _style(ax)
    x = list(range(3))
    api_y = [api[e]["passat1"] for e in EFFORTS]
    zc_y = [zc[e]["passat1"] for e in EFFORTS]
    ax.plot(x, zc_y, "-o", color=ZC_COLOR, lw=3.2, ms=11, zorder=4, label="ZCode harness (subscription)")
    ax.plot(x, api_y, "-o", color=API_COLOR, lw=3.2, ms=11, zorder=4, label="Raw API (uniform loop)")
    for xi, yi in zip(x, zc_y):
        ax.text(xi, yi + 2.2, f"{yi:.1f}%", ha="center", family=BRAND_MED, fontsize=13, color=ZC_COLOR)
    for xi, yi in zip(x, api_y):
        ax.text(xi, yi - 3.6, f"{yi:.1f}%", ha="center", family=BRAND_MED, fontsize=13, color=API_COLOR)
    ax.set_xticks(x)
    ax.set_xticklabels([EFF_LABEL[e] for e in EFFORTS], family=SANS, fontsize=13, color=INK2)
    ax.set_ylim(55, 95)
    ax.set_yticks([60, 70, 80, 90])
    ax.set_yticklabels(["60", "70", "80", "90"], family=SANS, fontsize=11, color=MUTED)
    ax.set_ylabel("pass@1  (%)", family=SANS, fontsize=12, color=INK2)
    ax.set_xlabel("reasoning effort", family=SANS, fontsize=12, color=INK2)
    ax.legend(loc="lower center", frameon=False, fontsize=11.5, ncol=1, handlelength=1.6,
              bbox_to_anchor=(0.5, -0.01))
    ax.set_title("Same model, opposite effort curves", family=BRAND_MED, fontsize=15,
                 color=INK, pad=12, loc="left")
    # gap annotation at max
    ax.annotate(
        "", xy=(2, zc_y[2]), xytext=(2, api_y[2]),
        arrowprops=dict(arrowstyle="<->", color=MUTED, lw=1.3),
    )
    ax.text(1.86, (zc_y[2] + api_y[2]) / 2, f"+{zc_y[2] - api_y[2]:.1f} pts", ha="right",
            va="center", family=BRAND_MED, fontsize=12, color=INK2)

    # ---- panel 2: failure composition ----
    ax2 = fig.add_subplot(gs[1, 1])
    _style(ax2)
    bars = [("API", api, API_COLOR), ("ZCode", zc, ZC_COLOR)]
    xs, labels, group_centers = [], [], []
    pos = 0.0
    for gi, (hname, d, _c) in enumerate(bars):
        start = pos
        for e in EFFORTS:
            s, w, t = d[e]["solved"], d[e]["wrong"], d[e]["timeout"]
            ax2.bar(pos, s, 0.72, color=SOLVED, zorder=3)
            ax2.bar(pos, w, 0.72, bottom=s, color=WRONG, zorder=3)
            ax2.bar(pos, t, 0.72, bottom=s + w, color=TIMEOUT, zorder=3)
            # solved count sits inside the top of the solved segment
            ax2.text(pos, s - 0.8, f"{s}", ha="center", va="top", family=BRAND_MED,
                     fontsize=12, color="#ffffff")
            xs.append(pos)
            labels.append(EFF_LABEL[e])
            pos += 1.0
        group_centers.append((start + pos - 1.0) / 2)
        pos += 0.9
    ax2.set_xticks(xs)
    ax2.set_xticklabels(labels, family=SANS, fontsize=11, color=INK2)
    for gc, (hname, _d, c) in zip(group_centers, bars):
        ax2.text(gc, -2.3, "Raw API" if hname == "API" else "ZCode harness", ha="center",
                 family=BRAND_MED, fontsize=12.5, color=c)
    ax2.set_ylim(0, 24)
    ax2.set_yticks([0, 5, 10, 15, 20, 23])
    ax2.set_yticklabels(["0", "5", "10", "15", "20", "23"], family=SANS, fontsize=11, color=MUTED)
    ax2.set_ylabel("runs (of 23)", family=SANS, fontsize=12, color=INK2)
    ax2.set_title("How each harness fails: timeouts vs wrong answers", family=BRAND_MED,
                  fontsize=15, color=INK, pad=26, loc="left")
    # legend above the bars so it never overlaps them
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=SOLVED),
        plt.Rectangle((0, 0), 1, 1, color=WRONG),
        plt.Rectangle((0, 0), 1, 1, color=TIMEOUT),
    ]
    ax2.legend(handles, ["solved", "wrong answer", "unfinished (timeout)"], loc="lower right",
               bbox_to_anchor=(1.0, 1.005), ncol=3, frameon=False, fontsize=11, handlelength=1.2,
               columnspacing=1.4)

    fig.text(
        0.065, 0.035,
        "Same GLM 5.3, same 23 post-cutoff PRs, hidden-test grading. Raw API is metered "
        "(35.48 USD, all columns); ZCode bills a GLM Coding Plan (no marginal cash). "
        "One attempt per cell.",
        family=SANS, fontsize=10, color=MUTED, va="center",
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
