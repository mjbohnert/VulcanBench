"""Default paths for cursor-agent benchmark runs."""

from __future__ import annotations

import os
from pathlib import Path


def default_cursor_runs_dir(suite: str) -> Path:
    """Isolated run root outside the VulcanBench git checkout.

    Override with ``VULCANBENCH_CURSOR_RUNS_DIR`` (e.g. ``/tmp/vulcanbench-runs``).
    """
    root = Path(os.environ.get("VULCANBENCH_CURSOR_RUNS_DIR", "/tmp/vulcanbench-runs"))
    return root / suite
