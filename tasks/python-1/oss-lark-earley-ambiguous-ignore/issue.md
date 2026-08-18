# Earley parser crashes on ambiguity introduced by ignored tokens

With the dynamic (Earley) lexer, a token that is `%ignore`d can also be a prefix of
a real token, so a single input can be read several different ways. Instead of
reporting that ambiguity, the parser crashes:

```python
from lark import Lark

grammar = r'''
!start: "foo1" | "foo" | "foo12"
%ignore "1"
%ignore "2"
'''
Lark(grammar, ambiguity="explicit").parse("foo12")
# RuntimeError: Earley should not generate multiple start symbol items! ...
```

`"foo12"` can be read as `foo` (+ ignored `12`), `foo1` (+ ignored `2`), or `foo12`.

## Expected behavior

- With `ambiguity="explicit"`, `parse("foo12")` returns an `_ambig` tree containing
  all three readings (`foo`, `foo1`, `foo12`) — no crash.
- The same holds when the ambiguity is inside a rule body (e.g.
  `!start: a "b"` with `!a: "a" | "a1" | "a12"` and ignored `1`/`2`, parsing
  `"a12b"` → three readings).
- With `ambiguity="resolve"`, `parse("foo12")` returns a single resolved tree.
- Unambiguous inputs are unaffected.

Fix the dynamic Earley parser so ambiguity arising from ignored tokens is produced
as an ambiguity tree instead of crashing.
