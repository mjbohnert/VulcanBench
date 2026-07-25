# `strftime` panics on unsupported or malformed format strings

Every `strftime` method in this crate (`Date::strftime`, `Time::strftime`,
`DateTime::strftime`, `Timestamp::strftime`, `Zoned::strftime`) returns a value
implementing `std::fmt::Display`. `Display` has no way to report an error, so
whenever formatting fails the implementation panics — converting the returned
value to a `String` blows up rather than producing output.

Formatting fails in two situations:

1. the format string is malformed or uses a directive the crate doesn't
   recognise (a trailing bare `%`, `%J`), and
2. the format string uses a directive requiring a field the value doesn't carry
   (`%z` needs an offset, which a civil `Date` has no notion of).

Both are easy to hit by accident, and the result is a panic from what reads like
ordinary string formatting.

## Expected behaviour

The `Display` implementation returned by the `strftime` methods must format in a
**lenient mode**: formatting must never fail, and therefore never panic. Any
directive that cannot be rendered — because it is unrecognised, incomplete, or
requires an absent field — is emitted into the output **verbatim**, including its
leading `%`. Well-formed directives are unaffected.

## Acceptance examples

```rust
use jiff::{civil::date, Zoned};

let zdt = Zoned::UNIX_EPOCH;

// A trailing bare `%` is emitted literally.
assert_eq!(zdt.strftime("%Y %").to_string(), "1970 %");

// An unrecognised directive is emitted verbatim.
assert_eq!(zdt.strftime("%Y %J").to_string(), "1970 %J");

// A format string that is only `%` formats to `%`.
assert_eq!(zdt.strftime("%").to_string(), "%");

// `%z` needs an offset; a civil date has none, so it is emitted verbatim.
let d = date(2024, 7, 9);
assert_eq!(d.strftime("%z").to_string(), "%z");

// Leniency is not specific to `Zoned`.
assert_eq!(d.strftime("%Y %").to_string(), "2024 %");

// Well-formed directives are unchanged.
assert_eq!(d.strftime("%Y-%m-%d").to_string(), "2024-07-09");
```

None of the above may panic.
