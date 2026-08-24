"""Hidden behavioral tests for oss-sqlglot-semistructured-case (#8161).

Dot access into a semi-structured value (MAP / VARIANT / JSON) is a case-sensitive
*data* lookup and must keep the original field casing through
qualify + annotate_types. Dot access into a STRUCT is an identifier and is still
normalized. Graded on the public optimizer output SQL string.
"""

from __future__ import annotations

from sqlglot import parse_one
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify

SCHEMA = {"t": {"m": "MAP(VARCHAR, INT)", "v": "VARIANT", "j": "JSON", "s": "STRUCT(Foo INT)"}}


def _optimized(sql: str, dialect: str = "duckdb") -> str:
    qualified = qualify(parse_one(sql, dialect=dialect), schema=SCHEMA, dialect=dialect)
    return annotate_types(qualified, schema=SCHEMA, dialect=dialect).sql(dialect)


# --- fail_to_pass: semi-structured field case was wrongly normalized ----------


def test_map_dot_access_preserves_case() -> None:
    assert _optimized("SELECT m.Foo FROM t") == 'SELECT "t"."m"."Foo" AS "foo" FROM "t" AS "t"'


def test_variant_dot_access_preserves_case() -> None:
    assert _optimized("SELECT v.Foo FROM t") == 'SELECT "t"."v"."Foo" AS "foo" FROM "t" AS "t"'


def test_qualified_root_map_access_preserves_case() -> None:
    assert _optimized("SELECT t.m.Foo FROM t") == 'SELECT "t"."m"."Foo" AS "foo" FROM "t" AS "t"'


# --- pass_to_pass: struct fields normalize; json already preserved ------------


def test_struct_field_is_still_normalized() -> None:
    assert _optimized("SELECT s.Foo FROM t") == 'SELECT "t"."s"."foo" AS "foo" FROM "t" AS "t"'


def test_json_nested_access_case_unchanged() -> None:
    assert (
        _optimized("SELECT j.Foo.Bar FROM t")
        == 'SELECT "t"."j"."Foo"."Bar" AS "bar" FROM "t" AS "t"'
    )
