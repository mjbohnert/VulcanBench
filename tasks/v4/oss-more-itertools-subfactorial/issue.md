# Add `subfactorial()`

`more_itertools` provides `derangements()`, which yields every permutation of a
sequence that leaves no element in its original position. There is no direct way
to compute *how many* such permutations exist without enumerating them.

The standard library pairs each combinatoric iterator with a counting function —
`math.prod` for `product`, `math.comb` for `combinations`, `math.perm` for
`permutations`. `derangements()` has no counterpart.

## Expected behaviour

Add a public `subfactorial(n)` that returns the number of permutations of *n*
elements with no fixed points — the length of `derangements()` over an *n*-element
sequence — computed directly rather than by enumeration.

The values are OEIS A000166:

```
n            0  1  2  3  4   5    6     7
subfactorial 1  0  1  2  9  44  265  1854
```

For `n >= 1` this equals the closed form `round(math.factorial(n) / math.e)`.
A negative *n* raises `ValueError`.

## Acceptance examples

```python
from math import e, factorial
from more_itertools import derangements, ilen, subfactorial

assert [subfactorial(n) for n in range(8)] == [1, 0, 1, 2, 9, 44, 265, 1854]

# Agrees with the length of derangements().
assert subfactorial(4) == ilen(derangements('abcd')) == 9
assert subfactorial(7) == ilen(derangements('epsilon')) == 1854

# Agrees with the rounded closed form for n >= 1.
assert all(subfactorial(n) == round(factorial(n) / e) for n in range(1, 12))

# Negative input is rejected.
# subfactorial(-1) raises ValueError
```

Existing helpers (`derangements`, `distinct_permutations`) are unchanged.
