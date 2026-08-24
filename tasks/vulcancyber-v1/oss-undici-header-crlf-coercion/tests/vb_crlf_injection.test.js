// Hidden fail_to_pass tests for oss-undici-header-crlf-coercion (nodejs/undici PR #5579).
//
// A header value that is not a plain string (e.g. a function carrying a crafted
// toString / Symbol.toPrimitive) is coerced with `${val}` before being sent. At
// the base commit that coerced string is pushed onto the request WITHOUT running
// it through isValidHeaderValue, so a payload like "legit\r\nx-injected: yes"
// smuggles CRLF into the wire request (header/request splitting). The fix must
// validate the coerced value and throw InvalidArgumentError for CRLF.
//
// At base the header is accepted, so request() proceeds to connect and rejects
// with a *network* error (AggregateError / ECONNREFUSED) — NOT InvalidArgumentError
// — and these assertions fail. At the fix it rejects synchronously with
// InvalidArgumentError. Run with `node --test`.

'use strict'

const { test } = require('node:test')
const assert = require('node:assert')
const { Client, errors } = require('./index.js')

const CRLF = 'legit\r\nx-injected: yes'

const withToString = (payload) => {
  const fn = function () {}
  fn.toString = () => payload
  return fn
}

const withToPrimitive = (payload) => {
  const fn = function () {}
  fn[Symbol.toPrimitive] = () => payload
  return fn
}

// Rejecting with InvalidArgumentError means the value was validated and refused
// before any bytes were written. A network error would mean it slipped through.
const mustRejectAsInvalid = async (headers) => {
  const client = new Client('http://localhost:8080')
  try {
    await assert.rejects(
      client.request({ path: '/', method: 'GET', headers }),
      errors.InvalidArgumentError
    )
  } finally {
    client.destroy()
  }
}

test('vb rejects coerced CRLF header via toString', async () => {
  await mustRejectAsInvalid({ 'x-safe': withToString(CRLF) })
})

test('vb rejects coerced CRLF header via Symbol.toPrimitive', async () => {
  await mustRejectAsInvalid({ 'x-safe': withToPrimitive(CRLF) })
})

test('vb rejects coerced CRLF header in an array element', async () => {
  await mustRejectAsInvalid({ 'x-safe': [withToString(CRLF)] })
})
