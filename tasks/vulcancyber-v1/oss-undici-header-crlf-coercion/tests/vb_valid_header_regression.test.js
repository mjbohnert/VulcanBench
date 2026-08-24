// Hidden pass_to_pass regression guard for oss-undici-header-crlf-coercion.
//
// A well-formed header value must still be accepted (validation must not become
// so strict that it rejects ordinary values). A valid value passes header
// validation and the request then fails only because nothing is listening — a
// network error, never InvalidArgumentError. This holds at the base commit AND
// after the fix, so it is a true no-regression guard. Run with `node --test`.

'use strict'

const { test } = require('node:test')
const assert = require('node:assert')
const { Client, errors } = require('./index.js')

test('vb valid header value is not rejected as invalid', async () => {
  const client = new Client('http://localhost:8080')
  try {
    await assert.rejects(
      client.request({ path: '/', method: 'GET', headers: { 'x-safe': 'a-normal-value' } }),
      (err) => !(err instanceof errors.InvalidArgumentError)
    )
  } finally {
    client.destroy()
  }
})
