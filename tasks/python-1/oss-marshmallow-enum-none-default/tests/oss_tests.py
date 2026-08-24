"""Hidden behavioral tests for oss-marshmallow-enum-none-default (#2994).

When a marshmallow ``Enum`` field is by-value and the enum has a member whose
value is ``None``, ``allow_none`` should default to ``True`` so that ``None``
round-trips instead of failing validation — unless the caller set ``allow_none``
explicitly. Graded through the public field / schema deserialize API.
"""

from __future__ import annotations

from enum import Enum

import pytest
from marshmallow import Schema, ValidationError, fields


class Maybe(Enum):
    yes = "y"
    no = None  # a member whose value is None


class NoNone(Enum):
    a = "a"
    b = "b"


# --- fail_to_pass: None was rejected at the base commit -----------------------


def test_by_value_true_allows_none() -> None:
    field = fields.Enum(Maybe, by_value=True)
    assert field.deserialize(None) is None


def test_by_value_field_allows_none() -> None:
    field = fields.Enum(Maybe, by_value=fields.String)
    assert field.deserialize(None) is None


def test_schema_load_allows_none() -> None:
    class S(Schema):
        x = fields.Enum(Maybe, by_value=True)

    assert S().load({"x": None}) == {"x": None}


# --- pass_to_pass: unchanged behavior -----------------------------------------


def test_explicit_allow_none_false_still_rejects() -> None:
    """An explicit allow_none=False must be honored, not overridden."""
    field = fields.Enum(Maybe, by_value=True, allow_none=False)
    with pytest.raises(ValidationError):
        field.deserialize(None)


def test_enum_without_none_member_still_rejects_none() -> None:
    """An enum with no None-valued member keeps rejecting None by default."""
    field = fields.Enum(NoNone, by_value=True)
    with pytest.raises(ValidationError):
        field.deserialize(None)
