from app.models import OeeMetrics, Telemetry


def calculate_oee(telemetry: Telemetry) -> OeeMetrics:
    planned = max(telemetry.planned_production_minutes, 1e-9)
    runtime = max(telemetry.runtime_minutes, 0)
    total = max(telemetry.total_count, 0)
    good = max(telemetry.good_count, 0)

    availability = min(max(runtime / planned, 0), 1)
    ideal_minutes = (telemetry.ideal_cycle_time_seconds * total) / 60
    performance = min(max(ideal_minutes / max(runtime, 1e-9), 0), 1)
    quality = min(max(good / max(total, 1), 0), 1)

    return OeeMetrics(
        availability=round(availability, 4),
        performance=round(performance, 4),
        quality=round(quality, 4),
        oee=round(availability * performance * quality, 4),
    )
