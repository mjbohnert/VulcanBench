#!/usr/bin/env python3
"""Finalize cursor-agent runs from bc-id -> run_dir mappings."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=Path, help="JSON: {bc_id: {run_dir, transcript}}")
    args = parser.parse_args()
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    for bc_id, entry in mapping.items():
        cmd = [
            "vulcanbench",
            "cursor-agent",
            "finalize",
            entry["run_dir"],
            "--transcript",
            entry["transcript"],
            "--bc-id",
            bc_id,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stderr or proc.stdout, file=sys.stderr)
            continue
        summary = json.loads(proc.stdout)
        passed = summary["scores"]["functional"] == 1.0
        tok = summary["tokens"]
        print(
            f"{summary['task_id']:45} {'PASS' if passed else 'FAIL'} "
            f"in={tok['input']} reason={tok['reasoning']} out={tok['output']}"
        )


if __name__ == "__main__":
    main()
