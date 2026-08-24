"""Hidden behavioral tests for oss-more-itertools-running-minmax-stable (#1211).

Graded on observable output of the public ``running_min`` / ``running_max``
recipes: the *values* they yield and, on ties, *which* of several equal values
they keep. The stability contract mirrors the builtins — ``min(x, y)`` and
``max(x, y)`` return ``x`` when ``x == y`` — so a window of equal-but-distinct
values must keep the oldest, which is observable through the value's type.
"""

from __future__ import annotations

from fractions import Fraction

import more_itertools as mi

# Values that compare equal (0 == 0.0 == Fraction(0)) but have distinct types,
# so "which equal value was kept" is observable via type().
EQUAL = [0, 0.0, Fraction(0)]


# --- fail_to_pass: wrong at the base commit, fixed by the patch ---------------
# The bug lives only in the bounded (maxlen) sliding-window path, so every
# fail_to_pass exercises a tie inside a window.


def test_running_min_ties_keep_oldest_windowed() -> None:
    """With maxlen=2, each window's minimum must be the oldest equal value,
    matching ``min`` applied to that window."""
    got = list(map(type, mi.running_min(EQUAL, maxlen=2)))
    expected = [type(min(EQUAL[0:1])), type(min(EQUAL[0:2])), type(min(EQUAL[1:3]))]
    assert got == expected  # [int, int, float]


def test_running_max_ties_keep_oldest_windowed() -> None:
    """With maxlen=2, each window's maximum must be the oldest equal value,
    matching ``max`` applied to that window."""
    got = list(map(type, mi.running_max(EQUAL, maxlen=2)))
    expected = [type(max(EQUAL[0:1])), type(max(EQUAL[0:2])), type(max(EQUAL[1:3]))]
    assert got == expected  # [int, int, float]


def test_running_min_tie_inside_window_keeps_oldest() -> None:
    """A tie that appears mid-stream inside a bounded window keeps the oldest
    equal value for as long as it stays in the window."""
    data = [2, 0, 0.0, 3]  # the two zeros tie inside maxlen=3 windows
    assert list(map(type, mi.running_min(data, maxlen=3))) == [int, int, int, int]


def test_running_max_tie_inside_window_keeps_oldest() -> None:
    data = [1, 5, 5.0, 2]  # the two fives tie inside maxlen=3 windows
    assert list(map(type, mi.running_max(data, maxlen=3))) == [int, int, int, int]


# --- pass_to_pass: correct at the base commit and after the patch -------------


def test_running_min_unbounded_stable_and_unchanged() -> None:
    """The unbounded path was already stable; guard that it stays so."""
    assert list(map(type, mi.running_min(EQUAL))) == [int, int, int]


def test_running_max_unbounded_stable_and_unchanged() -> None:
    assert list(map(type, mi.running_max(EQUAL))) == [int, int, int]


def test_running_min_basic_values_unchanged() -> None:
    """Distinct-value sliding minimum is unaffected by the stability fix."""
    data = [5, 3, 8, 1, 9, 2, 7]
    assert list(mi.running_min(data, maxlen=3)) == [5, 3, 3, 1, 1, 1, 2]


def test_running_max_basic_values_unchanged() -> None:
    data = [5, 3, 8, 1, 9, 2, 7]
    assert list(mi.running_max(data, maxlen=3)) == [5, 5, 8, 8, 9, 9, 9]
