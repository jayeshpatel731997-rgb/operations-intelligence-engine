from app.models import EventType, Telemetry
from app.oee import calculate_oee


def test_calculate_oee_components() -> None:
    telemetry = Telemetry(
        runtime_minutes=90,
        planned_production_minutes=100,
        downtime_minutes=10,
        total_count=2000,
        good_count=1900,
        reject_count=100,
        ideal_cycle_time_seconds=2.4,
        actual_cycle_time_seconds=2.7,
        current_rate_per_minute=22,
        target_rate_per_minute=25,
        last_event_type=EventType.normal,
        last_event_message="ok",
    )

    result = calculate_oee(telemetry)

    assert result.availability == 0.9
    assert result.performance == 0.8889
    assert result.quality == 0.95
    assert result.oee == 0.76
