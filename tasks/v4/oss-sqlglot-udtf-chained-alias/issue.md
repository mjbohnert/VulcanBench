# Chained correlated `UNNEST`s keep a stale alias and leave a dangling reference

`canonicalize_internal_names` rewrites user-supplied source and column aliases
to internal `_tN` / `_cN` names. It builds one column map per scope.

That works for CTEs and subqueries, which belong to a single scope. A UDTF such
as `UNNEST(...)` does not: the same UDTF expression can be a source in several
scopes. Each scope therefore gets its own map, and in a chain of correlated
`UNNEST`s only the last one has its alias rewritten.

For:

```sql
SELECT e.id FROM t AS e, UNNEST(e.arr) AS x, UNNEST(e.arr) AS y WHERE x = y
```

the result keeps `x` as an alias while the predicate already refers to `_c0`:

```sql
SELECT `_t0`.`id` AS `id` FROM `_t0` AS `_t0`
CROSS JOIN UNNEST(`_t0`.`arr`) AS `x`     -- should be `_c0`
CROSS JOIN UNNEST(`_t0`.`arr`) AS `_c1`
WHERE `_c0` = `_c1`                        -- `_c0` is never declared
```

`_c0` is referenced but never bound, so the emitted SQL is invalid.

## Expected behaviour

Every `UNNEST` in the chain is aliased with its canonical `_cN` name, so no
user-supplied alias survives and every name used in a predicate is also
declared:

```sql
SELECT `_t0`.`id` AS `id` FROM `_t0` AS `_t0`
CROSS JOIN UNNEST(`_t0`.`arr`) AS `_c0`
CROSS JOIN UNNEST(`_t0`.`arr`) AS `_c1`
WHERE `_c0` = `_c1`
```

A single `UNNEST`, and queries with none, are unchanged.

## Reproducing

The bug only appears through the full pipeline. Calling
`canonicalize_internal_names` on a freshly parsed expression produces identical
output before and after the fix. You need all three of:

1. `qualify()` run first, with an explicit schema,
2. the `bigquery` dialect, and
3. the `UNNEST` alias referenced as a bare column (`WHERE x = y`), not a
   qualified one (`WHERE x.a = y.a`).

```python
SCHEMA = {"t": {"id": "INT64", "arr": "ARRAY<INT64>"}}
expr = qualify(sqlglot.parse_one(sql, read="bigquery"), dialect="bigquery", schema=SCHEMA)
canonicalize_internal_names(expr).sql(dialect="bigquery")
```
