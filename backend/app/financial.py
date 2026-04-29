from app.models import FinancialImpact, Telemetry


def calculate_financial_impact(
    telemetry: Telemetry,
    unit_value_dollars: float,
    operating_cost_per_hour_dollars: float,
) -> FinancialImpact:
    target_units = int(
        telemetry.planned_production_minutes
        * 60
        / max(telemetry.ideal_cycle_time_seconds, 1e-9)
    )
    lost_units = max(target_units - telemetry.good_count, 0)
    revenue_loss = lost_units * unit_value_dollars
    operating_loss = (telemetry.downtime_minutes / 60) * operating_cost_per_hour_dollars

    return FinancialImpact(
        lost_units=lost_units,
        revenue_loss_dollars=round(revenue_loss, 2),
        operating_loss_dollars=round(operating_loss, 2),
        total_loss_dollars=round(revenue_loss + operating_loss, 2),
    )
