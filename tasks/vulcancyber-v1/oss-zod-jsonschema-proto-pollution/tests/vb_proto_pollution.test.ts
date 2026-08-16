// Hidden fail_to_pass tests for oss-zod-jsonschema-proto-pollution (colinhacks/zod PR #6346).
//
// zod's JSON Schema conversion builds plain objects and assigns keys with
// `obj[key] = value`. For an attacker-influenced key of "__proto__" that goes
// through the inherited __proto__ setter instead of creating an own property, so
// a "__proto__" property in a schema/shape/registry is silently dropped or mutates
// the prototype rather than being carried as data. The fix assigns via assignProp
// so "__proto__" becomes an own property everywhere it is emitted or resolved.
//
// Tests use only public API and JSON.parse (the only way to express a real own
// "__proto__" data key). Run with `tsx --test`.

import { test } from 'node:test'
import assert from 'node:assert'
import * as z from './packages/zod/src/v4/index'

test('vb required __proto__ property is kept and enforced', () => {
  const schema = z.fromJSONSchema(
    JSON.parse(
      '{"type":"object","properties":{"__proto__":{"type":"string","const":"admin"},"role":{"type":"string"}},"required":["__proto__","role"]}'
    )
  )
  assert.strictEqual(schema.safeParse({ role: 'x' }).success, false)
  assert.strictEqual(schema.safeParse(JSON.parse('{"role":"x","__proto__":"wrong"}')).success, false)
  assert.strictEqual(schema.safeParse(JSON.parse('{"role":"x","__proto__":"admin"}')).success, true)
})

test('vb __proto__ shape key is emitted as an own property', () => {
  const schema = z.object({ ['__proto__']: z.literal('admin'), role: z.string() })
  const result: any = z.toJSONSchema(schema, { io: 'input' })
  assert.deepStrictEqual(result.required, ['__proto__', 'role'])
  assert.ok(Object.prototype.hasOwnProperty.call(result.properties, '__proto__'))
})

test('vb __proto__ registry id is emitted as an own entry', () => {
  const registry = z.registry<{ id: string }>()
  registry.add(z.object({ a: z.string() }), { id: '__proto__' })
  registry.add(z.object({ b: z.string() }), { id: 'normal' })
  assert.deepStrictEqual(Object.keys(z.toJSONSchema(registry).schemas), ['__proto__', 'normal'])
})
