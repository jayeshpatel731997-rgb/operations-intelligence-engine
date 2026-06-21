from __future__ import annotations

import pandas as pd

from oee_engine import calculate_oee


SUPPORTED_ACTIONS = {
    "reduce downtime",
    "improve speed",
    "reduce defects",
    "add maintenance",
    "add shift",
}


def simulate_action(
    dataframe: pd.DataFrame,
    machine: str | None,
    action: str,
    improvement_percent: float,
    revenue_per_unit: float,
) -> dict[str, object]:
    action_key = action.strip().lower()
    if action_key not in SUPPORTED_ACTIONS:
        raise ValueError(f"Unsupported simulation action: {action}")

    improvement = min(max(float(improvement_percent), 1.0), 60.0) / 100
    current_data = dataframe.copy()
    projected_data = dataframe.copy()
    target_mask = _target_mask(projected_data, machine)
    if not target_mask.any():
        target_mask = projected_data.index == projected_data.index.max()

    current_oee = _average_oee(current_data)
    current_revenue_loss = _revenue_loss(current_data, revenue_per_unit)
    current_downtime = float(current_data.loc[target_mask, "downtime_events"].sum())

    if action_key == "reduce downtime":
        projected_data.loc[target_mask, "downtime_events"] *= 1 - improvement
    elif action_key == "improve speed":
        projected_data.loc[target_mask, "total_units"] *= 1 + improvement * 0.65
    elif action_key == "reduce defects":
        projected_data.loc[target_mask, "defect_units"] *= 1 - improvement
    elif action_key == "add maintenance":
        projected_data.loc[target_mask, "downtime_events"] *= 1 - improvement * 0.55
        projected_data.loc[target_mask, "speed_loss"] *= 1 - improvement * 0.35
    elif action_key == "add shift":
        projected_data.loc[target_mask, "planned_time"] *= 1 + improvement * 0.35
        projected_data.loc[target_mask, "total_units"] *= 1 + improvement * 0.30

    for index in projected_data.loc[target_mask].index:
        _recalculate(projected_data, index)

    projected_oee = _average_oee(projected_data)
    projected_revenue_loss = _revenue_loss(projected_data, revenue_per_unit)
    projected_downtime = float(projected_data.loc[target_mask, "downtime_events"].sum())
    revenue_saved = max(current_revenue_loss - projected_revenue_loss, 0)
    downtime_reduction = max(current_downtime - projected_downtime, 0)
    oee_gain = projected_oee - current_oee

    return {
        "machine": machine or "scope",
        "action": action_key,
        "improvement_percent": round(improvement * 100, 1),
        "current_oee": round(current_oee, 2),
        "projected_oee": round(projected_oee, 2),
        "revenue_saved": round(revenue_saved, 2),
        "formatted_revenue_saved": f"${revenue_saved:,.0f}",
        "downtime_reduction": round(downtime_reduction, 2),
        "expected_oee_gain": round(oee_gain, 2),
        "decision": "Recommended" if oee_gain >= 1.5 or revenue_saved >= 25000 else "Monitor",
    }


def _target_mask(dataframe: pd.DataFrame, machine: str | None) -> pd.Series:
    if not machine:
        return pd.Series(True, index=dataframe.index)
    machine_key = str(machine)
    if "machine_id" in dataframe.columns:
        return dataframe["machine_id"].astype(str).eq(machine_key)
    return dataframe["machine"].astype(str).eq(machine_key)


def _average_oee(dataframe: pd.DataFrame) -> float:
    if dataframe.empty:
        return 0.0
    values = []
    for record in dataframe.to_dict(orient="records"):
        values.append(
            calculate_oee(
                planned_time=float(record["planned_time"]),
                downtime=float(record["downtime_events"]),
                ideal_cycle_time=float(record["ideal_cycle_time"]),
                total_units=int(record["total_units"]),
                good_units=int(record["good_units"]),
            )["oee"]
        )
    return sum(values) / len(values)


def _revenue_loss(dataframe: pd.DataFrame, revenue_per_unit: float) -> float:
    lost_units = (dataframe["ideal_output"].astype(float) - dataframe["good_units"].astype(float)).clip(lower=0)
    return float((lost_units * revenue_per_unit).sum())


def _recalculate(dataframe: pd.DataFrame, index: object) -> None:
    planned_time = max(float(dataframe.at[index, "planned_time"]), 1)
    downtime = max(float(dataframe.at[index, "downtime_events"]), 0)
    total_units = max(int(float(dataframe.at[index, "total_units"])), 1)
    defect_units = min(max(int(float(dataframe.at[index, "defect_units"])), 0), total_units)
    ideal_cycle_time = max(float(dataframe.at[index, "ideal_cycle_time"]), 0.01)
    operating_time = max(planned_time - downtime, 1)
    ideal_output = int(operating_time * 60 / ideal_cycle_time)

    dataframe.at[index, "operating_time"] = operating_time
    dataframe.at[index, "total_units"] = total_units
    dataframe.at[index, "defect_units"] = defect_units
    dataframe.at[index, "good_units"] = max(total_units - defect_units, 0)
    dataframe.at[index, "ideal_output"] = ideal_output
    dataframe.at[index, "speed_loss"] = max(ideal_output - total_units, 0)
