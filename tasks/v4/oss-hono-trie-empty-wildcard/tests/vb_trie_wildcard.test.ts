// Hidden grader tests: a trailing wildcard after a regexp-constrained param
// must also match when the wildcard remainder is empty.
//
// These exercise TrieRouter directly. Hono's default SmartRouter would fall
// back to RegExpRouter, which already handles this case, and would therefore
// pass at the base commit.
import { test } from 'node:test'
import assert from 'node:assert'
import { TrieRouter } from './src/router/trie-router/index.ts'

type Match = [string, Record<string, string>][]

const handlers = (m: unknown): Match => (m as [Match])[0]

test('vb wildcard matches empty remainder after regexp param', () => {
  const router = new TrieRouter<string>()
  router.add('GET', '/:id{[0-9]+}/*', 'regexp')
  const res = handlers(router.match('GET', '/123'))
  assert.strictEqual(res.length, 1)
  assert.strictEqual(res[0][0], 'regexp')
})

test('vb empty wildcard remainder still captures the param', () => {
  const router = new TrieRouter<string>()
  router.add('GET', '/:id{[0-9]+}/*', 'regexp')
  const res = handlers(router.match('GET', '/123'))
  assert.strictEqual(res.length, 1)
  assert.strictEqual(res[0][1].id, '123')
})

test('vb wildcard middleware applies to the bare prefix route', () => {
  const router = new TrieRouter<string>()
  router.add('GET', '/regex-abc/:id{[0-9]+}/*', 'middleware')
  router.add('GET', '/regex-abc/:id{[0-9]+}/def', 'regexp')
  const res = handlers(router.match('GET', '/regex-abc/1'))
  assert.strictEqual(res.length, 1)
  assert.strictEqual(res[0][0], 'middleware')
})

