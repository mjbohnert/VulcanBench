"""Hidden behavioral tests for oss-trio-memory-channel-peak-buffer (trio #3474).

Memory-channel statistics gain a ``peak_buffer_used`` field: the high-water mark of
how many items the buffer has held at once, which must NOT reset when the buffer is
drained. Graded through the public ``open_memory_channel().statistics()`` API,
driven under ``trio.run``.
"""

from __future__ import annotations

import trio


# --- fail_to_pass: peak_buffer_used did not exist at the base commit ----------


def test_peak_starts_at_zero() -> None:
    async def main() -> None:
        send, _recv = trio.open_memory_channel(5)
        assert send.statistics().peak_buffer_used == 0

    trio.run(main)


def test_peak_tracks_maximum_buffer() -> None:
    async def main() -> None:
        send, _recv = trio.open_memory_channel(5)
        send.send_nowait(1)
        send.send_nowait(2)
        assert send.statistics().peak_buffer_used == 2

    trio.run(main)


def test_peak_survives_draining() -> None:
    async def main() -> None:
        send, recv = trio.open_memory_channel(5)
        send.send_nowait(1)
        send.send_nowait(2)
        assert recv.receive_nowait() == 1
        assert recv.receive_nowait() == 2
        stats = send.statistics()
        assert stats.current_buffer_used == 0  # buffer is empty again
        assert stats.peak_buffer_used == 2  # but the high-water mark is retained

    trio.run(main)


# --- pass_to_pass: existing statistics unaffected -----------------------------


def test_current_buffer_used_still_tracks_live_count() -> None:
    async def main() -> None:
        send, recv = trio.open_memory_channel(5)
        send.send_nowait(1)
        assert send.statistics().current_buffer_used == 1
        recv.receive_nowait()
        assert send.statistics().current_buffer_used == 0

    trio.run(main)


def test_open_channel_counts_unaffected() -> None:
    async def main() -> None:
        send, _recv = trio.open_memory_channel(5)
        send2 = send.clone()
        assert send.statistics().open_send_channels == 2
        send2.close()
        assert send.statistics().open_send_channels == 1

    trio.run(main)
