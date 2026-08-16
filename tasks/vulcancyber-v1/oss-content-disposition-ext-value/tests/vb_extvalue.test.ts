// Hidden fail_to_pass tests for oss-content-disposition-ext-value (jshttp/content-disposition PR #138).
//
// RFC 5987 `filename*` ext-values in the ISO-8859-1 charset were decoded
// leniently: a malformed percent-escape (e.g. %2r, %GG, a trailing %) was
// partially decoded into a `filename` parameter, unlike the UTF-8 path which
// rejects them. That produces an attacker-influenced, half-decoded filename that
// disagrees with the raw header -- a filename-spoofing vector. The fix makes
// decoding return nothing on any malformed escape, so `parse` keeps the raw
// `filename*` (and falls back to an explicit `filename` when present) instead of
// emitting a half-decoded name.
//
// At the base commit each case below produces a decoded `filename`, so the
// assertions fail. Run with `tsx --test`.

import { test } from 'node:test'
import assert from 'node:assert'
import { parse } from './src/index.ts'

test('vb malformed iso-8859-1 escape does not yield a decoded filename', () => {
  const p = parse("attachment; filename*=ISO-8859-1''%A3%2rates.pdf").parameters
  assert.strictEqual(p.filename, undefined)
  assert.strictEqual(p['filename*'], "ISO-8859-1''%A3%2rates.pdf")
})

test('vb malformed filename* falls back to the explicit filename', () => {
  const p = parse("attachment; filename=\"invoice.pdf\"; filename*=ISO-8859-1''report%2").parameters
  assert.strictEqual(p.filename, 'invoice.pdf')
})

test('vb invalid hex digits do not yield a decoded filename', () => {
  const p = parse("attachment; filename*=ISO-8859-1''%GGrates.pdf").parameters
  assert.strictEqual(p.filename, undefined)
})
