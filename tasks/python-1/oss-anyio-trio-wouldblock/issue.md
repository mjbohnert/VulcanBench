# `CapacityLimiter` leaks `trio.WouldBlock` on the trio backend

anyio defines its own `anyio.WouldBlock` exception so that backend-agnostic code
can catch a single type regardless of the event loop in use. On the **trio**
backend, `CapacityLimiter`'s non-blocking acquire methods don't honor that: when
the limiter is full they let the underlying `trio.WouldBlock` propagate instead of
raising `anyio.WouldBlock`.

```python
import anyio
from anyio import CapacityLimiter, WouldBlock

async def main():
    limiter = CapacityLimiter(1)
    limiter.acquire_on_behalf_of_nowait(object())   # now full
    try:
        limiter.acquire_nowait()
    except WouldBlock:
        print("caught anyio.WouldBlock")            # does not happen on trio today

anyio.run(main, backend="trio")
```

## Expected behavior

On the trio backend, when the limiter has no free capacity:

- `CapacityLimiter.acquire_nowait()` raises `anyio.WouldBlock`.
- `CapacityLimiter.acquire_on_behalf_of_nowait(borrower)` raises `anyio.WouldBlock`.

Unchanged:

- When capacity is available, the non-blocking acquire succeeds without raising.
- The asyncio backend already raises `anyio.WouldBlock` and must continue to.

Fix the trio backend's `CapacityLimiter` so its non-blocking acquire methods raise
`anyio.WouldBlock` rather than leaking `trio.WouldBlock`.
