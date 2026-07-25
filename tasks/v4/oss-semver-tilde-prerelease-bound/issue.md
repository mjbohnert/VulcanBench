# Tilde ranges exclude prereleases of their lower bound under `includePrerelease`

The README documents a partial tilde range as equivalent to the corresponding
x-range:

> `~1.2` := `>=1.2.0 <1.(2+1).0` := `>=1.2.0 <1.3.0-0` (**Same as `1.2.x`**)

With `{ includePrerelease: true }` that equivalence breaks. The x-range and
caret forms lower their bound to `-0` — the lowest possible prerelease — but the
tilde form does not:

| Range | `includePrerelease` result |
|---|---|
| `1.2.x` | `>=1.2.0-0 <1.3.0-0` |
| `^1.2` | `>=1.2.0-0 <2.0.0-0` |
| `~1.2` | `>=1.2.0 <1.3.0-0` ← lower bound excludes prereleases |

So `semver.satisfies('1.2.0-alpha', '~1.2', { includePrerelease: true })` is
`false`, while the documented-equivalent `1.2.x` returns `true`.

This affects the two partial tilde forms — `~M` and `~M.m`. A tilde range with a
full version (`~1.2.3`) has an explicit lower bound and is not affected.

## Expected behaviour

Under `includePrerelease`, a partial tilde range must use the `-0` lower bound,
matching the x-range it is documented to equal. Without `includePrerelease`,
and for tilde ranges with a full version, behaviour is unchanged.

## Acceptance examples

```js
const ipr = { includePrerelease: true }

// Partial tilde ranges gain the -0 lower bound.
new Range('~1.2', ipr).range === '>=1.2.0-0 <1.3.0-0'
new Range('~1',   ipr).range === '>=1.0.0-0 <2.0.0-0'

// And therefore match prereleases of that bound.
semver.satisfies('1.2.0-alpha', '~1.2', ipr) === true
semver.satisfies('1.0.0-alpha', '~1',   ipr) === true

// The documented equivalence with the x-range holds.
new Range('~1.2', ipr).range === new Range('1.2.x', ipr).range

// Unaffected: no includePrerelease.
new Range('~1.2').range === '>=1.2.0 <1.3.0-0'
semver.satisfies('1.2.0-alpha', '~1.2') === false

// Unaffected: tilde with a full version.
new Range('~1.2.3', ipr).range === '>=1.2.3 <1.3.0-0'

// Unaffected: caret and x-range forms already did this.
new Range('^1.2',  ipr).range === '>=1.2.0-0 <2.0.0-0'
new Range('1.2.x', ipr).range === '>=1.2.0-0 <1.3.0-0'
```
