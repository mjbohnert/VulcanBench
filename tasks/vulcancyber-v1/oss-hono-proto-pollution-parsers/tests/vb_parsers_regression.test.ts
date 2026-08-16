// Hidden pass_to_pass regression guard for oss-hono-proto-pollution-parsers.
// Imports only pre-existing public parsers, so it compiles and passes at the base
// commit AND after the fix — hardening the parse sites against __proto__ must not
// change ordinary parsing behaviour. Run with `tsx --test`.

import { test } from 'node:test'
import assert from 'node:assert'
import { getQueryParam, getQueryParams } from './src/utils/url'
import { parseAccept } from './src/utils/accept'
import { HonoRequest } from './src/request'

test('vb parsers unaffected for ordinary input', () => {
  assert.strictEqual(getQueryParam('http://example.com/?a=1&b=2', 'a'), '1')

  const many = getQueryParams('http://example.com/?a=1&a=2&b=3') as Record<string, string[]>
  assert.deepStrictEqual(many['a'], ['1', '2'])
  assert.deepStrictEqual(many['b'], ['3'])

  const acc = parseAccept('text/html,application/json;q=0.9')
  assert.strictEqual(acc[0].type, 'text/html')
  assert.strictEqual(acc[1].type, 'application/json')
  assert.strictEqual(acc[1].q, 0.9)

  const req = new HonoRequest(
    new Request('http://localhost', { headers: { 'content-type': 'application/json' } })
  )
  assert.strictEqual(req.header('Content-Type'), 'application/json')
})
