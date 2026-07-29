# Wrong match reported when a suffix/inner literal scan finds a later candidate first

A regex with no usable *prefix* literal but an extractable *suffix* or *inner*
literal is matched by scanning the haystack for that literal to produce
candidate positions, then confirming each candidate with a search.

When the first candidate confirms a match that starts **later** than a match
confirmed by a subsequent candidate, the engine returns the first one. Under
leftmost-first semantics the earlier-starting match is the correct answer.

A minimal reproducer is the pattern `.bb|b` on the haystack `zabb`: the reported
match is `2..3` (`"b"`), but the leftmost match is `1..4` (`"abb"`).

Triggering the bug requires a specific combination:

1. no prefix literal that would activate a standard prefix scan,
2. an extractable suffix or inner literal,
3. a match actually present in the haystack, and
4. a first literal-scan candidate whose confirmed match starts after that of a
   match confirmed by a later candidate.

Because of (3), this never produces a false positive or false negative — the
bug is strictly about which span is reported.

## Expected behaviour

When candidates are produced by a suffix or inner literal scan, the reported
match must be the leftmost one, matching what a straightforward leftmost-first
search would return. Patterns with a usable prefix literal, and patterns whose
first candidate already corresponds to the leftmost match, are unaffected.

## Acceptance examples

```rust
use regex::Regex;

fn span(pattern: &str, haystack: &str) -> (usize, usize) {
    let m = Regex::new(pattern).unwrap().find(haystack).unwrap();
    (m.start(), m.end())
}

assert_eq!(span(r".abb|b", "zabb"), (0, 4));
assert_eq!(span(r".bb|b", "zabb"), (1, 4));
assert_eq!(span(r".abb|b", "zzzabbz"), (2, 6));
assert_eq!(span(r"\s+\w+bb|b", " zabb"), (0, 5));
assert_eq!(span(r"(?:[a-wyz]{3}|[a-wyz]).b", "xaaabb"), (1, 6));

// The capture and iteration APIs must agree.
let re = Regex::new(r".bb|b").unwrap();
let m = re.captures("zabb").unwrap().get(0).unwrap();
assert_eq!((m.start(), m.end()), (1, 4));
assert_eq!(re.find_iter("zabb").next().map(|m| (m.start(), m.end())), Some((1, 4)));

// Unaffected: a usable prefix literal, and a haystack with no match.
assert_eq!(span(r"abc|b", "zabcb"), (1, 4));
assert_eq!(Regex::new(r".bb|b").unwrap().find("zacc"), None);
```
