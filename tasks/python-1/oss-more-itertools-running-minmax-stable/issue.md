# `running_min` / `running_max` are not stable on ties

`running_min(iterable, *, maxlen=...)` and `running_max(iterable, *, maxlen=...)`
yield the rolling minimum / maximum over a sliding window of the last `maxlen`
items. When several items in a window compare equal, these functions should be
**stable** the same way the builtins are: `min(x, y)` and `max(x, y)` return `x`
when `x == y`, i.e. the *oldest* of the equal values wins.

Right now the bounded (windowed) case keeps the *newest* equal value instead. You
can see it when equal values have different types:

```python
from fractions import Fraction
import more_itertools as mi

data = [0, 0.0, Fraction(0)]        # all equal, distinct types
list(map(type, mi.running_min(data, maxlen=2)))
# currently: [int, float, Fraction]
# expected:  [int, int, float]      # each window keeps its oldest minimum
```

## Expected behavior

- For a window containing equal values, `running_min` / `running_max` must yield
  the **oldest** equal value — matching `min` / `max` applied directly to that
  window. With `data = [0, 0.0, Fraction(0)]` and `maxlen=2`, the yielded types
  must be `[int, int, float]` for both `running_min` and `running_max`.
- The unbounded case (`maxlen=None`) is already stable and must stay so.
- Behavior on inputs with no ties (all-distinct values) must be unchanged.

Fix the windowed running-min/running-max logic so equal values keep the oldest
one, without changing behavior on non-equal inputs.
