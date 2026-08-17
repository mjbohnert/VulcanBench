# Add a `ne` (not-equal) validator to attrs

`attr.validators` provides ordering validators — `lt`, `le`, `gt`, `ge` — that
constrain an attribute's value relative to a bound. There is no validator to
forbid one specific value. Add a `ne` validator that rejects a single disallowed
value while accepting everything else.

## Expected behavior

`attr.validators.ne(val)` returns a validator that raises `ValueError` when the
attribute is set to a value equal to `val`, and accepts any other value:

```python
import attr
from attr import validators

@attr.s
class C:
    x = attr.ib(validator=validators.ne(42))

C(43)   # ok, x == 43
C(42)   # raises ValueError
```

- The forbidden value is honored even when it is falsy: `ne(0)` must reject `0`
  and accept `1`.
- Existing validators (`gt`, `ge`, `lt`, `le`, …) must be unaffected.

Implement `ne` in `attr.validators` (and export it) consistent with the existing
comparison validators.
