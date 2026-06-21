from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from main import app
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


def test_summary_report_includes_machine_metrics_and_alert_panel() -> None:
    summary = build_summary_report()

    assert {item["machine"] for item in summary["machine_metrics"]} == {"M1", "M2", "M3"}
    assert len(summary["critical_alerts"]) == 3
    for alert in summary["critical_alerts"]:
        assert alert["severity"] in {"HIGH", "MEDIUM"}
        assert alert["action"]
        assert isinstance(alert["financial_impact"], (int, float))


def test_scenario_query_changes_loss_profile() -> None:
    with TestClient(app) as client:
        normal = client.get("/ai-summary?scenario=normal").json()
        breakdown = client.get("/ai-summary?scenario=breakdown_spike").json()
        quality = client.get("/ai-summary?scenario=quality_issue").json()

    assert breakdown["scenario"] == "breakdown_spike"
    assert quality["scenario"] == "quality_issue"
    assert breakdown["top_losses"][0]["loss_category"] == "breakdown loss"
    assert any("quality" in alert["issue"].lower() for alert in quality["critical_alerts"])


def test_summary_accepts_date_filters_with_generated_data() -> None:
    with TestClient(app) as client:
        response = client.get("/ai-summary?start_date=2026-04-28&end_date=2026-04-29&scenario=normal")

    assert response.status_code == 200
    assert "machine_metrics" in response.json()


def test_platform_endpoints_return_predictive_simulation_and_reports() -> None:
    with TestClient(app) as client:
        predictive = client.get("/predictive-maintenance?plant_id=PLANT_A&line_id=LINE_1&machine_id=M3").json()
        simulation = client.post(
            "/simulate",
            json={"plant_id": "PLANT_A", "line_id": "LINE_1", "machine": "M3", "action": "reduce downtime", "improvement_percent": 20},
        ).json()
        decision = client.get("/ai-decision?plant_id=PLANT_A&line_id=LINE_1&machine_id=M3").json()
        csv_report = client.get("/export-report?format=csv")
        pdf_report = client.get("/export-report?format=pdf")

    assert predictive
    assert predictive[0]["machine"] == "M3"
    assert 0 <= predictive[0]["failure_risk"] <= 1
    assert predictive[0]["severity"] in {"HIGH", "MEDIUM", "LOW"}
    assert simulation["decision"] in {"Recommended", "Monitor"}
    assert simulation["projected_oee"] >= 0
    assert decision["recommended_action"]
    assert isinstance(decision["estimated_savings"], (int, float))
    assert csv_report.status_code == 200
    assert "text/csv" in csv_report.headers["content-type"]
    assert pdf_report.status_code == 200
    assert pdf_report.headers["content-type"] == "application/pdf"
