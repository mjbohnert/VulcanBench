// Regression guard: ordinary TrieRouter matching. Says nothing about an empty
// wildcard remainder, so it passes at the base commit.
import { test } from 'node:test'
import assert from 'node:assert'
import { TrieRouter } from './src/router/trie-router/index.ts'

type Match = [string, Record<string, string>][]
const handlers = (m: unknown): Match => (m as [Match])[0]

test('vb existing wildcard matches a non-empty remainder', () => {
  const router = new TrieRouter<string>()
  router.add('GET', '/:id{[0-9]+}/*', 'regexp')
  const res = handlers(router.match('GET', '/123/x'))
  assert.strictEqual(res.length, 1)
  assert.strictEqual(res[0][0], 'regexp')
  assert.strictEqual(res[0][1].id, '123')
})

test('vb existing plain static route matches', () => {
  const router = new TrieRouter<string>()
  router.add('GET', '/hello', 'static')
  assert.strictEqual(handlers(router.match('GET', '/hello'))[0][0], 'static')
  assert.strictEqual(handlers(router.match('GET', '/nope')).length, 0)
})

test('vb existing plain param route captures', () => {
  const router = new TrieRouter<string>()
  router.add('GET', '/users/:id', 'user')
  const res = handlers(router.match('GET', '/users/42'))
  assert.strictEqual(res[0][0], 'user')
  assert.strictEqual(res[0][1].id, '42')
})

test('vb existing sibling route still wins on its own path', () => {
  const router = new TrieRouter<string>()
  router.add('GET', '/regex-abc/:id{[0-9]+}/*', 'middleware')
  router.add('GET', '/regex-abc/:id{[0-9]+}/def', 'regexp')
  const res = handlers(router.match('GET', '/regex-abc/1/def'))
  assert.deepStrictEqual(res.map((h) => h[0]), ['middleware', 'regexp'])
})

test('vb non-matching regexp still does not match', () => {
  const router = new TrieRouter<string>()
  router.add('GET', '/:id{[0-9]+}/*', 'regexp')
  assert.strictEqual(handlers(router.match('GET', '/abc')).length, 0)
})
