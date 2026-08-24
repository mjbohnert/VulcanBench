"""Hidden behavioral tests for oss-lark-scan (lark #1592).

Adds ``Lark.scan(text)``: find every non-overlapping substring of ``text`` that
parses as the grammar's start rule, yielding ``ScanMatch(range, value)`` where
``range`` is the ``(start, end)`` offset pair and ``value`` is the parse tree.
Graded through the public ``scan`` API; the reconstructed tree must match
``parse``.
"""

from __future__ import annotations

import pytest
from lark import Lark
from lark.exceptions import LarkError

GRAMMAR = r"""
start: "(" ITEM* ")"
ITEM: /[a-z]/
%ignore " "
"""

TEXT = "xx (a b) yy (cd) ((z"


def _parser() -> Lark:
    return Lark(GRAMMAR, parser="lalr", start="start")


# --- fail_to_pass: scan() did not exist at the base commit --------------------


def test_scan_finds_all_bracketed_matches() -> None:
    finds = list(_parser().scan(TEXT))
    assert [m.range for m in finds] == [(3, 8), (12, 16)]
    assert [TEXT[s:e] for s, e in (m.range for m in finds)] == ["(a b)", "(cd)"]


def test_scan_returns_empty_on_no_match() -> None:
    assert list(_parser().scan("qwerty")) == []


def test_scan_value_matches_parse() -> None:
    parser = _parser()
    (match,) = list(parser.scan("(a b)"))
    assert match.value == parser.parse("(a b)")


# --- pass_to_pass: existing parse behavior is unchanged -----------------------


def test_parse_produces_start_tree() -> None:
    tree = _parser().parse("(a b)")
    assert tree.data == "start"


def test_parse_rejects_invalid_input() -> None:
    with pytest.raises(LarkError):
        _parser().parse("nope")
