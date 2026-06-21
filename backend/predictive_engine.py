from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RiskBand:
    severity: str
    remaining_hours: int
    action: str


def calculate_predictive_maintenance(dataframe: pd.DataFrame) -> list[dict[str, object]]:
    if dataframe.empty:
        return []

    risk_items: list[dict[str, object]] = []
    scope_columns = [column for column in ["plant_id", "line_id", "machine_id"] if column in dataframe.columns]
    group_columns = scope_columns or ["machine"]

    for scope_values, machine_data in dataframe.groupby(group_columns, dropna=False):
        if not isinstance(scope_values, tuple):
            scope_values = (scope_values,)
        scope = dict(zip(group_columns, scope_values))
        machine = str(scope.get("machine_id") or scope.get("machine") or "unknown")

        downtime_ratio = _bounded(
            machine_data["downtime_events"].astype(float).mean()
            / machine_data["planned_time"].astype(float).mean(),
            0,
            0.45,
        )
        speed_ratio = _bounded(
            machine_data["speed_loss"].astype(float).mean()
            / machine_data["ideal_output"].astype(float).clip(lower=1).mean(),
            0,
            0.45,
        )
        defect_ratio = _bounded(
            machine_data["defect_units"].astype(float).sum()
            / machine_data["total_units"].astype(float).clip(lower=1).sum(),
            0,
            0.18,
        )
        anomaly_count = _count_anomalies(machine_data)
        anomaly_ratio = min(anomaly_count / max(len(machine_data), 1), 1)

        risk_score = (
            downtime_ratio / 0.45 * 0.34
            + speed_ratio / 0.45 * 0.24
            + defect_ratio / 0.18 * 0.22
            + anomaly_ratio * 0.20
        )
        risk_score = round(_bounded(risk_score, 0.05, 0.96), 2)
        band = _risk_band(risk_score, machine)

        risk_items.append(
            {
                "plant_id": scope.get("plant_id", "PLANT_A"),
                "line_id": scope.get("line_id", "LINE_1"),
                "machine": machine,
                "machine_id": machine,
                "failure_risk": risk_score,
                "risk_score": risk_score,
                "severity": band.severity,
                "remaining_hours": band.remaining_hours,
                "recommended_action": band.action,
                "signals": {
                    "downtime_ratio": round(downtime_ratio, 3),
                    "speed_loss_ratio": round(speed_ratio, 3),
                    "defect_ratio": round(defect_ratio, 3),
                    "anomaly_count": anomaly_count,
                },
            }
        )

    return sorted(risk_items, key=lambda item: float(item["failure_risk"]), reverse=True)


def _count_anomalies(dataframe: pd.DataFrame) -> int:
    downtime_threshold = dataframe["downtime_events"].astype(float).mean() * 1.25
    speed_threshold = dataframe["speed_loss"].astype(float).mean() * 1.25
    defect_threshold = dataframe["defect_units"].astype(float).mean() * 1.35
    return int(
        (
            (dataframe["downtime_events"].astype(float) > downtime_threshold)
            | (dataframe["speed_loss"].astype(float) > speed_threshold)
            | (dataframe["defect_units"].astype(float) > defect_threshold)
        ).sum()
    )


def _risk_band(risk_score: float, machine: str) -> RiskBand:
    if risk_score >= 0.76:
        return RiskBand(
            "HIGH",
            max(8, int(42 - risk_score * 28)),
            f"Inspect {machine} spindle motor and drive train within 2 hours.",
        )
    if risk_score >= 0.48:
        return RiskBand(
            "MEDIUM",
            max(24, int(96 - risk_score * 48)),
            f"Schedule condition check for {machine} during the next planned break.",
        )
    return RiskBand(
        "LOW",
        max(96, int(180 - risk_score * 60)),
        f"Keep {machine} on normal monitoring cadence.",
    )


def _bounded(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)
