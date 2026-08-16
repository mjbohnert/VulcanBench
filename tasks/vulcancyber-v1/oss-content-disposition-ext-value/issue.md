# Malformed percent-escapes in an ISO-8859-1 `filename*` are decoded leniently

`Content-Disposition` `filename*` ext-values (RFC 5987) carry a charset. For the
`UTF-8` charset, a malformed percent-escape makes parsing reject the value. But
for the `ISO-8859-1` charset, malformed escapes (e.g. `%2r`, `%GG`, a trailing
`%`) are **partially decoded** and surface as a `filename` parameter.

That yields an attacker-influenced, half-decoded filename that disagrees with the
raw header — a filename-spoofing vector (the value a consumer sees differs from
what the header actually contains).

## Expected behaviour

Decoding an ISO-8859-1 ext-value must reject **any** malformed percent-escape,
just like the UTF-8 path. When the ext-value cannot be fully decoded, `parse` must
**not** emit a decoded `filename`:

- keep the raw `filename*` parameter as-is; and
- if the header also has a plain `filename`, fall back to that.

Well-formed ext-values (including valid UTF-8) still decode exactly as before.

The decoding lives in `src/index.ts` (the hex-escape decoding used by `parse`).
