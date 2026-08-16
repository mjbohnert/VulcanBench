# Request parsers are vulnerable to prototype pollution via `__proto__`

Several of the request-parsing helpers build their result objects from
untrusted input — the query string, the `Accept` header's media-type
parameters, and the request header map. When a request supplies a key named
`__proto__` (for example `?__proto__=a`, `Accept: text/html;__proto__=x`, or a
header named `__proto__`), the parsed key must be stored as ordinary data on the
returned object. It must never reach `Object.prototype` or otherwise mutate the
prototype chain.

## Expected behaviour

For each of these parse sites, the object returned to the caller:

- has **no** inherited prototype (its prototype is `null`), and
- exposes a `__proto__` entry supplied in the input as a normal own value,
  exactly like any other key.

Ordinary parsing of well-formed input is unchanged.

## Affected helpers

- query-string parsing (`src/utils/url.ts`)
- `Accept` media-type parameter parsing (`src/utils/accept.ts`)
- the request header map returned by `HonoRequest.header()` (`src/request.ts`)
