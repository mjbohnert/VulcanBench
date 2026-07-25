// Hidden grader tests: `If-None-Match: *` must be treated as a match for a
// successful GET/HEAD, per RFC 9110. Expected values are generated from the
// gold patch and asserted through the public Hono app.request API.
import { test } from 'node:test'
import assert from 'node:assert'
import { Hono } from './src/index.ts'
import { etag } from './src/middleware/etag/index.ts'

const app = new Hono()
app.use('/*', etag())
app.get('/ok', (c) => c.text('hello'))
app.post('/ok', (c) => c.text('created', 201))
app.get('/missing', (c) => c.text('nope', 404))

test('vb star matches on GET', async () => {
  const res = await app.request('/ok', { headers: { 'If-None-Match': '*' } })
  assert.strictEqual(res.status, 304)
})

test('vb star matches on HEAD', async () => {
  const res = await app.request('/ok', { method: 'HEAD', headers: { 'If-None-Match': '*' } })
  assert.strictEqual(res.status, 304)
})

test('vb star match sends an empty body', async () => {
  const res = await app.request('/ok', { headers: { 'If-None-Match': '*' } })
  assert.strictEqual(res.status, 304)
  assert.strictEqual(await res.text(), '')
})

