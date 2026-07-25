# `replaceUrlParam` substitutes a parameter whose name prefixes another

`replaceUrlParam` fills path parameters by building one regular expression per
parameter name:

```ts
const reg = new RegExp('/:' + k + '(?:{[^/]+})?\\??')
```

That pattern has no end boundary, so a parameter whose name is a **prefix** of
another parameter's name matches inside the longer token. With `id` and
`idType`, the `id` pattern matches the `:id` at the start of `:idType`:

```ts
replaceUrlParam('/a/:idType/:id', { id: '1', idType: 'slug' })
// → '/a/1Type/:id'   (expected '/a/slug/1')
```

The substitution lands in the middle of the wrong token, leaving a corrupted
path and an unreplaced parameter.

Note this only shows up when the longer parameter appears **earlier** in the
URL. In `/posts/:id/:idType` the `id` pattern's first match happens to be the
intended token, so that case looks fine.

## Expected behaviour

A parameter pattern must match only a complete path token — the match has to be
followed by a `/` or the end of the string. Parameter names that prefix other
names are then substituted correctly regardless of their order in the URL, and
regexp-constrained (`:id{[0-9]+}`) and optional (`:id?`) forms keep working.

## Acceptance examples

```ts
replaceUrlParam('/a/:idType/:id',          { id: '1', idType: 'slug' }) === '/a/slug/1'
replaceUrlParam('/a/:idType{[a-z]+}/:id',  { id: '1', idType: 'slug' }) === '/a/slug/1'
replaceUrlParam('/a/:idType?/:id',         { id: '1', idType: 'slug' }) === '/a/slug/1'
replaceUrlParam('/:userId/:user',          { user: 'bob', userId: '7' }) === '/7/bob'

// Unaffected: no name prefixes another.
replaceUrlParam('/a/:idType',    { idType: 'slug' })      === '/a/slug'
replaceUrlParam('/a/:id/:name',  { id: '1', name: 'x' })  === '/a/1/x'
replaceUrlParam('/x/:id{[0-9]+}',{ id: '7' })             === '/x/7'
replaceUrlParam('/p/:id?',       { id: '9' })             === '/p/9'
```
