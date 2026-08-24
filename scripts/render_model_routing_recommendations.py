"""Render the Model Routing task-difficulty recommendation card."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
FONT_DIR = ROOT / "scripts" / "rankings-chart"
OUTPUT = ASSETS / "model-routing-task-difficulty-recommendations-2026-08-07.png"

WIDTH, HEIGHT = 1800, 1200
BG = "#07080B"
SURFACE = "#101219"
SURFACE_ALT = "#0D0F15"
GRID = "#252833"
WHITE = "#F7F8FA"
TEXT = "#D8DAE1"
MUTED = "#8C909C"
CYAN = "#35C7DE"
VIOLET = "#8267E8"


def font(weight: int, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / f"geist-{weight}.ttf"), size)


FONTS = {
    "kicker": font(600, 20),
    "title": font(600, 54),
    "date": font(500, 38),
    "head": font(600, 20),
    "difficulty": font(700, 30),
    "model": font(600, 29),
    "effort": font(600, 18),
    "body": font(400, 22),
    "metric": font(600, 27),
    "unit": font(400, 17),
    "footer": font(400, 17),
    "brand": font(500, 18),
}

ROWS = [
    {
        "difficulty": "EASY",
        "model": "GPT-5.6 Luna",
        "effort": "LOW EFFORT",
        "why": "Cheapest and fastest for simple, well-scoped fixes.",
        "accuracy": "76.8%",
        "cost": "$0.03",
        "time": "1.2 min",
        "accent": "#35C7DE",
    },
    {
        "difficulty": "MEDIUM",
        "model": "GPT-5.6 Terra",
        "effort": "MEDIUM EFFORT",
        "why": "Best overall balance of accuracy, cost, and speed.",
        "accuracy": "87.0%",
        "cost": "$0.19",
        "time": "2.3 min",
        "accent": "#27BFA6",
    },
    {
        "difficulty": "HARD",
        "model": "Grok 4.5",
        "effort": "HIGH EFFORT",
        "why": "Highest observed accuracy when task success matters most.",
        "accuracy": "89.9%",
        "cost": "$0.47",
        "time": "8.4 min",
        "accent": "#A98AF3",
    },
    {
        "difficulty": "HARD / VALUE",
        "model": "DeepSeek V4-Flash",
        "effort": "MAX EFFORT",
        "why": "Near-Grok accuracy at 86% lower cost, with higher latency.",
        "accuracy": "88.4%",
        "cost": "$0.06",
        "time": "11.2 min",
        "accent": "#5D8EF5",
    },
]


def draw_text(
    draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, style: str, fill: str
) -> None:
    draw.text(xy, value, font=FONTS[style], fill=fill)


def wrap(draw: ImageDraw.ImageDraw, value: str, max_width: int) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), candidate, font=FONTS["body"])[2]
        if current and width > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    # Header
    logo = Image.open(ASSETS / "model-routing-logo.png").convert("RGB")
    logo = logo.resize((150, 150), Image.Resampling.LANCZOS)
    image.paste(logo, (82, 54))
    draw_text(draw, (266, 65), "MODEL ROUTING  /  BENCHMARK-INFORMED GUIDE", "kicker", CYAN)
    draw_text(draw, (266, 101), "Model Routing Task Difficulty Recommendations,", "title", WHITE)
    draw_text(draw, (266, 164), "August 7th, 2026", "date", TEXT)
    draw.line((82, 238, 1718, 238), fill=GRID, width=2)

    # Column headers
    columns = {
        "difficulty": 100,
        "model": 360,
        "why": 760,
        "accuracy": 1250,
        "cost": 1430,
        "time": 1590,
    }
    header_y = 272
    for x, label in (
        (columns["difficulty"], "TASK"),
        (columns["model"], "RECOMMENDED MODEL"),
        (columns["why"], "WHY"),
        (columns["accuracy"], "PASS@1"),
        (columns["cost"], "COST / RUN"),
        (columns["time"], "TIME / TASK"),
    ):
        draw_text(draw, (x, header_y), label, "head", MUTED)

    row_top = 316
    row_height = 168
    for index, row in enumerate(ROWS):
        y = row_top + index * row_height
        fill = SURFACE if index % 2 == 0 else SURFACE_ALT
        draw.rounded_rectangle((82, y, 1718, y + 148), radius=20, fill=fill, outline=GRID, width=2)
        draw.rounded_rectangle((82, y, 91, y + 148), radius=5, fill=row["accent"])

        draw_text(
            draw, (columns["difficulty"], y + 53), row["difficulty"], "difficulty", row["accent"]
        )
        draw_text(draw, (columns["model"], y + 35), row["model"], "model", WHITE)

        effort_box = draw.textbbox((0, 0), row["effort"], font=FONTS["effort"])
        effort_width = effort_box[2] - effort_box[0] + 28
        draw.rounded_rectangle(
            (columns["model"], y + 83, columns["model"] + effort_width, y + 119),
            radius=18,
            fill="#191C25",
            outline=row["accent"],
            width=1,
        )
        draw_text(draw, (columns["model"] + 14, y + 91), row["effort"], "effort", row["accent"])

        for line_index, line in enumerate(wrap(draw, row["why"], 425)):
            draw_text(draw, (columns["why"], y + 43 + line_index * 30), line, "body", TEXT)

        for key, unit in (("accuracy", "PASS@1"), ("cost", "AVG API"), ("time", "WALL CLOCK")):
            draw_text(draw, (columns[key], y + 38), row[key], "metric", WHITE)
            draw_text(draw, (columns[key], y + 78), unit, "unit", MUTED)

    # Evidence boundary and signature
    footer_y = 1010
    draw.line((82, footer_y, 1718, footer_y), fill=GRID, width=2)
    draw_text(
        draw,
        (82, footer_y + 31),
        "Source: VulcanBench Eval Suite 3 · 23 frontier-hard tasks from merged OSS PRs · fixed step and wall-clock budgets.",
        "footer",
        MUTED,
    )
    draw_text(
        draw,
        (82, footer_y + 62),
        "Easy and medium tiers are routing recommendations; Suite 3 does not independently benchmark easier difficulty strata.",
        "footer",
        MUTED,
    )
    draw_text(draw, (82, footer_y + 108), "MODEL ROUTING", "brand", VIOLET)
    draw_text(draw, (1450, footer_y + 108), "modelrouting.substack.com", "brand", TEXT)

    image.save(OUTPUT, format="PNG", optimize=True)
    print(f"saved {OUTPUT}")


if __name__ == "__main__":
    main()
