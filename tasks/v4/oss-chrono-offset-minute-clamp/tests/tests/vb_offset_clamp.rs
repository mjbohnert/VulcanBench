/*!
Hidden grader tests for offset-minute rounding at the top of the `FixedOffset`
range.

`FixedOffset` accepts up to 23:59:59. Formatting at minute precision rounds to
the nearest minute, so every offset from 23:59:30 up must still render as
`23:59` — never `24:00`, which is not a valid offset hour and does not parse
back. All expected values are generated from the gold patch, and every
assertion goes through public API (`format`, `to_rfc3339`, `to_rfc2822`,
`Display`, `parse_from_rfc3339`).
*/

use chrono::{DateTime, FixedOffset, NaiveDate, TimeZone};

/// 23:59:59 east — the largest representable `FixedOffset`.
const MAX_EAST: i32 = 86_399;
/// 23:59:30 east — the bottom of the window that rounds up to a full day.
const ROUND_UP_EAST: i32 = 86_370;

fn dt_at(secs: i32) -> DateTime<FixedOffset> {
    let off = FixedOffset::east_opt(secs).expect("offset within FixedOffset range");
    let naive = NaiveDate::from_ymd_opt(2024, 7, 9)
        .unwrap()
        .and_hms_opt(12, 0, 0)
        .unwrap();
    off.from_utc_datetime(&naive)
}

#[test]
fn z_directive_clamps_at_max_offset() {
    assert_eq!(dt_at(MAX_EAST).format("%z").to_string(), "+2359");
}

#[test]
fn colon_z_directive_clamps_at_max_offset() {
    assert_eq!(dt_at(MAX_EAST).format("%:z").to_string(), "+23:59");
}

#[test]
fn clamps_at_bottom_of_rounding_window() {
    assert_eq!(dt_at(ROUND_UP_EAST).format("%:z").to_string(), "+23:59");
}

#[test]
fn negative_offset_clamps_at_max_offset() {
    assert_eq!(dt_at(-MAX_EAST).format("%z").to_string(), "-2359");
}

#[test]
fn rfc3339_round_trips_at_max_offset() {
    let formatted = dt_at(MAX_EAST).to_rfc3339();
    assert!(
        formatted.ends_with("+23:59"),
        "expected a +23:59 offset, got {formatted}"
    );
    assert!(
        DateTime::parse_from_rfc3339(&formatted).is_ok(),
        "formatted value must parse back, got {formatted}"
    );
}

#[test]
fn rfc2822_clamps_at_max_offset() {
    let formatted = dt_at(MAX_EAST).to_rfc2822();
    assert!(
        formatted.ends_with("+2359"),
        "expected a +2359 offset, got {formatted}"
    );
}
