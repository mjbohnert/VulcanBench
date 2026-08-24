# `click.style()` mishandles some color arguments

`click.style(text, fg=..., bg=...)` wraps text in ANSI color codes. Two problems
with how it handles the color arguments:

1. The 256-color index `0` (black) is silently dropped. `click.style("x", fg=0)`
   produces no foreground color code at all, because the code treats the color as
   a plain truthiness check and `0` is falsy.
2. Invalid color values are not validated consistently. An out-of-range palette
   index such as `fg=999` emits a nonsense escape code instead of being rejected,
   and an unknown color name raises `TypeError` rather than a value error.

## Expected behavior

- `click.style("x", fg=0)` must include the 256-color code for index 0 — the
  output must contain `38;5;0` (and `bg=0` must contain `48;5;0`).
- An invalid color must raise `ValueError`: both an unknown color **name**
  (e.g. `fg="chartreuse-ish"`) and an out-of-range 256-color **index**
  (e.g. `fg=999`, outside 0–255).
- Valid inputs are unchanged: a known name like `fg="red"` and an RGB triple like
  `fg=(255, 0, 0)` must still produce their usual codes.

Fix the color handling in `style()` so index `0` is honored and invalid colors are
rejected with `ValueError`, without changing behavior for valid names, indices, or
RGB triples.
