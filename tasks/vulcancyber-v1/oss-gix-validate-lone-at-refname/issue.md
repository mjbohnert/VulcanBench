# A lone `@` is accepted as a reference name

In Git, a bare `@` is shorthand for `HEAD`, and Git refuses to create a reference
literally named `@`. This validator does not: `name_partial` accepts `@` as a
valid partial reference name, and the sanitizing variant leaves `@` unchanged.

Allowing a reference named `@` lets a caller create or reference a name that
collides with the `HEAD` shorthand — reference confusion / spoofing.

## Expected behaviour

A reference name that reduces to exactly `@` must be rejected, matching Git:

- `name_partial` (partial validation) returns an error (the existing "reserved
  name" error) for `@`;
- the sanitizing variant replaces a lone `@` with `-` (e.g. inputs that reduce to
  a bare `@`, such as `//@//`, sanitize to `-`, not `@`).

An `@` that appears **inside** a component (e.g. `refs/heads/@`) is still valid,
and ordinary names are unaffected.

The validation lives in `src/reference.rs`.
