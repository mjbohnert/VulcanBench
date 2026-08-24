"""Hidden behavioral tests for oss-lark-earley-ambiguous-ignore (lark #1577).

With the dynamic (Earley) lexer, ignored tokens that overlap real tokens can make
one input parse several ways. The Earley parser crashed on this
("Earley should not generate multiple start symbol items!") instead of producing
the ambiguity. Graded through the public ``Lark(...).parse`` output.
"""

from __future__ import annotations

from lark import Lark

# "foo12" can be read as foo + ignored "12", foo1 + ignored "2", or foo12.
GRAMMAR = r"""
!start: "foo1" | "foo" | "foo12"
%ignore "1"
%ignore "2"
"""


def _leaf(tree) -> str:
    return str(tree.children[0])


# --- fail_to_pass: the parser crashed on ambiguous-ignore input ---------------


def test_explicit_ambiguity_yields_all_readings() -> None:
    tree = Lark(GRAMMAR, ambiguity="explicit").parse("foo12")
    assert tree.data == "_ambig"
    assert {_leaf(c) for c in tree.children} == {"foo", "foo1", "foo12"}


def test_resolve_picks_a_single_reading() -> None:
    tree = Lark(GRAMMAR, ambiguity="resolve").parse("foo12")
    assert tree.data == "start"
    assert _leaf(tree) == "foo1"


def test_rule_body_ambiguity_yields_all_readings() -> None:
    grammar = r"""
    !start: a "b"
    !a: "a" | "a1" | "a12"
    %ignore "1"
    %ignore "2"
    """
    tree = Lark(grammar, ambiguity="explicit").parse("a12b")
    assert tree.data == "_ambig"
    assert len(tree.children) == 3


# --- pass_to_pass: unambiguous parsing is unaffected --------------------------


def test_unambiguous_input_parses() -> None:
    tree = Lark(GRAMMAR, ambiguity="explicit").parse("foo")
    assert tree.data == "start"
    assert _leaf(tree) == "foo"


def test_plain_grammar_unaffected() -> None:
    tree = Lark(r'start: "x" "y"', ambiguity="explicit").parse("xy")
    assert tree.data == "start"
