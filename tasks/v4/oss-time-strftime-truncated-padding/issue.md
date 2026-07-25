# `parse_strftime_*` panics on a truncated padding modifier

A strftime format string may use a padding modifier — `%_` (space-pad), `%-`
(no pad) or `%0` (zero-pad) — before a component byte, as in `%_d`.

When the format string **ends immediately after the modifier**, there is no
component byte. The tokenizer reads the component position without first
checking that it exists, so parsing panics with an index-out-of-bounds instead
of returning an error:

```rust
time::format_description::parse_strftime_borrowed("%_"); // panics
```

A lone `%` at the end of the input is already handled and returns an error;
only the padding-modifier forms panic.

## Expected behaviour

A format string that ends after a padding modifier must return the same kind of
`Err` the parser already produces for other malformed input. Parsing must never
panic. Format strings where the modifier is followed by a component, and all
other well-formed inputs, are unaffected.

Both `parse_strftime_borrowed` and `parse_strftime_owned` share the tokenizer
and must behave the same way.

## Acceptance examples

```rust
use time::format_description::{parse_strftime_borrowed, parse_strftime_owned};

// Truncated padding modifiers: an error, not a panic.
assert!(parse_strftime_borrowed("%_").is_err());
assert!(parse_strftime_borrowed("%-").is_err());
assert!(parse_strftime_borrowed("%0").is_err());

// It may also appear at the end of a longer format string.
assert!(parse_strftime_borrowed("%Y-%m-%d %_").is_err());

// The owned parser behaves identically.
assert!(parse_strftime_owned("%_").is_err());

// Unaffected: a modifier followed by a component still parses.
assert!(parse_strftime_borrowed("%_d").is_ok());
assert!(parse_strftime_borrowed("%-d").is_ok());
assert!(parse_strftime_borrowed("%0d").is_ok());
assert!(parse_strftime_borrowed("%Y-%m-%d").is_ok());

// Unaffected: a lone `%` was already an error.
assert!(parse_strftime_borrowed("%").is_err());
```

The tests assert only that an error is returned, never its message.
