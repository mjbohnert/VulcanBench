# `numeric_range` equality/hashing disagrees with `range` for single-element ranges

`numeric_range` is meant to behave like the built-in `range`, including how
instances compare and hash. Built-in `range` treats two ranges as equal when they
produce the same sequence of values — and for a **single-element** range the step
is irrelevant (`range(0, 1, 1) == range(0, 1, 5)` is `True`).

`numeric_range` gets this wrong: two single-element ranges with the same start but
different step compare unequal, and hash differently.

```python
from decimal import Decimal as D
from more_itertools import numeric_range

a = numeric_range(D(0), D(1), D(1))   # [0]
b = numeric_range(D(0), D(1), D(5))   # [0]
a == b            # False  (should be True)
hash(a) == hash(b)  # False
```

## Expected behavior

Mirror built-in `range` semantics:

- Two `numeric_range`s are equal when they yield the same values. For a
  single-element range, the step does not matter: `numeric_range(0, 1, 1)` equals
  `numeric_range(0, 1, 5)`.
- Equal `numeric_range`s must hash equal.
- Multi-element ranges and unequal ranges are unchanged (still compare by start,
  step, and length as appropriate).

Fix `numeric_range.__eq__` and `__hash__` so equality and hashing match built-in
`range`.
