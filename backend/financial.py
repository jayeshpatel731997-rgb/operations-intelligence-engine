from __future__ import annotations


def calculate_ideal_output(operating_time: float, ideal_cycle_time: float) -> int:
    if operating_time <= 0 or ideal_cycle_time <= 0:
        return 0

    operating_seconds = operating_time * 60
    return int(operating_seconds / ideal_cycle_time)


def calculate_lost_units(
    operating_time: float,
    ideal_cycle_time: float,
    good_units: int,
) -> int:
    ideal_output = calculate_ideal_output(operating_time, ideal_cycle_time)
    return max(ideal_output - good_units, 0)


def calculate_revenue_loss(
    operating_time: float,
    ideal_cycle_time: float,
    good_units: int,
    revenue_per_unit: float,
) -> dict[str, float]:
    lost_units = calculate_lost_units(
        operating_time=operating_time,
        ideal_cycle_time=ideal_cycle_time,
        good_units=good_units,
    )
    revenue_loss = lost_units * revenue_per_unit

    return {
        "lost_units": lost_units,
        "revenue_loss": round(revenue_loss, 2),
    }


if __name__ == "__main__":
    print(
        calculate_revenue_loss(
            operating_time=435,
            ideal_cycle_time=2.4,
            good_units=9700,
            revenue_per_unit=18.5,
        )
    )
