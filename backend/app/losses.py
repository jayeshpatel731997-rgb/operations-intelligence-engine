from app.models import EventType, LossItem, Telemetry

LOSS_LABELS = {
    EventType.breakdown: "Breakdowns",
    EventType.setup_adjustment: "Setup and adjustments",
    EventType.small_stop: "Small stops",
    EventType.reduced_speed: "Reduced speed",
    EventType.startup_reject: "Startup rejects",
    EventType.production_reject: "Production rejects",
}


def classify_losses(telemetry: Telemetry, unit_value_dollars: float) -> list[LossItem]:
    downtime_units = int(
        telemetry.downtime_minutes
        * 60
        / max(telemetry.ideal_cycle_time_seconds, 1e-9)
    )
    speed_loss_units = max(
        int((telemetry.actual_cycle_time_seconds - telemetry.ideal_cycle_time_seconds) * telemetry.total_count / 60),
        0,
    )
    reject_units = telemetry.reject_count

    losses = [
        LossItem(
            category="Breakdowns",
            minutes=round(telemetry.downtime_minutes * 0.55, 2),
            units=int(downtime_units * 0.55),
            dollars=round(downtime_units * 0.55 * unit_value_dollars, 2),
            description="Unplanned stops and mechanical or control faults.",
        ),
        LossItem(
            category="Setup and adjustments",
            minutes=round(telemetry.downtime_minutes * 0.2, 2),
            units=int(downtime_units * 0.2),
            dollars=round(downtime_units * 0.2 * unit_value_dollars, 2),
            description="Changeovers, calibration, and restart stabilization.",
        ),
        LossItem(
            category="Small stops",
            minutes=round(telemetry.downtime_minutes * 0.25, 2),
            units=int(downtime_units * 0.25),
            dollars=round(downtime_units * 0.25 * unit_value_dollars, 2),
            description="Short interruptions, jams, starvation, and micro-stops.",
        ),
        LossItem(
            category="Reduced speed",
            minutes=round(max(telemetry.actual_cycle_time_seconds - telemetry.ideal_cycle_time_seconds, 0) * telemetry.total_count / 60, 2),
            units=speed_loss_units,
            dollars=round(speed_loss_units * unit_value_dollars, 2),
            description="Running below the ideal cycle rate.",
        ),
        LossItem(
            category="Startup rejects",
            minutes=0,
            units=int(reject_units * 0.25),
            dollars=round(reject_units * 0.25 * unit_value_dollars, 2),
            description="Scrap generated during ramp-up and stabilization.",
        ),
        LossItem(
            category="Production rejects",
            minutes=0,
            units=int(reject_units * 0.75),
            dollars=round(reject_units * 0.75 * unit_value_dollars, 2),
            description="Scrap generated during steady-state production.",
        ),
    ]

    if telemetry.last_event_type in LOSS_LABELS:
        active_category = LOSS_LABELS[telemetry.last_event_type]
        return [
            loss.model_copy(
                update={"description": f"{loss.description} Current signal: {telemetry.last_event_message}"}
            )
            if loss.category == active_category
            else loss
            for loss in losses
        ]

    return losses
