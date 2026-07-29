/*!
Regression guard: well-formed `strftime` directives are unaffected.

Deliberately says nothing about malformed or unsupported directives, so this
file compiles and passes at the base commit as well as after the fix.
*/

use jiff::{civil::date, Zoned};

#[test]
fn civil_date_formats_normally() {
    let d = date(2024, 7, 9);
    assert_eq!(d.strftime("%Y-%m-%d").to_string(), "2024-07-09");
}

#[test]
fn zoned_formats_normally() {
    let zdt = Zoned::UNIX_EPOCH;
    assert_eq!(zdt.strftime("%Y-%m-%d").to_string(), "1970-01-01");
}

#[test]
fn literal_text_is_preserved() {
    let d = date(2024, 7, 9);
    assert_eq!(d.strftime("day %d of month %m").to_string(), "day 09 of month 07");
}
