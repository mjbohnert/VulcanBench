"""Voice-tax reporting: aggregate a run's results.jsonl into tables.

Headline metric: **voice tax** = text accuracy - audio accuracy on the
clean/normal condition (all voices pooled). Also reported: per-category and
per-condition breakdowns, and latency percentiles (median/P95/P99) for both
time-to-first-token and total turn time. Markdown output follows the style
of ``harness/report.py``.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from harness.voice.audio import TEXT_CONDITION_SLUG


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    idx = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(idx), math.ceil(idx)
    if lo == hi:
        return sorted_vals[lo]
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def latency_stats(vals: list[float]) -> dict[str, float]:
    s = sorted(vals)
    return {
        "median": round(_percentile(s, 0.50), 3),
        "p95": round(_percentile(s, 0.95), 3),
        "p99": round(_percentile(s, 0.99), 3),
    }


def _acc(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    return sum(1 for r in rows if r.get("correct")) / len(rows)


def build_report(run_dir: Path) -> dict[str, Any]:
    manifest = json.loads((run_dir / "manifest.json").read_text())
    raw_rows = [
        json.loads(line)
        for line in (run_dir / "results.jsonl").read_text().splitlines()
        if line.strip()
    ]
    # results.jsonl is append-only and resumable runs re-attempt failed or
    # judge-errored units, so superseded attempts linger. Only the LATEST row
    # per (model, mode, question, condition) counts.
    latest: dict[str, dict[str, Any]] = {}
    for r in raw_rows:
        latest[f"{r['model']}|{r['mode']}|{r['question_id']}|{r['condition_slug']}"] = r
    rows = list(latest.values())
    ok_rows = [r for r in rows if r.get("error") is None]
    errors = [r for r in rows if r.get("error") is not None]

    by_model: dict[str, dict[str, Any]] = {}
    for model in sorted({r["model"] for r in ok_rows}):
        mrows = [r for r in ok_rows if r["model"] == model]
        text_rows = [r for r in mrows if r["mode"] == "text"]
        audio_rows = [r for r in mrows if r["mode"] == "audio"]
        clean_normal = [
            r
            for r in audio_rows
            if r["condition"]
            and r["condition"]["rate"] == "normal"
            and r["condition"]["noise"] == "clean"
        ]
        text_acc = _acc(text_rows)
        audio_acc = _acc(clean_normal)
        # Paired comparison: restrict text baseline to items that also have a
        # clean/normal audio row, so partial runs can't skew the delta.
        audio_ids = {r["question_id"] for r in clean_normal}
        paired_text = [r for r in text_rows if r["question_id"] in audio_ids]
        paired_text_acc = _acc(paired_text)

        conditions: dict[str, Any] = {}
        for slug in sorted({r["condition_slug"] for r in mrows}):
            crows = [r for r in mrows if r["condition_slug"] == slug]
            sub_ids = {r["question_id"] for r in crows}
            base = [r for r in text_rows if r["question_id"] in sub_ids]
            conditions[slug] = {
                "n": len(crows),
                "accuracy": _acc(crows),
                "text_accuracy_same_items": _acc(base) if slug != TEXT_CONDITION_SLUG else None,
                "tax": (
                    None
                    if slug == TEXT_CONDITION_SLUG or _acc(base) is None or _acc(crows) is None
                    else round((_acc(base) or 0) - (_acc(crows) or 0), 4)
                ),
            }

        categories: dict[str, Any] = {}
        for cat in sorted({r["category"] for r in mrows}):
            cat_text = [r for r in text_rows if r["category"] == cat]
            cat_audio = [r for r in clean_normal if r["category"] == cat]
            categories[cat] = {
                "text_accuracy": _acc(cat_text),
                "audio_accuracy": _acc(cat_audio),
                "tax": (
                    None
                    if _acc(cat_text) is None or _acc(cat_audio) is None
                    else round((_acc(cat_text) or 0) - (_acc(cat_audio) or 0), 4)
                ),
            }

        latency = {
            "text": {
                "t_first_s": latency_stats([r["t_first_s"] for r in text_rows]),
                "t_total_s": latency_stats([r["t_total_s"] for r in text_rows]),
            },
            "audio": {
                "t_first_s": latency_stats([r["t_first_s"] for r in audio_rows]),
                "t_total_s": latency_stats([r["t_total_s"] for r in audio_rows]),
            },
        }

        stt_used = sum(1 for r in audio_rows if r.get("transcribed_by"))
        by_model[model] = {
            "text_accuracy": text_acc,
            "audio_accuracy_clean_normal": audio_acc,
            "voice_tax": (
                None
                if paired_text_acc is None or audio_acc is None
                else round(paired_text_acc - audio_acc, 4)
            ),
            "n_text": len(text_rows),
            "n_audio_clean_normal": len(clean_normal),
            "stt_fallback_answers": stt_used,
            "conditions": conditions,
            "categories": categories,
            "latency": latency,
        }

    judge_share: dict[str, int] = defaultdict(int)
    for r in ok_rows:
        judge_share[r.get("score_method", "?")] += 1

    return {
        "manifest": manifest,
        "models": by_model,
        "score_methods": dict(judge_share),
        "n_rows": len(rows),
        "n_errors": len(errors),
    }


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f}%"


def to_markdown(report: dict[str, Any]) -> str:
    m = report["manifest"]
    lines = [
        "# Voice Eval Suite v1 — run report",
        "",
        f"_Run `{m['run_id']}` · {m.get('n_items', '?')} items · models: "
        f"{', '.join(m['models'])} · judge {m['judge_model']} · TTS "
        f"{m['tts']['provider']} ({', '.join(m['tts']['voices'])}) · seed {m['seed']}_",
        "",
        "## Voice tax (text - audio accuracy, clean/normal, paired items)",
        "",
        "| Model | Text | Audio (clean/normal) | Voice tax |",
        "|---|---|---|---|",
    ]
    for model, data in report["models"].items():
        tax = data["voice_tax"]
        tax_s = "—" if tax is None else f"{100 * tax:+.1f} pp"
        lines.append(
            f"| {model} | {_pct(data['text_accuracy'])} | "
            f"{_pct(data['audio_accuracy_clean_normal'])} | {tax_s} |"
        )
    for model, data in report["models"].items():
        lines += ["", f"## {model} — by category", "", "| Category | Text | Audio | Tax |",
                  "|---|---|---|---|"]  # fmt: skip
        for cat, c in data["categories"].items():
            tax_s = "—" if c["tax"] is None else f"{100 * c['tax']:+.1f} pp"
            lines.append(
                f"| {cat} | {_pct(c['text_accuracy'])} | {_pct(c['audio_accuracy'])} | {tax_s} |"
            )
        lines += ["", f"## {model} — by condition", "",
                  "| Condition | n | Accuracy | Text acc (same items) | Tax |",
                  "|---|---|---|---|---|"]  # fmt: skip
        for slug, c in data["conditions"].items():
            tax_s = "—" if c["tax"] is None else f"{100 * c['tax']:+.1f} pp"
            lines.append(
                f"| {slug} | {c['n']} | {_pct(c['accuracy'])} | "
                f"{_pct(c['text_accuracy_same_items'])} | {tax_s} |"
            )
        lat = data["latency"]
        lines += ["", f"## {model} — latency (seconds)", "",
                  "| Mode | Metric | Median | P95 | P99 |", "|---|---|---|---|---|"]  # fmt: skip
        for mode in ("text", "audio"):
            for metric in ("t_first_s", "t_total_s"):
                st = lat[mode][metric]
                lines.append(f"| {mode} | {metric} | {st['median']} | {st['p95']} | {st['p99']} |")
    if report["n_errors"]:
        lines += ["", f"⚠️ {report['n_errors']} unit(s) errored and are excluded; "
                  "re-run the same command to retry them."]  # fmt: skip
    return "\n".join(lines) + "\n"
