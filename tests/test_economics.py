"""Tests for explicit API-versus-subscription economics receipts."""

from __future__ import annotations

from harness.economics import api_receipt, subscription_receipt


def test_api_receipt_records_metered_cash() -> None:
    receipt = api_receipt(1.25, 0.05).as_summary()
    assert receipt["billing_mode"] == "api-metered"
    assert receipt["marginal_cash_usd"] == 1.25
    assert receipt["api_equivalent_cost_usd"] == 1.25
    assert receipt["grading_cash_usd"] == 0.05


def test_subscription_receipt_does_not_invent_zero_cash() -> None:
    receipt = subscription_receipt(
        api_equivalent_cost_usd=0.42,
        grading_cash_usd=None,
        grading_api_equivalent_usd=0.01,
        plan_name="max",
        cli_reported_cost_usd=0.44,
    ).as_summary()
    assert receipt["billing_mode"] == "subscription-included"
    assert receipt["marginal_cash_usd"] is None
    assert receipt["allocated_plan_cost_usd"] is None
    assert receipt["api_equivalent_cost_usd"] == 0.42
    assert receipt["grading_cash_usd"] is None
    assert receipt["grading_api_equivalent_usd"] == 0.01
    assert receipt["measurement_quality"]["marginal_cash_usd"] == "unavailable"
