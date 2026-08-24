# A very long integer in a URL crashes routing instead of 404ing

The URL routing `<int:...>` converter turns the matched path segment into an
integer with `int(value)`. Python limits integer-from-string conversion to about
4300 digits and raises `ValueError` beyond that. The converter does not handle
that error, so a request URL with a very long run of digits (e.g.
`/thing/<thousands of digits>`) makes routing raise an unhandled `ValueError` —
a server error / crash — instead of simply not matching the route. A single
request can therefore trigger a denial-of-service.

## Expected behaviour

When the integer converter cannot convert the value (including because it exceeds
the digit limit), it must be treated as a **non-match** so the request cleanly
returns 404 Not Found — never an unhandled exception.

Ordinary integers still match and convert; an integer whose digit count is within
the limit still matches.

The converter lives in `src/werkzeug/routing/converters.py`; the matcher that
turns a conversion failure into a non-match is in
`src/werkzeug/routing/matcher.py`.
