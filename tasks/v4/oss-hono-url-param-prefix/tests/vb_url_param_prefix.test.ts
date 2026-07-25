// Hidden grader tests: replaceUrlParam must not substitute a parameter whose
// name is a prefix of another parameter's name. Expected values are generated
// from the gold patch and asserted through the exported utility.
import { test } from 'node:test'
import assert from 'node:assert'
import { replaceUrlParam } from './src/client/utils.ts'

test('vb prefix param is not matched inside a longer param', () => {
  assert.strictEqual(replaceUrlParam('/a/:idType/:id', { id: '1', idType: 'slug' }), '/a/slug/1')
})

test('vb prefix param with a regexp constraint is not matched', () => {
  assert.strictEqual(
    replaceUrlParam('/a/:idType{[a-z]+}/:id', { id: '1', idType: 'slug' }),
    '/a/slug/1'
  )
})

test('vb prefix param that is optional is not matched', () => {
  assert.strictEqual(replaceUrlParam('/a/:idType?/:id', { id: '1', idType: 'slug' }), '/a/slug/1')
})

test('vb prefix relationship holds in either direction', () => {
  assert.strictEqual(replaceUrlParam('/:userId/:user', { user: 'bob', userId: '7' }), '/7/bob')
})
