# Header values coerced from non-strings bypass CRLF validation

When a request header value is a plain string, it is validated before being
sent. But when the value is some other type — for example a function carrying a
crafted `toString` or `Symbol.toPrimitive` — it is coerced to a string with
`` `${value}` `` and sent **without** the same validation.

That lets a caller (or an object that flows in from untrusted data) smuggle a
carriage-return/line-feed into a header value, e.g.:

    { 'x-safe': someObjectThatStringifiesTo('legit\r\ntransfer-encoding: chunked') }

The embedded `\r\n` splits the header and injects an attacker-controlled header
or request onto the wire (HTTP request/response splitting and smuggling).

## Expected behaviour

Every header value that is coerced to a string — whether it is a bare value or
an element of a header-value array — must go through the same validation as a
string value. If the coerced value is not a valid header value (for instance it
contains CR or LF), reject the request by throwing the same
`InvalidArgumentError` used elsewhere for invalid headers, before anything is
written to the connection.

Ordinary, well-formed header values are unaffected.

The relevant code is the header-processing path in `lib/core/request.js`.
