#!/usr/bin/env python3
"""Per-task breakdown for cursor-agent suite runs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_summaries(runs_dir: Path, model: str, suite: str | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for summary_path in runs_dir.rglob("summary.json"):
        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("model") != model:
            continue
        if suite is not None and data.get("suite") != suite:
            continue
        out.append(data)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument("--model", default="cursor-agent:composer-2.5")
    parser.add_argument("--suite", default="v4")
    args = parser.parse_args()

    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for summary in _load_summaries(args.runs_dir, args.model, args.suite):
        by_task[str(summary.get("task_id", "unknown"))].append(summary)

    if not by_task:
        print(f"No runs for model={args.model!r} suite={args.suite!r} under {args.runs_dir}")
        raise SystemExit(1)

    total_runs = sum(len(v) for v in by_task.values())
    passed = sum(
        1
        for runs in by_task.values()
        for s in runs
        if (s.get("scores") or {}).get("functional") == 1.0
    )
    failed = total_runs - passed

    print(f"# {args.model} on suite {args.suite}")
    print(f"Tasks: {len(by_task)} | Runs: {total_runs} | Pass: {passed} | Fail: {failed}")
    print()
    print(
        "| task | runs | pass | avg functional | time (s) | "
        "input tok | reasoning tok | output tok | est. cost ($) |"
    )
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    for task_id in sorted(by_task):
        runs = by_task[task_id]
        funcs = [(r.get("scores") or {}).get("functional") for r in runs]
        n_pass = sum(1 for f in funcs if f == 1.0)
        avg_func = sum(f for f in funcs if isinstance(f, (int, float))) / len(runs)
        avg_time = sum(float(r.get("duration_s") or 0) for r in runs) / len(runs)
        tok = runs[0].get("tokens") or {}
        avg_in = sum((r.get("tokens") or {}).get("input", 0) for r in runs) / len(runs)
        avg_reason = sum((r.get("tokens") or {}).get("reasoning", 0) for r in runs) / len(runs)
        avg_out = sum((r.get("tokens") or {}).get("output", 0) for r in runs) / len(runs)
        costs = [r.get("cost_usd") for r in runs if r.get("cost_usd") is not None]
        avg_cost = sum(costs) / len(costs) if costs else None
        cost_cell = f"{avg_cost:.4f}" if avg_cost is not None else "n/a"
        print(
            f"| {task_id} | {len(runs)} | {n_pass}/{len(runs)} | {avg_func:.3f} | "
            f"{avg_time:.1f} | {avg_in:.0f} | {avg_reason:.0f} | {avg_out:.0f} | {cost_cell} |"
        )


if __name__ == "__main__":
    main()
