"""Regression guard: existing combinatoric helpers are unaffected.

Mentions nothing about subfactorial, so it imports and passes at the base
commit.
"""

from more_itertools import derangements, ilen, distinct_permutations


def test_derangements_basic():
    assert sorted(''.join(d) for d in derangements('abc')) == ['bca', 'cab']


def test_derangements_length_unchanged():
    assert ilen(derangements('abcd')) == 9
    assert ilen(derangements('epsilon')) == 1854


def test_distinct_permutations_unchanged():
    assert sorted(''.join(p) for p in distinct_permutations('aab')) == ['aab', 'aba', 'baa']
