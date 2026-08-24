# Allow `on_setattr` hooks to be generators

An attrs `on_setattr` hook is called `(instance, attribute, value)` whenever an
attribute is set, and its return value becomes the stored value. That only lets a
hook run code *before* the assignment. There's no way to also run code *after* the
new value is in place (for logging, cross-field updates, etc.).

Allow an `on_setattr` hook to be a **generator**:

- code before the `yield` runs before the attribute is set,
- the value it `yield`s becomes the stored value,
- code after the `yield` runs once the instance already holds the new value.

```python
import attr

def hook(instance, attribute, value):
    yield value.upper()

@attr.s
class C:
    x = attr.ib(on_setattr=hook)

c = C(x="ab")
c.x = "cd"
c.x          # "CD"  (the yielded value is stored)
```

## Expected behavior

- A generator hook's yielded value overwrites the assigned value.
- Pre-yield code sees the old value; post-yield code sees the new value already set
  on the instance. For a hook that appends `("pre", instance.x)` before the yield
  and `("post", instance.x)` after, setting `x` from `"x"` to `"xxx"` records
  `[("pre", "x"), ("post", "xxx")]`.
- Ordinary (returning) hooks are unchanged: a hook that `return`s a value still
  stores that value.

Add generator support to `on_setattr` handling.
