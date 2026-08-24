// Hidden pass_to_pass regression guard for oss-toml-writer-quote-count-overflow.
//
// Bounding the quote-run counter must not change how ordinary short strings are
// serialized. These hold at the base commit and after the fix. Run with
// `cargo test --offline`.

use toml_writer::ToTomlValue;

#[test]
fn plain_string_is_basic_quoted() {
    assert_eq!("hello".to_toml_value(), "\"hello\"");
}

#[test]
fn string_with_space_is_basic_quoted() {
    assert_eq!("a b".to_toml_value(), "\"a b\"");
}
