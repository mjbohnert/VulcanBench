# `parse_url` accepts control characters in the host

`parse_url()` does not validate the host portion of a URL's authority. A URL whose
host contains a control character — a carriage return, line feed, NUL, or other
control byte, whether written literally or percent-encoded (`%00`, `%0d`, `%0a`,
…) — is parsed into a `Url` whose `.host` still contains that character.

A host that carries a CR/LF (or other control byte) downstream enables Host-header
and CRLF injection, request splitting/smuggling, and SSRF-style host confusion.

## Expected behaviour

`parse_url` must reject a URL whose host contains a control character or a space,
including percent-encoded control octets, by raising `LocationParseError` instead
of returning a `Url`.

Well-formed hosts — ordinary domain names and IP literals — must still parse
normally.

The parsing/normalization lives in `src/urllib3/util/url.py`.
