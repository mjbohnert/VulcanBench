// Hidden pass_to_pass regression guard for oss-zod-jsonschema-proto-pollution.
//
// Handling __proto__ as an own property must not change ordinary JSON Schema
// conversion: normal object schemas still round-trip and still enforce required
// keys. Both hold at the base commit and after the fix. Run with `tsx --test`.

import { test } from 'node:test'
import assert from 'node:assert'
import * as z from './packages/zod/src/v4/index'

test('vb ordinary object schema round-trips and enforces required keys', () => {
  const schema = z.object({ name: z.string(), age: z.number() })
  const json: any = z.toJSONSchema(schema)
  assert.ok(Object.prototype.hasOwnProperty.call(json.properties, 'name'))
  assert.ok(Object.prototype.hasOwnProperty.call(json.properties, 'age'))

  const back = z.fromJSONSchema(json)
  assert.strictEqual(back.safeParse({ name: 'a', age: 1 }).success, true)
  assert.strictEqual(back.safeParse({ name: 'a' }).success, false)
})
