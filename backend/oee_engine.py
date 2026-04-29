from __future__ import annotations


def calculate_availability(planned_time: float, downtime: float) -> float:
    if planned_time <= 0:
        return 0.0

    operating_time = max(planned_time - downtime, 0)
    return round((operating_time / planned_time) * 100, 2)


def calculate_performance(
    planned_time: float,
    downtime: float,
    ideal_cycle_time: float,
    total_units: int,
) -> float:
    operating_time = max(planned_time - downtime, 0)
    if operating_time <= 0 or ideal_cycle_time <= 0:
        return 0.0

    operating_seconds = operating_time * 60
    performance = (ideal_cycle_time * total_units / operating_seconds) * 100
    return round(min(performance, 100), 2)


def calculate_quality(total_units: int, good_units: int) -> float:
    if total_units <= 0:
        return 0.0

    quality = (good_units / total_units) * 100
    return round(min(max(quality, 0), 100), 2)


def calculate_oee(
    planned_time: float,
    downtime: float,
    ideal_cycle_time: float,
    total_units: int,
    good_units: int,
) -> dict[str, float]:
    availability = calculate_availability(planned_time, downtime)
    performance = calculate_performance(
        planned_time,
        downtime,
        ideal_cycle_time,
        total_units,
    )
    quality = calculate_quality(total_units, good_units)
    oee = (availability / 100) * (performance / 100) * (quality / 100) * 100

    return {
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": round(oee, 2),
    }


if __name__ == "__main__":
    print(
        calculate_oee(
            planned_time=480,
            downtime=45,
            ideal_cycle_time=2.4,
            total_units=10000,
            good_units=9700,
        )
    )
