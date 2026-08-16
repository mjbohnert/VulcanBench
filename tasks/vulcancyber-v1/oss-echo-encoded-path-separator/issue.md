# Encoded path separators let static file requests bypass route-level middleware

The router matches routes against the raw, still-encoded request path (unless
escaped-path matching is explicitly enabled). So a percent-encoded path separator
— `%2F` (forward slash) or `%5C` (backslash), in either letter case, and even
double-encoded like `%252F` — is **not** treated as a segment boundary during
routing.

The static file handlers, however, unescape the wildcard segment before opening
the file. That turns an encoded separator into a real one *after* routing has
already happened, so a request can resolve a file outside the path the router
authorized — slipping past route-level middleware such as authentication on a
sibling route.

Example: with an authenticated `/admin` group and a static tree mounted at `/`,
a request to `/admin%2Fsecret.txt` is not matched as `/admin/...` by the router
(so the auth middleware never runs), but the static handler then unescapes it to
`admin/secret.txt` and serves the protected file.

## Expected behaviour

When resolving a static file, a wildcard path segment that contains an encoded
path separator must be rejected as **404 Not Found** *before* it is unescaped —
no real filename contains a path separator. This applies to both static file
handlers (the one on the echo instance and the one in the static middleware),
and must cover `%2F`/`%2f`, `%5C`/`%5c`, and double-encoded forms.

Legitimate static files, and ordinary unencoded paths handled by their matched
route, must continue to work.

The relevant code is the static directory handler in `echo.go` and the static
middleware in `middleware/static.go`.
