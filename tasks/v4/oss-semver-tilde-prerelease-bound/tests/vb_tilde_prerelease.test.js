// Hidden grader tests: tilde ranges with includePrerelease must use the same
// `-0` lower bound as the x-range they are documented to be equivalent to.
//
// All expected values are generated from the gold patch and asserted through
// the public API (new Range(...).range and semver.satisfies).
const { test } = require('node:test')
const assert = require('node:assert')
const semver = require('./index.js')
const Range = require('./classes/range.js')

const ipr = { includePrerelease: true }

test('vb tilde minor lower bound includes prereleases', () => {
  assert.strictEqual(new Range('~1.2', ipr).range, '>=1.2.0-0 <1.3.0-0')
})

test('vb tilde major lower bound includes prereleases', () => {
  assert.strictEqual(new Range('~1', ipr).range, '>=1.0.0-0 <2.0.0-0')
})

test('vb tilde minor matches a prerelease of its lower bound', () => {
  assert.strictEqual(semver.satisfies('1.2.0-alpha', '~1.2', ipr), true)
})

test('vb tilde major matches a prerelease of its lower bound', () => {
  assert.strictEqual(semver.satisfies('1.0.0-alpha', '~1', ipr), true)
})

test('vb tilde agrees with the equivalent x-range', () => {
  assert.strictEqual(
    new Range('~1.2', ipr).range,
    new Range('1.2.x', ipr).range,
  )
  assert.strictEqual(
    semver.satisfies('1.2.0-alpha', '~1.2', ipr),
    semver.satisfies('1.2.0-alpha', '1.2.x', ipr),
  )
})
