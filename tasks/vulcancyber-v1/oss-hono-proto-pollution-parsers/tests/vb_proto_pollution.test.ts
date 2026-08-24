// Hidden fail_to_pass tests for oss-hono-proto-pollution-parsers (honojs/hono PR #5161).
// The three request-parsing sites — query string, Accept params, and header map —
// must build their result objects with a null prototype (Object.create(null)) so an
// attacker-controlled `__proto__` key is stored as ordinary data instead of mutating
// Object.prototype. At the base commit each site uses a plain `{}` literal, so the
// returned object's prototype is Object.prototype and these assertions fail.
// Run with `tsx --test` (hono source uses extensionless ESM imports).

import { test } from 'node:test'
import assert from 'node:assert'
import { getQueryParams } from './src/utils/url'
import { parseAccept } from './src/utils/accept'
import { HonoRequest } from './src/request'

test('vb query params use a null-prototype object', () => {
  const params = getQueryParams('http://example.com/?__proto__=a&__proto__=b') as Record<
    string,
    string[]
  >
  assert.strictEqual(Object.getPrototypeOf(params), null)
  assert.deepStrictEqual(params['__proto__'], ['a', 'b'])
})

test('vb accept params use a null-prototype object', () => {
  const result = parseAccept('text/html;__proto__=x')
  assert.strictEqual(Object.getPrototypeOf(result[0].params), null)
  assert.strictEqual(result[0].params['__proto__'], 'x')
})

test('vb header map uses a null-prototype object', () => {
  const req = new HonoRequest(new Request('http://localhost', { headers: { 'x-custom': 'v' } }))
  const headers = req.header()
  assert.strictEqual(Object.getPrototypeOf(headers), null)
})
