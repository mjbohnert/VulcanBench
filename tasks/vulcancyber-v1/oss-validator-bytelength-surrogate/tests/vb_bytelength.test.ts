// Hidden fail_to_pass tests for oss-validator-bytelength-surrogate (validatorjs/validator.js PR #2822).
//
// isByteLength() measured a string's UTF-8 byte length with
// `encodeURI(str).split(/%..|./).length - 1`. encodeURI throws a URIError on ANY
// unpaired UTF-16 surrogate, so a single lone surrogate in the input crashes the
// validator (and every caller that reaches it, e.g. isEmail) -- an
// uncaught-exception denial-of-service. The fix computes the byte length manually,
// counting a surrogate pair as 4 bytes and an unpaired surrogate as 3 (U+FFFD).
//
// At the base commit each call below throws URIError, so the assertions fail. Run
// with `tsx --test`.

import { test } from 'node:test'
import assert from 'node:assert'
import isByteLength from './src/lib/isByteLength.js'

test('vb lone high surrogate is measured as three bytes', () => {
  assert.strictEqual(isByteLength('\uD800', { min: 3, max: 3 }), true)
})

test('vb lone low surrogate exceeds a two-byte maximum', () => {
  assert.strictEqual(isByteLength('\uDC00', { max: 2 }), false)
})

test('vb ascii char plus lone surrogate is measured as four bytes', () => {
  assert.strictEqual(isByteLength('a\uDBFF', { min: 4, max: 4 }), true)
})
