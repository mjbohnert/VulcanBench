# Add absolute-deadline timeout helpers `fail_at` / `move_on_at`

anyio provides delay-based timeout context managers: `fail_after(delay)` raises
`TimeoutError` if the block takes longer than `delay` seconds, and
`move_on_after(delay)` silently cancels the block after `delay` seconds. Both take a
*relative* delay.

When you already have an absolute time to stop at (a deadline computed from
`anyio.current_time()`), you must convert it back to a delay. Add the deadline-based
counterparts.

## Expected behavior

- `anyio.fail_at(deadline)`: a context manager that raises `TimeoutError` if the
  enclosed code has not finished by the absolute time `deadline` (as measured by
  `anyio.current_time()`); if it finishes in time, no exception is raised.
- `anyio.move_on_at(deadline)`: a context manager that cancels the enclosed code at
  `deadline` without raising, exposing `cancelled_caught == True` on its cancel
  scope when the deadline fired.
- Passing `None` as the deadline disables the timeout.
- The existing `fail_after` / `move_on_after` are unchanged.

```python
import anyio

async def main():
    deadline = anyio.current_time() + 0.05
    with anyio.move_on_at(deadline) as scope:
        await anyio.sleep(5)
    assert scope.cancelled_caught

anyio.run(main)
```

Implement `fail_at` and `move_on_at` and export them from the `anyio` package.
