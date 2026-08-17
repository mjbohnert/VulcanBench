"""Hidden behavioral tests for oss-more-itertools-iter-index-negative (#1182).

``iter_index`` has a fast path for sequences (objects with ``.index``) and a slow
path for general iterables. Negative ``start`` / ``stop`` worked on the fast path
but broke on the slow path. Graded on the public ``iter_index`` output; the two
paths must agree.

'AABCADEAF' — the value 'A' occurs at indexes 0, 1, 4, 7.
"""

from __future__ import annotations

import more_itertools as mi

DATA = "AABCADEAF"


# --- fail_to_pass: the slow path (general iterable) was broken -----------------
# ``iter(DATA)`` has no ``.index`` method, so it takes the general-iterable path.


def test_general_iterable_negative_start() -> None:
    assert list(mi.iter_index(iter(DATA), "A", start=-3)) == [7]


def test_general_iterable_negative_stop() -> None:
    assert list(mi.iter_index(iter(DATA), "A", stop=-2)) == [0, 1, 4]


def test_general_iterable_negative_start_and_stop() -> None:
    assert list(mi.iter_index(iter(DATA), "A", start=-5, stop=-1)) == [4, 7]


# --- pass_to_pass: the sequence fast path already worked ----------------------


def test_sequence_negative_start_unchanged() -> None:
    assert list(mi.iter_index(DATA, "A", start=-3)) == [7]


def test_sequence_full_scan_unchanged() -> None:
    assert list(mi.iter_index(DATA, "A")) == [0, 1, 4, 7]
