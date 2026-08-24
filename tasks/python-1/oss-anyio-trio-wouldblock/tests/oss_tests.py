"""Hidden behavioral tests for oss-anyio-trio-wouldblock (anyio #1218).

On the trio backend, ``CapacityLimiter.acquire_nowait`` /
``acquire_on_behalf_of_nowait`` leaked ``trio.WouldBlock`` when the limiter was
full, instead of anyio's own ``anyio.WouldBlock``. Callers writing
backend-agnostic code catch ``anyio.WouldBlock``, so the leak broke them.

Graded through the public anyio API, running on the trio backend via
``anyio.run(..., backend="trio")``. The limiter is filled by a *different*
borrower so the follow-up nowait acquire legitimately has no capacity.
"""

from __future__ import annotations

import anyio
import pytest
from anyio import CapacityLimiter, WouldBlock


def _run_trio(func) -> None:
    anyio.run(func, backend="trio")


# --- fail_to_pass: trio backend leaked trio.WouldBlock at the base commit -----


def test_acquire_nowait_raises_anyio_wouldblock() -> None:
    async def main() -> None:
        limiter = CapacityLimiter(1)
        limiter.acquire_on_behalf_of_nowait(object())  # full, held by another borrower
        with pytest.raises(WouldBlock):
            limiter.acquire_nowait()

    _run_trio(main)


def test_acquire_on_behalf_of_nowait_raises_anyio_wouldblock() -> None:
    async def main() -> None:
        limiter = CapacityLimiter(1)
        limiter.acquire_on_behalf_of_nowait(object())
        with pytest.raises(WouldBlock):
            limiter.acquire_on_behalf_of_nowait(object())

    _run_trio(main)


def test_multi_token_limiter_raises_anyio_wouldblock_when_exhausted() -> None:
    async def main() -> None:
        limiter = CapacityLimiter(2)
        limiter.acquire_on_behalf_of_nowait(object())
        limiter.acquire_on_behalf_of_nowait(object())
        with pytest.raises(WouldBlock):
            limiter.acquire_on_behalf_of_nowait(object())

    _run_trio(main)


# --- pass_to_pass: unchanged behavior -----------------------------------------


def test_nowait_succeeds_when_capacity_available() -> None:
    async def main() -> None:
        limiter = CapacityLimiter(2)
        limiter.acquire_on_behalf_of_nowait(object())
        limiter.acquire_nowait()  # capacity remains; must not raise

    _run_trio(main)


def test_asyncio_backend_already_raises_anyio_wouldblock() -> None:
    """The asyncio backend already raised anyio.WouldBlock; keep it that way."""

    async def main() -> None:
        limiter = CapacityLimiter(1)
        limiter.acquire_on_behalf_of_nowait(object())
        with pytest.raises(WouldBlock):
            limiter.acquire_on_behalf_of_nowait(object())

    anyio.run(main, backend="asyncio")
