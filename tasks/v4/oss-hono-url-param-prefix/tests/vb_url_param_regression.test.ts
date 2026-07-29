// Regression guard: ordinary parameter substitution. No parameter name here is
// a prefix of another, so this passes at the base commit.
import { test } from 'node:test'
import assert from 'node:assert'
import { replaceUrlParam } from './src/client/utils.ts'

test('vb existing single param is replaced', () => {
  assert.strictEqual(replaceUrlParam('/a/:idType', { idType: 'slug' }), '/a/slug')
  assert.strictEqual(replaceUrlParam('/posts/:id', { id: '1' }), '/posts/1')
})

test('vb existing multiple distinct params are replaced', () => {
  assert.strictEqual(replaceUrlParam('/a/:id/:name', { id: '1', name: 'x' }), '/a/1/x')
})

test('vb existing regexp-constrained param is replaced', () => {
  assert.strictEqual(replaceUrlParam('/x/:id{[0-9]+}', { id: '7' }), '/x/7')
})

test('vb existing optional param is replaced', () => {
  assert.strictEqual(replaceUrlParam('/p/:id?', { id: '9' }), '/p/9')
})
