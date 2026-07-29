// Regression guard: ordinary ETag negotiation. Says nothing about `*`, so it
// passes at the base commit.
import { test } from 'node:test'
import assert from 'node:assert'
import { Hono } from './src/index.ts'
import { etag } from './src/middleware/etag/index.ts'

const app = new Hono()
app.use('/*', etag())
app.get('/ok', (c) => c.text('hello'))
app.get('/missing', (c) => c.text('nope', 404))

test('vb existing plain request gets an etag', async () => {
  const res = await app.request('/ok')
  assert.strictEqual(res.status, 200)
  assert.ok(res.headers.get('etag'))
})

test('vb existing matching etag yields 304', async () => {
  const first = await app.request('/ok')
  const tag = first.headers.get('etag') as string
  const res = await app.request('/ok', { headers: { 'If-None-Match': tag } })
  assert.strictEqual(res.status, 304)
})

test('vb existing non-matching etag yields 200', async () => {
  const res = await app.request('/ok', { headers: { 'If-None-Match': 'W/"not-the-tag"' } })
  assert.strictEqual(res.status, 200)
  assert.strictEqual(await res.text(), 'hello')
})

test('vb existing error response is not turned into 304', async () => {
  const res = await app.request('/missing', { headers: { 'If-None-Match': 'W/"nope"' } })
  assert.strictEqual(res.status, 404)
})
