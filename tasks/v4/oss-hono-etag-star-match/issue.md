# `If-None-Match: *` is never treated as a match by the etag middleware

RFC 9110 defines `*` in `If-None-Match` as a wildcard that matches **any**
current representation of the resource. A client sending
`If-None-Match: *` on a conditional `GET` is asking "send this only if it
doesn't exist yet."

The etag middleware passes the header value straight to its entity-tag
comparison, which compares tags literally. `*` never equals a generated ETag, so
the condition never fires: the request is answered `200` with the full body
instead of `304 Not Modified`.

## Expected behaviour

A bare `If-None-Match: *` counts as a match when the request method is `GET` or
`HEAD` and the response is successful. Such a request must be answered `304`
with an empty body.

Everything else is unchanged: normal entity-tag comparison, responses that are
not successful (a `404` must not become a `304`), and requests with no
`If-None-Match` header.

## Acceptance examples

```ts
const app = new Hono()
app.use('/*', etag())
app.get('/ok', (c) => c.text('hello'))
app.get('/missing', (c) => c.text('nope', 404))

// A bare `*` matches on GET and HEAD.
await app.request('/ok', { headers: { 'If-None-Match': '*' } })
// → status 304, body ''

await app.request('/ok', { method: 'HEAD', headers: { 'If-None-Match': '*' } })
// → status 304

// Unaffected: an unsuccessful response is not turned into a 304.
await app.request('/missing', { headers: { 'If-None-Match': 'W/"nope"' } })
// → status 404

// Unaffected: ordinary entity-tag negotiation.
// a matching etag → 304; a non-matching etag → 200 with the body;
// no If-None-Match → 200 with an `etag` response header.
```

Only a bare `*` is in scope — a `*` appearing inside a list of entity tags is
not required to match.
