/*!
Hidden grader tests for lenient `strftime` formatting.

Every expected value here is generated from the gold patch: the `Display`
implementation returned by `<type>::strftime` must never panic, and unsupported
or malformed directives must round-trip into the output verbatim.
*/

use jiff::{civil::date, Zoned};

/// A trailing bare `%` must be emitted literally instead of panicking.
#[test]
fn trailing_percent_is_literal() {
    let zdt = Zoned::UNIX_EPOCH;
    assert_eq!(zdt.strftime("%Y %").to_string(), "1970 %");
}

/// An unrecognized directive must be emitted verbatim, sign included.
#[test]
fn unknown_directive_is_literal() {
    let zdt = Zoned::UNIX_EPOCH;
    assert_eq!(zdt.strftime("%Y %J").to_string(), "1970 %J");
}

/// A format string consisting solely of `%` must format to `%`.
#[test]
fn lone_percent_is_literal() {
    let zdt = Zoned::UNIX_EPOCH;
    assert_eq!(zdt.strftime("%").to_string(), "%");
}

/// A directive requiring a field the type does not carry (a civil `Date` has no
/// offset) must be emitted verbatim rather than panicking.
#[test]
fn missing_field_directive_is_literal() {
    let d = date(2024, 7, 9);
    assert_eq!(d.strftime("%z").to_string(), "%z");
}

/// Lenient formatting is not specific to `Zoned`: civil types behave the same.
#[test]
fn civil_date_trailing_percent_is_literal() {
    let d = date(2024, 7, 9);
    assert_eq!(d.strftime("%Y %").to_string(), "2024 %");
}
