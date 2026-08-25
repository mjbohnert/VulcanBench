"""Report No. 18 harness-study card: GLM 5.3 in ZCode vs a bare-bones harness.

Two panels in the VulcanBench Harness Study format:
  Left  - pass@1 by effort, ZCode vs the bare-bones API loop, +/-1 stderr whiskers.
  Right - where GLM 5.3 lands on the v3 best-effort leaderboard: its raw-API best
          is a legitimate board entry near the bottom; ZCode (model plus product)
          is shown for reference, lifting the same model into the 87% cluster.

Reads docs/results/v3-glm53-2026-08/v3-glm53-2026-08.json and writes
report18-glm53-zcode.png next to it.
Usage: python scripts/rankings-chart/make_glm53_studycard.py
"""

from __future__ import annotations

import json
from math import sqrt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import BRAND, BRAND_MED, GRID, INK, INK2, MUTED, SANS, SURFACE, register_fonts

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent.parent / "docs" / "results" / "v3-glm53-2026-08"
DATA = REPORT / "v3-glm53-2026-08.json"
OUT = REPORT / "report18-glm53-zcode.png"
LOGO = HERE / "vb_logo_rounded.png"

API_COLOR = INK
ZC_COLOR = "#10b981"
FIELD = "#c7c3ba"  # other models on the board
EFFORTS = ["low", "high", "extra-high"]
LBL = {"low": "low", "high": "high", "extra-high": "max"}

# v3 best-effort-per-model leaderboard (raw-API / uniform-loop entries), from
# vulcanbench.com/leaderboard. pass@1 percent, best effort. GLM 5.3's raw-API
# best (78.3, low) is inserted as its own board entry; ZCode is NOT a board
# entry and is drawn as a reference marker only.
BOARD = [
    ("Grok 4.5", 89.9),
    ("Claude Fable 5", 89.5),
    ("DeepSeek V4-Flash", 88.4),
    ("DeepSeek V4 Pro", 87.0),
    ("GPT-5.6 Terra", 87.0),
    ("Claude Opus 5", 87.0),
    ("Grok 4.6", 87.0),
    ("GPT-5.6 Sol", 87.0),
    ("GPT-5.6 Luna", 85.5),
    ("Qwen3.8-27B", 82.6),
    ("Qwen3.8-Max", 81.2),
    ("GLM 5.3 (raw API)", 78.3),
    ("Claude Haiku 4.5", 76.2),
    ("Kimi K3", 73.7),
]
GLM_ZCODE = 87.0


def stderr_pct(solved: int, n: int) -> float:
    p = solved / n
    return sqrt(p * (1 - p) / n) * 100


