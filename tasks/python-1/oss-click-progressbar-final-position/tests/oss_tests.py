"""Hidden behavioral tests for oss-click-progressbar-final-position (click #3769).

When ``update_min_steps`` does not evenly divide the work (or exceeds it), the
progress bar froze below completion — e.g. reporting ``14/20`` for a length of 20
with a threshold of 7, because the trailing remainder was never flushed. Graded on
the rendered output of the public ``click.progressbar``: the final frame must show
completion.
"""

from __future__ import annotations

import io

import click
import click._termui_impl


def _final_render(update_min_steps: int, drive: str, monkeypatch) -> str:
    monkeypatch.setattr(click._termui_impl, "isatty", lambda _: True)
    stream = io.StringIO()
    if drive == "iterate":
        with click.progressbar(
            range(20), show_pos=True, update_min_steps=update_min_steps, file=stream
        ) as bar:
            for _ in bar:
                pass
    else:
        with click.progressbar(
            length=20, show_pos=True, update_min_steps=update_min_steps, file=stream
        ) as bar:
            for _ in range(20):
                bar.update(1)
    return stream.getvalue()


# --- fail_to_pass: bar froze below completion at the base commit --------------


def test_lands_on_final_position_threshold_indivisible(monkeypatch) -> None:
    # 7 does not divide 20, leaving a remainder that used to freeze the bar at 14/20.
    assert "20/20" in _final_render(7, "iterate", monkeypatch)


def test_lands_on_final_position_threshold_exceeds_length(monkeypatch) -> None:
    # 25 > 20, so nothing rendered until the end; the final frame must still complete.
    assert "20/20" in _final_render(25, "iterate", monkeypatch)


def test_lands_on_final_position_when_driven_by_update(monkeypatch) -> None:
    assert "20/20" in _final_render(7, "update", monkeypatch)


# --- pass_to_pass: thresholds that divide the length already worked -----------


def test_threshold_one_completes(monkeypatch) -> None:
    assert "20/20" in _final_render(1, "iterate", monkeypatch)


def test_threshold_two_completes(monkeypatch) -> None:
    assert "20/20" in _final_render(2, "iterate", monkeypatch)
