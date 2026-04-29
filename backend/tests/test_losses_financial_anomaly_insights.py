import pytest

from app.anomaly import AnomalyDetector
from app.financial import calculate_financial_impact
from app.insights import fallback_insight
from app.losses import classify_losses
from app.models import EventType, Telemetry
from app.oee import calculate_oee


def make_telemetry(**overrides):
    base = {
        "runtime_minutes": 90,
        "planned_production_minutes": 100,
        "downtime_minutes": 10,
        "total_count": 2000,
        "good_count": 1850,
        "reject_count": 150,
        "ideal_cycle_time_seconds": 2.4,
        "actual_cycle_time_seconds": 3.0,
        "current_rate_per_minute": 20,
        "target_rate_per_minute": 25,
        "last_event_type": EventType.production_reject,
        "last_event_message": "reject spike",
    }
    base.update(overrides)
    return Telemetry(**base)


def test_loss_classifier_returns_six_big_losses() -> None:
    losses = classify_losses(make_telemetry(), unit_value_dollars=10)

    assert {loss.category for loss in losses} == {
        "Breakdowns",
        "Setup and adjustments",
        "Small stops",
        "Reduced speed",
        "Startup rejects",
        "Production rejects",
    }
    assert max(losses, key=lambda item: item.dollars).dollars > 0


def test_financial_impact_calculates_lost_units_and_dollars() -> None:
    impact = calculate_financial_impact(make_telemetry(), unit_value_dollars=10, operating_cost_per_hour_dollars=120)

    assert impact.lost_units == 650
    assert impact.revenue_loss_dollars == 6500
    assert impact.operating_loss_dollars == 20
    assert impact.total_loss_dollars == 6520


def test_anomaly_detector_flags_oee_drop() -> None:
    detector = AnomalyDetector(window_size=10)
    for _ in range(6):
        healthy = make_telemetry(runtime_minutes=98, downtime_minutes=2, total_count=2400, good_count=2380, reject_count=20, actual_cycle_time_seconds=2.4)
        detector.detect(healthy, calculate_oee(healthy))

    degraded = make_telemetry(runtime_minutes=70, downtime_minutes=30, total_count=1600, good_count=1450, reject_count=150, actual_cycle_time_seconds=3.4)
    anomalies = detector.detect(degraded, calculate_oee(degraded))

    assert {anomaly.type for anomaly in anomalies} >= {"oee_drop", "speed_degradation"}


@pytest.mark.asyncio
async def test_fallback_insight_is_deterministic_without_api_key() -> None:
    telemetry = make_telemetry()
    oee = calculate_oee(telemetry)
    losses = classify_losses(telemetry, unit_value_dollars=10)
    financial = calculate_financial_impact(telemetry, 10, 120)

    insight = fallback_insight(telemetry, oee, losses, financial, [])

    assert insight.provider == "fallback"
    assert "OEE is" in insight.summary
    assert insight.recommended_actions
