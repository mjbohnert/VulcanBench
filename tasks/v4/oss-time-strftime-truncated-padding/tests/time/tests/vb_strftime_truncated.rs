/*!
Hidden grader tests for truncated strftime padding modifiers.

A strftime format string that ends immediately after a padding modifier
(`%_`, `%-`, `%0`) has no component byte following it. Parsing such a string
must report an error through the normal `Result` channel rather than panicking
on an out-of-bounds index.

Assertions check only that an error is returned -- never its text -- and go
through the public `parse_strftime_borrowed` / `parse_strftime_owned` APIs.
*/

use time::format_description::{parse_strftime_borrowed, parse_strftime_owned};

#[test]
fn underscore_padding_without_component_is_error() {
    assert!(parse_strftime_borrowed("%_").is_err());
}

#[test]
fn hyphen_padding_without_component_is_error() {
    assert!(parse_strftime_borrowed("%-").is_err());
}

#[test]
fn zero_padding_without_component_is_error() {
    assert!(parse_strftime_borrowed("%0").is_err());
}

/// The truncated modifier may sit at the end of a longer format string.
#[test]
fn trailing_truncated_padding_after_valid_components_is_error() {
    assert!(parse_strftime_borrowed("%Y-%m-%d %_").is_err());
}

/// The owned parser shares the tokenizer and must behave identically.
#[test]
fn owned_parser_rejects_truncated_padding() {
    assert!(parse_strftime_owned("%_").is_err());
    assert!(parse_strftime_owned("%-").is_err());
    assert!(parse_strftime_owned("%0").is_err());
}
