# `manualintegrate` leaves some rational functions unevaluated

`sympy.integrals.manualintegrate.manualintegrate` integrates step by step. For
rational functions it relies on a partial-fractions rule, but when `apart` cannot
decompose the integrand any further, there is no fallback — so it gives up and
returns an unevaluated `Integral` for rational functions it should be able to
handle.

```python
from sympy import symbols
from sympy.integrals.manualintegrate import manualintegrate

x = symbols("x")
manualintegrate(1 / (x**4 + 1), x)   # returns an unevaluated Integral
```

`ratint` (the general rational-function integrator) handles these.

## Expected behavior

`manualintegrate` should fully integrate rational functions, using `ratint` as a
fallback when partial fractions cannot decompose the integrand further. For each of

- `1 / (x**4 + 1)`
- `(x**2 + 1) / (x**4 + 1)`
- `1 / (x**4 - x**2 + 1)`

the result must contain no unevaluated `Integral`, and differentiating it must give
back the original integrand.

Rational functions that already integrate (e.g. `1/(x**3 + 1)`,
`1/(x**2 + x + 1)`) must keep working and stay correct.

Add a rational-integration fallback so `manualintegrate` no longer leaves these
rational functions unevaluated.
