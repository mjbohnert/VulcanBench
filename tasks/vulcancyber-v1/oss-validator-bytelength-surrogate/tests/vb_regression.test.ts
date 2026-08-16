// Hidden pass_to_pass regression guard for oss-validator-bytelength-surrogate.
//
// The manual byte-length computation must agree with the old one for well-formed
// input: a valid surrogate pair is 4 bytes, and ASCII is one byte per character.
// Both hold at the base commit and after the fix. Run with `tsx --test`.

import { test } from 'node:test'
import assert from 'node:assert'
import isByteLength from './src/lib/isByteLength.js'

test('vb valid surrogate pair is measured as four bytes', () => {
  assert.strictEqual(isByteLength('\u{1F600}', { min: 4, max: 4 }), true)
})

test('vb ascii byte length is unaffected', () => {
  assert.strictEqual(isByteLength('abc', { min: 1, max: 3 }), true)
})
