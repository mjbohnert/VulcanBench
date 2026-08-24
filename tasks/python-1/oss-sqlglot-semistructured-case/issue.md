# Optimizer lower-cases field names in semi-structured data access

When the optimizer qualifies and annotates a query, it normalizes identifiers
(lower-casing them for case-insensitive dialects like DuckDB). That is correct for
column and struct-field *identifiers*, but **wrong** for dot access into
semi-structured values — `MAP`, `VARIANT`, and `JSON`. There the key after the dot
is a case-sensitive *data* lookup, not an identifier, so its casing must be
preserved.

Given a table `t` with columns `m MAP(VARCHAR, INT)`, `v VARIANT`, `j JSON`, and
`s STRUCT(Foo INT)`, on the `duckdb` dialect:

```
SELECT m.Foo FROM t
-- currently:  SELECT "t"."m"."foo" AS "foo" FROM "t" AS "t"   (Foo wrongly lowercased)
-- expected:   SELECT "t"."m"."Foo" AS "foo" FROM "t" AS "t"
```

## Expected behavior (qualify + annotate_types, duckdb dialect)

- MAP access preserves case:
  `SELECT m.Foo FROM t` → `SELECT "t"."m"."Foo" AS "foo" FROM "t" AS "t"`
- VARIANT access preserves case:
  `SELECT v.Foo FROM t` → `SELECT "t"."v"."Foo" AS "foo" FROM "t" AS "t"`
- This holds when the root is already qualified:
  `SELECT t.m.Foo FROM t` → `SELECT "t"."m"."Foo" AS "foo" FROM "t" AS "t"`
- Unchanged: a STRUCT field is a normal identifier and is still normalized:
  `SELECT s.Foo FROM t` → `SELECT "t"."s"."foo" AS "foo" FROM "t" AS "t"`
- Unchanged: JSON nested access keeps its casing:
  `SELECT j.Foo.Bar FROM t` → `SELECT "t"."j"."Foo"."Bar" AS "bar" FROM "t" AS "t"`

Stop the optimizer from normalizing the field parts of semi-structured (MAP /
VARIANT / JSON) dot access, while leaving STRUCT field identifiers normalized.
