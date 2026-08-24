"""Hidden behavioral tests for oss-attrs-generator-on-setattr (attrs #1592).

An ``on_setattr`` hook may now be a *generator*: code before its ``yield`` runs
before the attribute is set, the yielded value becomes the stored value, and code
after the ``yield`` runs once the instance holds the new value. Regular (returning)
hooks are unchanged. Graded through the public attrs API (attribute values and hook
side effects).
"""

from __future__ import annotations

import attr


# --- fail_to_pass: generator hooks were not driven at the base commit ---------


def test_yielded_value_overwrites_assignment() -> None:
    def hook(instance, attribute, value):
        yield "yielded!"

    @attr.s
    class C:
        x = attr.ib(on_setattr=hook)

    c = C(x="x")
    c.x = "xxx"
    assert c.x == "yielded!"


def test_generator_hook_can_transform_value() -> None:
    def hook(instance, attribute, value):
        yield value.upper()

    @attr.s
    class C:
        x = attr.ib(on_setattr=hook)

    c = C(x="ab")
    c.x = "cd"
    assert c.x == "CD"


def test_pre_and_post_yield_bracket_the_assignment() -> None:
    calls: list[tuple[str, str]] = []

    def hook(instance, attribute, value):
        calls.append(("pre", instance.x))
        yield value
        calls.append(("post", instance.x))

    @attr.s
    class C:
        x = attr.ib(on_setattr=hook)

    c = C(x="x")
    assert calls == []  # hook not driven during __init__
    c.x = "xxx"
    assert calls == [("pre", "x"), ("post", "xxx")]


# --- pass_to_pass: ordinary returning hooks are unchanged ---------------------


def test_returning_hook_still_transforms() -> None:
    def hook(instance, attribute, value):
        return value.upper()

    @attr.s
    class C:
        x = attr.ib(on_setattr=hook)

    c = C(x="ab")
    c.x = "cd"
    assert c.x == "CD"


def test_returning_hook_identity_value() -> None:
    def hook(instance, attribute, value):
        return value

    @attr.s
    class C:
        x = attr.ib(on_setattr=hook)

    c = C(x="ab")
    c.x = "cd"
    assert c.x == "cd"
