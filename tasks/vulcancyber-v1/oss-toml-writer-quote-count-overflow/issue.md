# Serializing a string with a long run of quotes overflows and panics

When the TOML writer serializes a string, it scans the value for the longest run
of consecutive single-quote and double-quote characters in order to choose how to
quote the output. Those run-length counters are `u8`, and each character in a run
is added with an unchecked increment. A value containing **256 or more consecutive
quote characters** overflows the counter — which panics in a debug build.

Serializing a single attacker-influenced string can therefore crash the writer: a
denial-of-service.

## Expected behaviour

Counting a run of quote characters must never overflow, no matter how long the run
is. Accumulate the run length so it saturates at the maximum instead of wrapping,
and keep choosing the same quote style the writer would otherwise choose.

Serialization of ordinary strings is unchanged; only the previously-panicking
long-run case now succeeds.

The counting lives in `src/string.rs` (the value-metrics computation).
