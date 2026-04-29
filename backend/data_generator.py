from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import random


MACHINES = {
    "M1": {"ideal_cycle_time": 2.4, "planned_time": 480},
    "M2": {"ideal_cycle_time": 3.1, "planned_time": 480},
    "M3": {"ideal_cycle_time": 1.9, "planned_time": 480},
}


def generate_production_data(days: int = 30, seed: int | None = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    start_date = date.today() - timedelta(days=days - 1)
    rows = []

    for day_index in range(days):
        production_date = start_date + timedelta(days=day_index)

        for machine_id, config in MACHINES.items():
            planned_time = config["planned_time"]
            ideal_cycle_time = config["ideal_cycle_time"]

            base_downtime = rng.uniform(12, 45)
            downtime_spike = rng.uniform(35, 110) if rng.random() < 0.16 else 0
            downtime_events = round(base_downtime + downtime_spike, 2)

            speed_fluctuation = rng.uniform(0.86, 1.14)
            available_minutes = max(planned_time - downtime_events, 0)
            theoretical_units = available_minutes * 60 / ideal_cycle_time
            total_units = max(int(theoretical_units * speed_fluctuation), 0)

            base_defect_rate = rng.uniform(0.01, 0.045)
            defect_variation = rng.uniform(0.03, 0.085) if rng.random() < 0.12 else 0
            defect_rate = min(base_defect_rate + defect_variation, 0.18)
            good_units = max(int(total_units * (1 - defect_rate)), 0)

            rows.append(
                {
                    "date": production_date.isoformat(),
                    "machine": machine_id,
                    "planned_time": planned_time,
                    "downtime_events": downtime_events,
                    "ideal_cycle_time": ideal_cycle_time,
                    "total_units": total_units,
                    "good_units": good_units,
                }
            )

    return pd.DataFrame(rows)


if __name__ == "__main__":
    print(generate_production_data().head(10))
