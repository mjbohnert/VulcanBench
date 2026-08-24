# `iter_index` rejects negative start/stop on general iterables

`iter_index(iterable, value, start=0, stop=None)` yields the indexes at which
`value` appears in `iterable`. It has two code paths: a fast path for sequences
(objects with an `.index` method, like `str`/`list`) and a slow path for general
iterables (anything else, e.g. a generator or `iter(...)`).

Negative `start` / `stop` work on the fast path but break on the slow path:

```python
import more_itertools as mi

list(mi.iter_index("AABCADEAF", "A", start=-3))       # works -> [7]
list(mi.iter_index(iter("AABCADEAF"), "A", start=-3))  # raises instead of [7]
```

The slow path forwards `start`/`stop` to `islice`, which rejects negative indexes.

## Expected behavior

For `"AABCADEAF"` (the value `"A"` occurs at indexes 0, 1, 4, 7), both a sequence
and a general iterable of the same items must give identical results:

- `start=-3` → `[7]`
- `stop=-2` → `[0, 1, 4]`
- `start=-5, stop=-1` → `[4, 7]`

Fix the general-iterable path so negative `start` / `stop` use the usual
from-the-end semantics, matching the sequence path. Behavior with non-negative
`start` / `stop` must be unchanged.
