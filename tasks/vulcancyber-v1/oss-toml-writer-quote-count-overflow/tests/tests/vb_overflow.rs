// Hidden fail_to_pass tests for oss-toml-writer-quote-count-overflow (toml-rs/toml PR #1189).
//
// When choosing how to quote a TOML string, the writer counts the longest run of
// consecutive single/double quotes in the value. Those counters are u8, and each
// run character is added with `+= 1` without any bound, so a value containing 256
// or more consecutive quote characters overflows the counter. In a debug build
// that overflow panics; a single attacker-influenced string being serialized can
// therefore crash the writer -- a denial-of-service. The fix accumulates the run
// length with a saturating counter so it can never overflow.
//
// At the base commit each call below panics (attempt to add with overflow), so the
// test fails; after the fix it returns the correct TOML representation. Run with
// `cargo test --offline`.

use toml_writer::ToTomlValue;

#[test]
fn long_double_quote_run_serializes_without_overflow() {
    let s = "\"".repeat(256);
    // No single quotes in the value, so it is emitted as a literal string '...'.
    assert_eq!(s.to_toml_value(), format!("'{s}'"));
}

#[test]
fn long_single_quote_run_serializes_without_overflow() {
    let s = "'".repeat(256);
    // Contains single quotes, so it falls back to a basic string "...".
    assert_eq!(s.to_toml_value(), format!("\"{s}\""));
}

#[test]
fn very_long_double_quote_run_serializes_without_overflow() {
    let s = "\"".repeat(300);
    assert_eq!(s.to_toml_value(), format!("'{s}'"));
}
