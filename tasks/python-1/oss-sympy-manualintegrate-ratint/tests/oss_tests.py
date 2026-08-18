"""Hidden behavioral tests for oss-sympy-manualintegrate-ratint (sympy #30144).

``manualintegrate`` left some rational functions unevaluated because its
partial-fractions path could not decompose them further. Adding ``ratint`` as a
fallback lets it finish. Graded on the public ``manualintegrate`` result: it must
be fully evaluated (no residual ``Integral``) and correct (its derivative equals
the integrand).
"""

from __future__ import annotations

from sympy import Integral, diff, simplify, symbols
from sympy.integrals.manualintegrate import manualintegrate

x = symbols("x")


def _is_correct_closed_form(integrand) -> bool:
    result = manualintegrate(integrand, x)
    if result.has(Integral):
        return False
    return simplify(diff(result, x) - integrand) == 0


# --- fail_to_pass: left unevaluated at the base commit ------------------------


def test_quartic_denominator_rational() -> None:
    assert _is_correct_closed_form(1 / (x**4 + 1))


def test_biquadratic_numerator_rational() -> None:
    assert _is_correct_closed_form((x**2 + 1) / (x**4 + 1))


def test_cyclotomic_like_denominator_rational() -> None:
    assert _is_correct_closed_form(1 / (x**4 - x**2 + 1))


# --- pass_to_pass: already integrable, must stay correct ----------------------


def test_cubic_denominator_still_integrates() -> None:
    assert _is_correct_closed_form(1 / (x**3 + 1))


def test_irreducible_quadratic_still_integrates() -> None:
    assert _is_correct_closed_form(1 / (x**2 + x + 1))
