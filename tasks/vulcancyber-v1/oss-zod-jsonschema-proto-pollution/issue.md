# JSON Schema conversion is vulnerable to `__proto__` via prototype pollution

The JSON Schema conversion builds plain result objects and fills them in with
`obj[key] = value`. When a key is `"__proto__"`, that assignment goes through the
inherited `__proto__` setter instead of creating an ordinary own property. As a
result a `"__proto__"` key coming from a schema, an object shape, or a registry
entry is silently dropped (or mutates the object's prototype) rather than being
carried through as data.

This shows up in several directions of the conversion:

- resolving a JSON Schema into a zod type (`fromJSONSchema`): a `"__proto__"`
  property is not kept, so it is neither emitted nor enforced;
- emitting a JSON Schema from a zod type (`toJSONSchema`): a `"__proto__"` object
  shape key, or a registry id / `$defs` key of `"__proto__"`, is not written as an
  own property.

## Expected behaviour

A `"__proto__"` key must be treated as ordinary data — stored and read as an own
property — everywhere the conversion builds an object from keys it does not
control, in both directions:

- a required `"__proto__"` property parsed from a JSON Schema is kept and enforced;
- a `"__proto__"` shape key, registry id, or `$defs` id is emitted as an own
  property / own entry with a resolvable reference.

Ordinary schemas must convert and round-trip exactly as before.

The relevant code is the JSON Schema conversion in
`packages/zod/src/v4/classic/from-json-schema.ts` and
`packages/zod/src/v4/core/` (the to-json-schema processors). A helper for making
an assignment an own property already exists in `core/util.ts`.
