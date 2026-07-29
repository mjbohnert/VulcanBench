"""Regression guard: a single UNNEST and queries with none at all.

Neither involves a UDTF appearing in more than one scope, so this passes at the
base commit.
"""

import sqlglot
from sqlglot.optimizer.canonicalize_internal_names import canonicalize_internal_names
from sqlglot.optimizer.qualify import qualify

SCHEMA = {"t": {"id": "INT64", "arr": "ARRAY<INT64>"}}


def canonicalize(sql):
    expr = qualify(sqlglot.parse_one(sql, read="bigquery"), dialect="bigquery", schema=SCHEMA)
    return canonicalize_internal_names(expr).sql(dialect="bigquery")


def test_single_unnest_is_aliased():
    got = canonicalize("SELECT e.id FROM t AS e, UNNEST(e.arr) AS x WHERE x = 1")
    assert got == (
        "SELECT `_t0`.`id` AS `id` FROM `_t0` AS `_t0` "
        "CROSS JOIN UNNEST(`_t0`.`arr`) AS `_c0` WHERE `_c0` = 1"
    )


def test_query_without_unnest_is_unchanged():
    got = canonicalize("SELECT e.id FROM t AS e WHERE e.id = 1")
    assert got == "SELECT `_t0`.`id` AS `id` FROM `_t0` AS `_t0` WHERE `_t0`.`id` = 1"


def test_table_source_is_canonicalized():
    got = canonicalize("SELECT e.id FROM t AS e")
    assert "`_t0`" in got and "`e`" not in got
