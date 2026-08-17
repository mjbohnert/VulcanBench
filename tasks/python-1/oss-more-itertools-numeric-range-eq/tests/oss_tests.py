"""Hidden behavioral tests for oss-more-itertools-numeric-range-eq (#1216).

``numeric_range`` equality and hashing should mirror the built-in ``range``: two
ranges are equal when they cover the same values, which for a single-element range
means the step is irrelevant. Equality and hashing must agree. Graded through the
public ``==`` / ``hash`` behavior of ``numeric_range``.
"""

from __future__ import annotations

from decimal import Decimal as D

from more_itertools import numeric_range


# --- fail_to_pass: step wrongly mattered for single-element ranges ------------


def test_single_element_ranges_equal_regardless_of_step() -> None:
    # Both cover exactly [0]; like range(0, 1, 1) == range(0, 1, 5).
    a = numeric_range(D(0), D(1), D(1))
    b = numeric_range(D(0), D(1), D(5))
    assert list(a) == list(b) == [D(0)]
    assert a == b


def test_single_element_equal_ranges_hash_equal() -> None:
    a = numeric_range(D(0), D(1), D(1))
    b = numeric_range(D(0), D(1), D(5))
    assert a == b
    assert hash(a) == hash(b)  # equal objects must hash equal


def test_single_element_ranges_equal_other_values() -> None:
    a = numeric_range(D(3), D(4), D(1))
    b = numeric_range(D(3), D(4), D(9))
    assert list(a) == list(b) == [D(3)]
    assert a == b
    assert hash(a) == hash(b)


# --- pass_to_pass: multi-element and unequal cases unchanged ------------------


def test_equal_multi_element_ranges_still_equal() -> None:
    a = numeric_range(D(0), D(10), D(2))
    b = numeric_range(D(0), D(10), D(2))
    assert a == b
    assert hash(a) == hash(b)


def test_different_ranges_not_equal() -> None:
    assert numeric_range(D(0), D(10), D(2)) != numeric_range(D(1), D(10), D(2))
    assert numeric_range(D(0), D(10), D(2)) != numeric_range(D(0), D(10), D(3))
