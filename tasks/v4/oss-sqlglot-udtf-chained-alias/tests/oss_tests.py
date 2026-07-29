"""Hidden grader tests for canonicalize_internal_names over chained correlated
UNNESTs.

A UDTF source can appear in more than one scope. Each scope was assigned its own
column map, so only the last UNNEST in a chain had its alias rewritten -- the
earlier ones kept their user-supplied alias while predicates already referenced
the canonical `_cN` name, leaving a dangling reference.

Expected SQL is generated from the gold patch.
"""

import sqlglot
from sqlglot.optimizer.canonicalize_internal_names import canonicalize_internal_names
from sqlglot.optimizer.qualify import qualify

SCHEMA = {"t": {"id": "INT64", "arr": "ARRAY<INT64>"}}


def canonicalize(sql):
    expr = qualify(sqlglot.parse_one(sql, read="bigquery"), dialect="bigquery", schema=SCHEMA)
    return canonicalize_internal_names(expr).sql(dialect="bigquery")


def test_two_chained_unnests_are_fully_aliased():
    got = canonicalize(
        "SELECT e.id FROM t AS e, UNNEST(e.arr) AS x, UNNEST(e.arr) AS y WHERE x = y"
    )
    assert got == (
        "SELECT `_t0`.`id` AS `id` FROM `_t0` AS `_t0` "
        "CROSS JOIN UNNEST(`_t0`.`arr`) AS `_c0` "
        "CROSS JOIN UNNEST(`_t0`.`arr`) AS `_c1` "
        "WHERE `_c0` = `_c1`"
    )


def test_three_chained_unnests_are_fully_aliased():
    got = canonicalize(
        "SELECT e.id FROM t AS e, UNNEST(e.arr) AS x, UNNEST(e.arr) AS y, "
        "UNNEST(e.arr) AS z WHERE x = y AND y = z"
    )
    assert got == (
        "SELECT `_t0`.`id` AS `id` FROM `_t0` AS `_t0` "
        "CROSS JOIN UNNEST(`_t0`.`arr`) AS `_c0` "
        "CROSS JOIN UNNEST(`_t0`.`arr`) AS `_c1` "
        "CROSS JOIN UNNEST(`_t0`.`arr`) AS `_c2` "
        "WHERE `_c0` = `_c1` AND `_c1` = `_c2`"
    )


def test_no_user_alias_survives_canonicalization():
    got = canonicalize(
        "SELECT e.id FROM t AS e, UNNEST(e.arr) AS x, UNNEST(e.arr) AS y WHERE x = y"
    )
    for alias in ("`x`", "`y`"):
        assert alias not in got


def test_every_referenced_name_is_declared():
    # No dangling reference: each `_cN` used in the predicate is also an alias.
    got = canonicalize(
        "SELECT e.id FROM t AS e, UNNEST(e.arr) AS x, UNNEST(e.arr) AS y WHERE x = y"
    )
    where = got.split("WHERE", 1)[1]
    for name in ("`_c0`", "`_c1`"):
        assert name in where
        assert f"AS {name}" in got
