"""Hidden grader tests for the net-new subfactorial() function.

subfactorial(n) is the number of permutations of n elements with no fixed
points -- the length of derangements(). Expected values are generated from the
gold patch (OEIS A000166).
"""

from math import e, factorial

import pytest

from more_itertools import derangements, ilen, subfactorial


def test_subfactorial_known_values():
    assert [subfactorial(n) for n in range(8)] == [1, 0, 1, 2, 9, 44, 265, 1854]


def test_subfactorial_matches_derangements_length():
    for n, word in enumerate(['', 'a', 'ab', 'abc', 'abcd', 'abcde']):
        assert subfactorial(n) == ilen(derangements(word))


def test_subfactorial_matches_rounded_closed_form():
    # round(n! / e) is the standard closed form for n >= 1.
    for n in range(1, 12):
        assert subfactorial(n) == round(factorial(n) / e)


def test_subfactorial_rejects_negative():
    with pytest.raises(ValueError):
        subfactorial(-1)