def main() -> None:  # noqa: PLR0915 (single linear chart layout)
    register_fonts()
    data = json.loads(DATA.read_text())
    api, zc = data["api"], data["zcode"]

    def series(d):
        return (
            [d[e]["passat1"] for e in EFFORTS],
            [stderr_pct(d[e]["solved"], d[e]["n"]) for e in EFFORTS],
        )

    api_y, api_se = series(api)
    zc_y, zc_se = series(zc)

    fig = plt.figure(figsize=(16, 9), dpi=160)
    fig.patch.set_facecolor(SURFACE)

    # header
    hax = fig.add_axes((0, 0.85, 1, 0.15))
    hax.axis("off")
    tx = 0.062
    try:
        logo = plt.imread(str(LOGO))
        hax.imshow(
            logo,
            extent=(tx, tx + 0.05, 0.24, 0.86),
            transform=hax.transAxes,
            aspect="auto",
            zorder=5,
        )
        wx = tx + 0.066
    except Exception:
        wx = tx
    hax.text(
        wx,
        0.64,
        "VulcanBench",
        family=BRAND,
        fontsize=26,
        color=INK,
        va="center",
        transform=hax.transAxes,
    )
    hax.text(
        wx,
        0.26,
        "Technical Report No. 18   ·   Harness Study No. 03",
        family=BRAND_MED,
        fontsize=13,
        color=MUTED,
        va="center",
        transform=hax.transAxes,
    )
    hax.text(
        0.938,
        0.5,
        "GLM 5.3 in ZCode\nvs. a bare-bones harness",
        family=BRAND_MED,
        fontsize=14.5,
        color=INK2,
        va="center",
        ha="right",
        transform=hax.transAxes,
        linespacing=1.3,
    )

    # headline
    fig.text(
        0.062,
        0.795,
        "Through its raw API, GLM 5.3 sits near the bottom of the board (78.3%). Its own",
        family=SANS,
        fontsize=16.5,
        color=INK,
        va="center",
    )
    fig.text(
        0.062,
        0.758,
        "ZCode harness lifts the same model 21.8 points, into the 87% frontier cluster.",
        family=SANS,
        fontsize=16.5,
        color=INK,
        va="center",
    )

    # ---- left panel: effort curves ----
    ax = fig.add_axes((0.062, 0.17, 0.42, 0.47))
    _grid(ax)
    x = [0, 1, 2]
    ax.errorbar(
        x,
        zc_y,
        yerr=zc_se,
        color=ZC_COLOR,
        lw=3.2,
        marker="o",
        ms=11,
        capsize=6,
        elinewidth=2,
        capthick=2,
        zorder=5,
        label="ZCode harness",
    )
    ax.errorbar(
        x,
        api_y,
        yerr=api_se,
        color=API_COLOR,
        lw=3.2,
        marker="o",
        ms=11,
        capsize=6,
        elinewidth=2,
        capthick=2,
        zorder=5,
        label="Bare-bones API loop",
    )
    for xi, yi, se in zip(x, zc_y, zc_se, strict=True):
        ax.text(
            xi,
            yi + se + 1.8,
            f"{yi:.1f}",
            ha="center",
            family=BRAND_MED,
            fontsize=13.5,
            color=ZC_COLOR,
        )
    for xi, yi, se in zip(x, api_y, api_se, strict=True):
        ax.text(
            xi,
            yi - se - 3.4,
            f"{yi:.1f}",
            ha="center",
            family=BRAND_MED,
            fontsize=13.5,
            color=API_COLOR,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([LBL[e] for e in EFFORTS], family=SANS, fontsize=14, color=INK2)
    ax.set_xlim(-0.3, 2.3)
    ax.set_ylim(50, 100)
    ax.set_yticks([50, 60, 70, 80, 90, 100])
    ax.set_yticklabels(["50", "60", "70", "80", "90", "100"], family=SANS, fontsize=11, color=MUTED)
    ax.set_xlabel("reasoning effort", family=SANS, fontsize=12.5, color=INK2)
    ax.set_title("pass@1 by effort", family=BRAND_MED, fontsize=15, color=INK, loc="left", pad=10)
    ax.legend(
        loc="lower left",
        frameon=False,
        fontsize=12.5,
        handlelength=1.6,
        bbox_to_anchor=(0.02, 0.02),
    )

    # ---- right panel: best-effort leaderboard placement ----
    ax2 = fig.add_axes((0.60, 0.17, 0.345, 0.58))
    ax2.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    ax2.spines["bottom"].set_color(GRID)
    ax2.tick_params(length=0)
    n = len(BOARD)
    ys = list(range(n, 0, -1))  # top model at the top
    base = 70.0
    for (name, val), y in zip(BOARD, ys, strict=True):
        is_glm = name.startswith("GLM 5.3")
        color = API_COLOR if is_glm else FIELD
        ax2.barh(y, val - base, left=base, height=0.62, color=color, zorder=3)
        weight = BRAND_MED if is_glm else SANS
        ax2.text(
            base - 0.6,
            y,
            name,
            ha="right",
            va="center",
            family=weight,
            fontsize=10.5,
            color=INK if is_glm else INK2,
        )
        ax2.text(
            val + 0.5,
            y,
            f"{val:.1f}",
            ha="left",
            va="center",
            family=SANS,
            fontsize=10,
            color=INK if is_glm else MUTED,
        )
    # ZCode reference: dashed line at 87.0 down to the cluster, plus a marker on GLM's row
    glm_y = ys[[nm for nm, _ in BOARD].index("GLM 5.3 (raw API)")]
    ax2.plot(
        [GLM_ZCODE, GLM_ZCODE], [glm_y - 0.4, n + 0.4], color=ZC_COLOR, lw=1.6, ls="--", zorder=2
    )
    ax2.annotate(
        "",
        xy=(GLM_ZCODE, glm_y),
        xytext=(78.3, glm_y),
        arrowprops=dict(arrowstyle="->", color=ZC_COLOR, lw=2.2),
        zorder=6,
    )
    ax2.plot(GLM_ZCODE, glm_y, "o", color=ZC_COLOR, ms=10, zorder=7)
    ax2.text(
        GLM_ZCODE + 0.5,
        glm_y - 0.95,
        "same model,\nin ZCode: 87.0",
        ha="left",
        va="top",
        family=BRAND_MED,
        fontsize=10.5,
        color=ZC_COLOR,
        linespacing=1.2,
    )
    ax2.set_xlim(base, 93)
    ax2.set_ylim(0.3, n + 1.4)
    ax2.set_yticks([])
    ax2.set_xticks([70, 80, 90])
    ax2.set_xticklabels(["70", "80", "90"], family=SANS, fontsize=11, color=MUTED)
    ax2.set_title(
        "v3 best-effort leaderboard  (pass@1 %)",
        family=BRAND_MED,
        fontsize=15,
        color=INK,
        loc="left",
        pad=10,
    )

    # footer
    fig.text(
        0.062,
        0.072,
        "VulcanBench v3: 23 post-cutoff merged PRs, hidden deterministic tests, Docker-isolated. "
        "One attempt per cell for GLM 5.3; whiskers are +/-1 binomial stderr.",
        family=SANS,
        fontsize=10.5,
        color=MUTED,
        va="center",
    )
    fig.text(
        0.062,
        0.038,
        "Board entries are raw-API / uniform-loop runs. ZCode is model plus product, shown for reference, "
        "not a raw-API leaderboard entry. Verified running glm-5.3 from ZCode's session store.",
        family=SANS,
        fontsize=10.5,
        color=MUTED,
        va="center",
    )
    fig.text(
        0.938,
        0.072,
        "vulcanbench.com",
        family=BRAND_MED,
        fontsize=12.5,
        color=INK2,
        va="center",
        ha="right",
    )

    fig.savefig(OUT, facecolor=SURFACE)
    print(f"wrote {OUT}")


def _grid(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, lw=1)
    ax.set_ylabel("pass@1  (%)", family=SANS, fontsize=12.5, color=INK2)


if __name__ == "__main__":
    main()
