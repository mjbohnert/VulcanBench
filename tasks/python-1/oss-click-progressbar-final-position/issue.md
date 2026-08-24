# Progress bar can freeze below 100% depending on `update_min_steps`

`click.progressbar` supports an `update_min_steps` threshold that batches redraws so
the bar only re-renders after at least that many steps of progress. When the
threshold does not evenly divide the total work — or exceeds it — the final partial
batch is never flushed, so the bar freezes below completion.

For a length of 20 with `update_min_steps=7`, the bar stops at `14/20` and never
reaches `20/20`, even though all 20 items were processed. Thresholds of 1 or 2
(which divide 20) complete correctly.

```python
import io, click, click._termui_impl
click._termui_impl.isatty = lambda _: True
stream = io.StringIO()
with click.progressbar(range(20), show_pos=True, update_min_steps=7, file=stream) as bar:
    for _ in bar:
        pass
"20/20" in stream.getvalue()   # False — froze at 14/20
```

## Expected behavior

After all work is done, the progress bar's final render shows completion (`20/20`
for a length of 20), regardless of `update_min_steps` — including thresholds that do
not divide the length (e.g. 7) and thresholds that exceed it (e.g. 25), whether the
bar is driven by iteration or by explicit `update()`. Thresholds that already
completed (1, 2, …) are unaffected.

Fix the progress bar so the trailing progress is flushed and it always lands on its
final position.
