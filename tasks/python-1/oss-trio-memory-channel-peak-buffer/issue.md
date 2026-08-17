# Track peak buffer usage in memory-channel statistics

`trio.open_memory_channel()` exposes runtime `statistics()` about the channel:
`current_buffer_used`, `open_send_channels`, `tasks_waiting_send`, and so on. There
is no way to see the **high-water mark** — the most items the buffer has ever held
at once — which is useful for tuning `max_buffer_size`.

Add a `peak_buffer_used` statistic that records the largest number of items the
buffer has held since the channel was created, and does **not** decrease when items
are received.

## Expected behavior

```python
import trio

async def main():
    send, recv = trio.open_memory_channel(5)
    assert send.statistics().peak_buffer_used == 0
    send.send_nowait(1)
    send.send_nowait(2)
    assert send.statistics().peak_buffer_used == 2
    recv.receive_nowait()
    recv.receive_nowait()
    assert send.statistics().current_buffer_used == 0   # drained
    assert send.statistics().peak_buffer_used == 2       # high-water mark retained

trio.run(main)
```

- A fresh channel reports `peak_buffer_used == 0`.
- Sending items raises `peak_buffer_used` to the maximum simultaneous buffer depth.
- Draining the buffer leaves `peak_buffer_used` unchanged.
- Existing statistics (`current_buffer_used`, `open_send_channels`, …) are
  unaffected.

Expose `peak_buffer_used` on the memory-channel statistics.
