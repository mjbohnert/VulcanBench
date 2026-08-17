"""Hidden behavioral tests for oss-click-style-validate-color (click #3677).

Graded on the observable output of the public ``click.style``: the ANSI codes it
emits, and the exception type it raises for invalid colors — never internal
helpers.
"""

from __future__ import annotations

import click
import pytest

RESET = "\033[0m"


# --- fail_to_pass: wrong at the base commit, fixed by the patch ---------------


def test_foreground_index_zero_not_dropped() -> None:
    """The 256-color index 0 (black) is a valid color and must not be silently
    dropped as a falsy value."""
    out = click.style("x", fg=0)
    assert "38;5;0" in out
    assert out == f"\033[38;5;0mx{RESET}"


def test_background_index_zero_not_dropped() -> None:
    out = click.style("x", bg=0)
    assert "48;5;0" in out


def test_unknown_color_name_raises_value_error() -> None:
    """An unknown color name is invalid input and must raise ValueError."""
    with pytest.raises(ValueError):
        click.style("x", fg="chartreuse-ish")


def test_out_of_range_index_raises_value_error() -> None:
    """A 256-color index outside 0..255 is invalid and must raise ValueError
    rather than emitting a bogus escape code."""
    with pytest.raises(ValueError):
        click.style("x", fg=999)


# --- pass_to_pass: correct at the base commit and after the patch -------------


def test_named_color_unchanged() -> None:
    assert click.style("x", fg="red") == f"\033[31mx{RESET}"


def test_rgb_tuple_unchanged() -> None:
    out = click.style("x", fg=(255, 0, 0))
    assert "38;2;255;0;0" in out
