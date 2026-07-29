// Regression guard: tilde ranges without includePrerelease, tilde ranges with
// a full version, and the caret/x-range forms that already used a `-0` lower
// bound. Says nothing about the partial-tilde prerelease bound, so it passes at
// the base commit.
const { test } = require('node:test')
const assert = require('node:assert')
const semver = require('./index.js')
const Range = require('./classes/range.js')

const ipr = { includePrerelease: true }

test('vb existing tilde without includePrerelease unaffected', () => {
  assert.strictEqual(new Range('~1.2').range, '>=1.2.0 <1.3.0-0')
  assert.strictEqual(new Range('~1').range, '>=1.0.0 <2.0.0-0')
})

test('vb existing tilde with a full version unaffected', () => {
  assert.strictEqual(new Range('~1.2.3', ipr).range, '>=1.2.3 <1.3.0-0')
})

test('vb existing caret and x-range lower bounds unaffected', () => {
  assert.strictEqual(new Range('^1.2', ipr).range, '>=1.2.0-0 <2.0.0-0')
  assert.strictEqual(new Range('1.2.x', ipr).range, '>=1.2.0-0 <1.3.0-0')
})

test('vb existing plain satisfies unaffected', () => {
  assert.strictEqual(semver.satisfies('1.2.5', '~1.2'), true)
  assert.strictEqual(semver.satisfies('1.3.0', '~1.2'), false)
  assert.strictEqual(semver.satisfies('1.2.0-alpha', '~1.2'), false)
})
