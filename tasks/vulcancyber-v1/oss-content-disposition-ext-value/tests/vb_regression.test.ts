// Hidden pass_to_pass regression guard for oss-content-disposition-ext-value.
//
// Rejecting malformed escapes must not change parsing of well-formed values: a
// valid UTF-8 ext-value still decodes, and a plain quoted filename is unchanged.
// Both hold at the base commit and after the fix. Run with `tsx --test`.

import { test } from 'node:test'
import assert from 'node:assert'
import { parse } from './src/index.ts'

test('vb valid utf-8 ext-value still decodes', () => {
  const p = parse("attachment; filename*=utf-8''%E2%82%AC%20rates.pdf").parameters
  assert.strictEqual(p.filename, '€ rates.pdf')
})

test('vb plain quoted filename is unchanged', () => {
  const p = parse('attachment; filename="a.pdf"').parameters
  assert.strictEqual(p.filename, 'a.pdf')
})
