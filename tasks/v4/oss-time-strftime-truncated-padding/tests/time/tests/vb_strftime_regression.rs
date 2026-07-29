/*!
Regression guard: complete format strings still parse, and inputs that already
reported errors still do.

Says nothing about truncated padding modifiers, so it compiles and passes at
the base commit.
*/

use time::format_description::{parse_strftime_borrowed, parse_strftime_owned};

#[test]
fn padding_modifiers_with_a_component_parse() {
    assert!(parse_strftime_borrowed("%_d").is_ok());
    assert!(parse_strftime_borrowed("%-d").is_ok());
    assert!(parse_strftime_borrowed("%0d").is_ok());
}

#[test]
fn ordinary_format_strings_parse() {
    assert!(parse_strftime_borrowed("%Y-%m-%d").is_ok());
    assert!(parse_strftime_borrowed("%H:%M:%S").is_ok());
}

#[test]
fn lone_percent_is_already_an_error() {
    assert!(parse_strftime_borrowed("%").is_err());
}

#[test]
fn owned_parser_handles_complete_format_strings() {
    assert!(parse_strftime_owned("%Y-%m-%d").is_ok());
    assert!(parse_strftime_owned("%0d").is_ok());
}
