# `parse_qs_bytes` has no limit on the number of fields (DoS)

`tornado.escape.parse_qs_bytes` parses untrusted
`application/x-www-form-urlencoded` data with no cap on how many fields it will
accept. A request body containing a very large number of parameters forces the
parser to build an equally large result (and pushes that cost downstream into
per-argument handling) — an algorithmic denial-of-service reachable from a single
request.

## Expected behaviour

Add a keyword-only `max_num_fields` parameter to `parse_qs_bytes`. When the number
of parsed fields exceeds it, raise `ValueError` instead of returning the parsed
result. Each field counts toward the limit, including repeated occurrences of the
same key.

When `max_num_fields` is not given, behaviour is unchanged: parsing is exact and
imposes no field cap.

The function lives in `tornado/escape.py`.
