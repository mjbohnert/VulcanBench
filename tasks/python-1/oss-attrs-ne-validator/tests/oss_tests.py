"""Hidden behavioral tests for oss-attrs-ne-validator (attrs #1571).

Graded on the observable behavior of the new ``attr.validators.ne`` validator via
the public attrs API: an attribute so validated accepts unequal values and rejects
the forbidden value with ValueError. Existing validators must be unaffected.
"""

from __future__ import annotations

import attr
import pytest
from attr import validators


# --- fail_to_pass: the ``ne`` validator did not exist at the base commit ------


def test_ne_allows_unequal_value() -> None:
    @attr.s
    class C:
        x = attr.ib(validator=validators.ne(42))

    assert C(43).x == 43


def test_ne_rejects_equal_value() -> None:
    @attr.s
    class C:
        x = attr.ib(validator=validators.ne(42))

    with pytest.raises(ValueError):
        C(42)


def test_ne_zero_is_a_real_bound() -> None:
    """The forbidden value 0 must be honored (not treated as "no bound")."""

    @attr.s
    class C:
        x = attr.ib(validator=validators.ne(0))

    assert C(1).x == 1
    with pytest.raises(ValueError):
        C(0)


# --- pass_to_pass: existing validators unaffected -----------------------------


def test_gt_validator_unaffected() -> None:
    @attr.s
    class C:
        x = attr.ib(validator=validators.gt(0))

    assert C(1).x == 1
    with pytest.raises(ValueError):
        C(0)


def test_ge_validator_unaffected() -> None:
    @attr.s
    class C:
        x = attr.ib(validator=validators.ge(5))

    assert C(5).x == 5
    with pytest.raises(ValueError):
        C(4)
