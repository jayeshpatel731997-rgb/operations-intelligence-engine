from __future__ import annotations


def classify_downtime_loss(downtime: float, impact: float) -> dict[str, float | str]:
    return {
        "loss_category": "breakdown loss",
        "duration": round(max(downtime, 0), 2),
        "impact": round(max(impact, 0), 2),
    }


def classify_speed_loss(
    operating_time: float,
    ideal_cycle_time: float,
    total_units: int,
    impact_per_unit: float,
) -> dict[str, float | str]:
    if operating_time <= 0 or ideal_cycle_time <= 0:
        lost_units = 0
    else:
        ideal_units = int((operating_time * 60) / ideal_cycle_time)
        lost_units = max(ideal_units - total_units, 0)

    duration = lost_units * ideal_cycle_time / 60

    return {
        "loss_category": "performance loss",
        "duration": round(duration, 2),
        "impact": round(lost_units * impact_per_unit, 2),
    }


def classify_defect_loss(
    total_units: int,
    good_units: int,
    ideal_cycle_time: float,
    impact_per_unit: float,
) -> dict[str, float | str]:
    defective_units = max(total_units - good_units, 0)
    duration = defective_units * ideal_cycle_time / 60

    return {
        "loss_category": "quality loss",
        "duration": round(duration, 2),
        "impact": round(defective_units * impact_per_unit, 2),
    }


def classify_losses(
    downtime: float,
    operating_time: float,
    ideal_cycle_time: float,
    total_units: int,
    good_units: int,
    impact_per_unit: float,
    downtime_impact: float | None = None,
) -> list[dict[str, float | str]]:
    downtime_cost = downtime_impact
    if downtime_cost is None:
        downtime_cost = (downtime * 60 / ideal_cycle_time) * impact_per_unit if ideal_cycle_time > 0 else 0

    return [
        classify_downtime_loss(downtime, downtime_cost),
        classify_speed_loss(operating_time, ideal_cycle_time, total_units, impact_per_unit),
        classify_defect_loss(total_units, good_units, ideal_cycle_time, impact_per_unit),
    ]


if __name__ == "__main__":
    print(
        classify_losses(
            downtime=45,
            operating_time=435,
            ideal_cycle_time=2.4,
            total_units=10000,
            good_units=9700,
            impact_per_unit=18.5,
        )
    )
