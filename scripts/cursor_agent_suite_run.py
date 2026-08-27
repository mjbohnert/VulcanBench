#!/usr/bin/env python3
"""Prepare and track cursor-agent suite runs (solve/finalize via cloud agents)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from harness.cursor_agent.paths import default_cursor_runs_dir
from harness.suite import load_suite


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr)
        raise SystemExit(proc.returncode)
    return json.loads(proc.stdout)


def prepare_all(
    *,
    suite: str,
    repeats: int,
    output_dir: Path,
    model: str,
    tasks: list[str] | None = None,
) -> list[dict[str, Any]]:
    suite_obj = load_suite(suite)
    task_ids = tasks or suite_obj.task_ids
    manifests: list[dict[str, Any]] = []
    for repeat in range(1, repeats + 1):
        for task_id in task_ids:
            manifest = _run(
                [
                    "vulcanbench",
                    "cursor-agent",
                    "prepare",
                    "--task",
                    task_id,
                    "--suite",
                    suite,
                    "--repeat",
                    str(repeat),
                    "--model",
                    model,
                    "--output-dir",
                    str(output_dir),
                ]
            )
            manifests.append(manifest)
    return manifests


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def status(runs_dir: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path) if manifest_path.is_file() else {"runs": []}
    runs = manifest.get("runs") or []
    pending_solve = []
    pending_finalize = []
    done = []
    for entry in runs:
        run_dir = Path(entry["run_dir"])
        if not (run_dir / "summary.json").is_file():
            if entry.get("bc_id"):
                pending_finalize.append(entry)
            else:
                pending_solve.append(entry)
        else:
            done.append(entry)
    return {
        "total": len(runs),
        "done": len(done),
        "pending_solve": len(pending_solve),
        "pending_finalize": len(pending_finalize),
        "pending_solve_runs": pending_solve[:5],
        "pending_finalize_runs": pending_finalize[:5],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare", help="Prepare all suite runs")
    prep.add_argument("--suite", default="v4")
    prep.add_argument("--repeats", type=int, default=3)
    prep.add_argument("--output-dir", type=Path, default=None, help="Isolated run root")
    prep.add_argument("--model", default="cursor-agent:composer-2.5")
    prep.add_argument(
        "--manifest",
        type=Path,
        default=Path("/tmp/vulcanbench-runs/cursor-agent-manifest.json"),
    )
    prep.add_argument("--task", action="append", dest="tasks", help="Limit to task id(s)")

    st = sub.add_parser("status", help="Show run progress")
    st.add_argument(
        "--manifest",
        type=Path,
        default=Path("/tmp/vulcanbench-runs/cursor-agent-manifest.json"),
    )
    st.add_argument("--runs-dir", type=Path, default=None, help="Run root (default: isolated)")

    args = parser.parse_args()
    if args.cmd == "prepare":
        out = args.output_dir if args.output_dir is not None else default_cursor_runs_dir(args.suite)
        manifests = prepare_all(
            suite=args.suite,
            repeats=args.repeats,
            output_dir=out,
            model=args.model,
            tasks=args.tasks,
        )
        write_manifest(
            args.manifest,
            {
                "suite": args.suite,
                "model": args.model,
                "repeats": args.repeats,
                "runs": [
                    {
                        "run_id": m["run_id"],
                        "task_id": m["task_id"],
                        "repeat_index": m["repeat_index"],
                        "run_dir": m["run_dir"],
                        "workspace": m["workspace"],
                    }
                    for m in manifests
                ],
            },
        )
        print(f"Prepared {len(manifests)} runs -> {args.manifest}")
    elif args.cmd == "status":
        manifest = load_manifest(args.manifest) if args.manifest.is_file() else {"runs": []}
        runs_dir = args.runs_dir
        if runs_dir is None:
            suite = manifest.get("suite", "v4")
            runs_dir = default_cursor_runs_dir(str(suite))
        print(json.dumps(status(runs_dir, args.manifest), indent=2))


if __name__ == "__main__":
    main()
