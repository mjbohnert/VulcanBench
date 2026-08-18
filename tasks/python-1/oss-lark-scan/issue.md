# Add `Lark.scan()` to find grammar matches inside arbitrary text

A `Lark` parser can only `parse()` a string that matches the grammar in full.
There is no way to locate the places a grammar matches *inside* a larger text —
useful for extracting structured fragments embedded in free text.

Add a `scan(text)` method that yields every non-overlapping substring of `text`
that parses as the grammar's start rule.

## Expected behavior

`Lark(...).scan(text)` yields `ScanMatch` objects, each with:

- `range`: the `(start, end)` character offsets of the match in `text`, and
- `value`: the parse tree for that substring — identical to what `parse()` would
  return for `text[start:end]`.

```python
from lark import Lark

grammar = r'''
start: "(" ITEM* ")"
ITEM: /[a-z]/
%ignore " "
'''
p = Lark(grammar, parser="lalr", start="start")

text = "xx (a b) yy (cd) ((z"
[m.range for m in p.scan(text)]   # [(3, 8), (12, 16)]  -> "(a b)", "(cd)"
list(p.scan("qwerty"))            # []  (no matches)
```

- Matches are returned left to right and do not overlap.
- Text with no match yields nothing.
- The existing `parse()` behavior is unchanged.

Implement `Lark.scan` (and export `ScanMatch`).
