"""Hidden behavioral tests for oss-anyio-fail-at-deadline (anyio #1228).

anyio gains deadline-based timeout helpers ``fail_at(deadline)`` and
``move_on_at(deadline)`` — absolute-time analogues of the existing delay-based
``fail_after`` / ``move_on_after``. Graded through the public anyio API under
``anyio.run``. Deadlines are computed from ``anyio.current_time()`` with generous
margins to stay robust.
"""

from __future__ import annotations

import anyio
import pytest


# --- fail_to_pass: the deadline-based helpers did not exist at the base commit -


def test_fail_at_raises_timeout_when_deadline_passes() -> None:
    async def main() -> None:
        deadline = anyio.current_time() + 0.05
        with pytest.raises(TimeoutError):
            with anyio.fail_at(deadline):
                await anyio.sleep(5)

    anyio.run(main)


def test_fail_at_completes_when_deadline_is_far() -> None:
    async def main() -> None:
        deadline = anyio.current_time() + 10
        with anyio.fail_at(deadline):
            await anyio.sleep(0.01)  # finishes well before the deadline

    anyio.run(main)  # must not raise


def test_move_on_at_cancels_at_deadline_without_raising() -> None:
    async def main() -> None:
        deadline = anyio.current_time() + 0.05
        with anyio.move_on_at(deadline) as scope:
            await anyio.sleep(5)
        assert scope.cancelled_caught is True

    anyio.run(main)


# --- pass_to_pass: the delay-based helpers are unchanged -----------------------


def test_fail_after_still_raises_timeout() -> None:
    async def main() -> None:
        with pytest.raises(TimeoutError):
            with anyio.fail_after(0.05):
                await anyio.sleep(5)

    anyio.run(main)


def test_move_on_after_still_cancels() -> None:
    async def main() -> None:
        with anyio.move_on_after(0.05) as scope:
            await anyio.sleep(5)
        assert scope.cancelled_caught is True

    anyio.run(main)
