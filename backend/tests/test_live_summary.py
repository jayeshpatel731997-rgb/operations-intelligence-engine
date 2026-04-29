from __future__ import annotations

from datetime import datetime

from main import build_summary_report


def test_summary_report_includes_live_timestamp_and_financial_contract() -> None:
    summary = build_summary_report()

    assert datetime.fromisoformat(str(summary["last_updated"]))
    assert summary["trend_direction"] in {"increase", "decrease", "stable"}
    assert isinstance(summary["financial"], dict)
    assert isinstance(summary["financial"]["revenue_loss"], (int, float))
    assert summary["financial"]["revenue_loss"] >= 0
    assert summary["financial"]["formatted"].startswith("$")


def test_summary_report_changes_between_requests_with_realistic_oee() -> None:
    first = build_summary_report()
    second = build_summary_report()

    assert 75 <= first["current_oee"] <= 95
    assert 75 <= second["current_oee"] <= 95
    assert (
        first["current_oee"] != second["current_oee"]
        or first["financial"]["revenue_loss"] != second["financial"]["revenue_loss"]
        or first["last_updated"] != second["last_updated"]
    )
