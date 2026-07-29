/*!
Regression guard: ordinary offsets format and round-trip as they always have.

Every offset here is below the rounding window that rolls over to a full day,
so this file asserts only long-standing behaviour and compiles and passes at
the base commit.
*/

use chrono::{DateTime, FixedOffset, NaiveDate, TimeZone};

fn dt_at(secs: i32) -> DateTime<FixedOffset> {
    let off = FixedOffset::east_opt(secs).expect("offset within FixedOffset range");
    let naive = NaiveDate::from_ymd_opt(2024, 7, 9)
        .unwrap()
        .and_hms_opt(12, 0, 0)
        .unwrap();
    off.from_utc_datetime(&naive)
}

#[test]
fn whole_minute_offsets_format_normally() {
    assert_eq!(dt_at(3_600).format("%z").to_string(), "+0100");
    assert_eq!(dt_at(5_400).format("%:z").to_string(), "+01:30");
    assert_eq!(dt_at(-18_000).format("%z").to_string(), "-0500");
}

#[test]
fn utc_offset_formats_normally() {
    assert_eq!(dt_at(0).format("%z").to_string(), "+0000");
    assert_eq!(dt_at(0).format("%:z").to_string(), "+00:00");
}

#[test]
fn ordinary_offset_round_trips_through_rfc3339() {
    let formatted = dt_at(5_400).to_rfc3339();
    assert!(formatted.ends_with("+01:30"), "got {formatted}");
    assert!(DateTime::parse_from_rfc3339(&formatted).is_ok(), "got {formatted}");
}

#[test]
fn seconds_below_the_rounding_window_round_down() {
    // 23:59:29 rounds down to 23:59; this never reached the roll-over path.
    assert_eq!(dt_at(86_369).format("%:z").to_string(), "+23:59");
}
