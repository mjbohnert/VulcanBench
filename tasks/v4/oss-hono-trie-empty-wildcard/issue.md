# A trailing wildcard after a regexp param does not match an empty remainder

`TrieRouter` supports routes that combine a regexp-constrained parameter with a
trailing wildcard:

```ts
router.add('GET', '/:id{[0-9]+}/*', 'regexp')
```

This matches `/123/x`, but **not** `/123`. When the regexp consumes the whole
remaining path, the wildcard child is never consulted, so a path with an empty
wildcard remainder finds no handler at all.

The same problem hides wildcard middleware from a bare prefix route:

```ts
router.add('GET', '/regex-abc/:id{[0-9]+}/*', 'middleware')
router.add('GET', '/regex-abc/:id{[0-9]+}/def', 'regexp')
```

`/regex-abc/1/def` correctly matches both, but `/regex-abc/1` matches nothing —
the middleware registered for the wildcard is skipped.

## Expected behaviour

A trailing wildcard must also match when its remainder is empty. `/123` matches
`/:id{[0-9]+}/*` with `id` captured as `"123"`, and `/regex-abc/1` matches the
wildcard middleware. Paths that fail the regexp (`/abc`) still do not match, and
non-empty remainders behave exactly as before.

## Acceptance examples

```ts
const router = new TrieRouter<string>()
router.add('GET', '/:id{[0-9]+}/*', 'regexp')

// Empty wildcard remainder now matches, and captures the param.
const [res] = router.match('GET', '/123')
// res.length === 1, res[0][0] === 'regexp', res[0][1].id === '123'

// Unaffected: non-empty remainder, and a path failing the regexp.
// router.match('GET', '/123/x') → one 'regexp' handler with id '123'
// router.match('GET', '/abc')   → no handlers
```

Note the params object has a null prototype, so compare fields individually
rather than with a deep-equality check against an object literal.
