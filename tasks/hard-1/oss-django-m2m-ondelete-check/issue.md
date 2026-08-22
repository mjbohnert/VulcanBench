# Auto-created M2M through models must reject database-level `on_delete` mixing

Django now supports database-level `on_delete` variants (e.g. `models.DB_CASCADE`),
where the cascade is enforced by the database rather than by Django's Python-level
collector. These cannot be mixed with Python-level variants in a chain of model
references.

A `ManyToManyField` without an explicit `through` model gets an **auto-created**
intermediary, which always uses **Python-level** cascade. If either end model of
such an M2M is reached through a `ForeignKey` that uses a **database-level**
`on_delete`, the two cascade worlds are mixed and deletion behavior is ambiguous —
but Django currently accepts it silently.

Add a system check, error id **`fields.E323`**, raised by the `ManyToManyField`
during `check()`.

## Expected behavior

For a `ManyToManyField` with an **auto-created** through model, inspect the two end
models reached through the intermediary. For every `ForeignKey` on those models
whose `on_delete` is a database-level variant (and not `DO_NOTHING`), raise a
`fields.E323` error pointing at that offending `ForeignKey`:

- Both ends use a database-level FK → **two** E323 errors (one per end's FK).
- Only one end does → **one** E323, pointing at that end's FK.
- Neither end does (all Python-level `on_delete`) → **no** E323.
- The M2M uses an explicit, **manually created** `through` model → **no** E323
  (manual through models are validated on their own).

The error message states that the field specifies a database-level `on_delete`
variant while the auto-created intermediary uses a Python-level variant, and hints
to either use a Python-level variant or create an explicit through model.

Implement the `fields.E323` check on `ManyToManyField`.
