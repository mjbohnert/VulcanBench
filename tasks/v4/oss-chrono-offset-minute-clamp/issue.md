# Offsets near 24:00 format as `+24:00` and no longer parse back

`FixedOffset` accepts any offset up to 23:59:59. When a `DateTime<FixedOffset>`
is formatted at **minute precision**, the offset's seconds are rounded to the
nearest minute first. Rounding 23:59:30 (or anything above it, up to 23:59:59)
produces 1440 minutes, which is printed as `+24:00`.

An offset hour is only valid as `00`–`23`. `DateTime::parse_from_rfc3339`
rejects `+24:00` with `OutOfRange`, so a value that chrono itself formatted can
no longer be read back by chrono.

Every minute-precision path is affected: the `%z` and `%:z` format directives,
`to_rfc3339`, and `to_rfc2822`.

## Expected behaviour

Rounding the offset to whole minutes must never roll over to a full day. An
offset in the 23:59:30–23:59:59 range must format as `23:59`, so the hour stays
below 24 and the formatted value round-trips. Offsets below that window are
unaffected and must keep rounding exactly as before.

## Acceptance examples

```rust
use chrono::{DateTime, FixedOffset, NaiveDate, TimeZone};

fn dt_at(secs: i32) -> DateTime<FixedOffset> {
    let off = FixedOffset::east_opt(secs).unwrap();
    let naive = NaiveDate::from_ymd_opt(2024, 7, 9).unwrap().and_hms_opt(12, 0, 0).unwrap();
    off.from_utc_datetime(&naive)
}

// 23:59:59 — the largest representable offset.
assert_eq!(dt_at(86_399).format("%z").to_string(), "+2359");
assert_eq!(dt_at(86_399).format("%:z").to_string(), "+23:59");

// 23:59:30 — the bottom of the window that used to roll over.
assert_eq!(dt_at(86_370).format("%:z").to_string(), "+23:59");

// Negative offsets clamp the same way.
assert_eq!(dt_at(-86_399).format("%z").to_string(), "-2359");

// The formatted value must parse back.
let formatted = dt_at(86_399).to_rfc3339();
assert!(formatted.ends_with("+23:59"));
assert!(DateTime::parse_from_rfc3339(&formatted).is_ok());

// RFC 2822 takes the same path.
assert!(dt_at(86_399).to_rfc2822().ends_with("+2359"));

// Offsets below the rounding window are unchanged.
assert_eq!(dt_at(86_369).format("%:z").to_string(), "+23:59"); // 23:59:29 rounds down
assert_eq!(dt_at(3_600).format("%z").to_string(), "+0100");
assert_eq!(dt_at(0).format("%:z").to_string(), "+00:00");
```
