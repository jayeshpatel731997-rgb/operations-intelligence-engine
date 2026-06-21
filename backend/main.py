from __future__ import annotations

import asyncio
import csv
import io
import logging
import random
from datetime import datetime, timezone

import pandas as pd
from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_agent import generate_operations_insight
from ai_decision import generate_decision_summary
from anomaly import detect_anomalies
from data_generator import generate_production_data
from event_engine import build_event, build_machine_health, get_event_history
from financial import calculate_revenue_loss
from loss_classifier import classify_losses
from oee_engine import calculate_oee
from predictive_engine import calculate_predictive_maintenance
from reporting_engine import build_report_csv, build_report_pdf
from simulation_engine import simulate_action


REVENUE_PER_UNIT = 18.5
SCENARIOS = {"normal", "breakdown_spike", "quality_issue"}
PLANT_LINES = {
    "PLANT_A": {
        "label": "Austin Cell A",
        "lines": {"LINE_1": "Body Line", "LINE_2": "Final Assembly"},
        "factor": 1.0,
    },
    "PLANT_B": {
        "label": "Detroit Cell B",
        "lines": {"LINE_1": "Machining Line", "LINE_2": "Pack Line"},
        "factor": 0.94,
    },
}
REQUIRED_UPLOAD_COLUMNS = {
    "date",
    "machine",
    "output",
    "downtime",
    "defects",
    "ideal_cycle_time",
}
UPLOADED_DATA: pd.DataFrame | None = None
logger = logging.getLogger("operations_intelligence.websocket")


class SimulationRequest(BaseModel):
    machine: str | None = None
    machine_id: str | None = None
    plant_id: str | None = None
    line_id: str | None = None
    action: str = Field(..., min_length=3)
    improvement_percent: float = Field(20, ge=1, le=60)

app = FastAPI(title="Operations Intelligence Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_production_data() -> pd.DataFrame:
    base_dataframe = generate_production_data(days=30, seed=None)
    expanded_rows = []
    for plant_id, plant_config in PLANT_LINES.items():
        for line_index, line_id in enumerate(plant_config["lines"]):
            scoped = base_dataframe.copy()
            plant_factor = float(plant_config["factor"])
            line_factor = 1 + (line_index * 0.035)
            scoped["plant_id"] = plant_id
            scoped["plant_name"] = plant_config["label"]
            scoped["line_id"] = line_id
            scoped["line_name"] = plant_config["lines"][line_id]
            scoped["machine_id"] = scoped["machine"].astype(str)
            scoped["downtime_events"] = (scoped["downtime_events"].astype(float) * (1 / plant_factor) * line_factor).round(2)
            scoped["total_units"] = (scoped["total_units"].astype(float) * plant_factor / line_factor).round().astype(int)
            scoped["good_units"] = scoped["good_units"].clip(upper=scoped["total_units"])
            expanded_rows.append(scoped)

    dataframe = pd.concat(expanded_rows, ignore_index=True)
    dataframe["operating_time"] = dataframe["planned_time"] - dataframe["downtime_events"]
    dataframe["defect_units"] = dataframe["total_units"] - dataframe["good_units"]
    dataframe["ideal_output"] = (
        dataframe["operating_time"] * 60 / dataframe["ideal_cycle_time"]
    ).astype(int)
    dataframe["speed_loss"] = (
        dataframe["ideal_output"] - dataframe["total_units"]
    ).clip(lower=0)
    return dataframe


def get_data_source() -> pd.DataFrame:
    if UPLOADED_DATA is not None:
        return apply_live_variation(UPLOADED_DATA.copy())
    return apply_live_variation(get_production_data())


def normalize_scenario(scenario: str | None) -> str:
    scenario_key = (scenario or "normal").strip().lower()
    if scenario_key not in SCENARIOS:
        raise HTTPException(status_code=400, detail="Invalid scenario")
    return scenario_key


def apply_live_variation(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = dataframe.copy()
    if dataframe.empty:
        return dataframe

    rng = random.Random()
    minute_wave = 1 + ((datetime.now().minute % 10) - 5) * 0.002

    for index in dataframe.index:
        downtime = max(float(dataframe.at[index, "downtime_events"]), 0)
        total_units = max(int(dataframe.at[index, "total_units"]), 0)
        planned_time = max(float(dataframe.at[index, "planned_time"]), 1)
        ideal_cycle_time = max(float(dataframe.at[index, "ideal_cycle_time"]), 0.01)
        current_defects = max(int(dataframe.at[index, "defect_units"]), 0)

        downtime_factor = min(max(rng.uniform(0.92, 1.08) * minute_wave, 0.85), 1.15)
        unit_factor = min(max(rng.uniform(0.97, 1.03) / minute_wave, 0.94), 1.06)
        defect_factor = rng.uniform(0.85, 1.15)

        varied_downtime = min(round(downtime * downtime_factor, 2), planned_time * 0.22)
        varied_total_units = max(int(round(total_units * unit_factor)), 1)
        varied_defects = min(
            max(int(round(current_defects * defect_factor + rng.randint(-2, 2))), 0),
            int(varied_total_units * 0.08),
        )
        operating_time = max(planned_time - varied_downtime, 1)
        ideal_output = int(operating_time * 60 / ideal_cycle_time)

        dataframe.at[index, "downtime_events"] = varied_downtime
        dataframe.at[index, "total_units"] = varied_total_units
        dataframe.at[index, "defect_units"] = varied_defects
        dataframe.at[index, "good_units"] = max(varied_total_units - varied_defects, 0)
        dataframe.at[index, "operating_time"] = operating_time
        dataframe.at[index, "ideal_output"] = ideal_output
        dataframe.at[index, "speed_loss"] = max(ideal_output - varied_total_units, 0)

    return dataframe


def apply_scenario(dataframe: pd.DataFrame, scenario: str | None = None) -> pd.DataFrame:
    scenario_key = normalize_scenario(scenario)
    dataframe = dataframe.copy()
    if dataframe.empty or scenario_key == "normal":
        return dataframe

    if scenario_key == "breakdown_spike":
        target_mask = dataframe["machine_id"].astype(str).eq("M2") if "machine_id" in dataframe.columns else dataframe["machine"].astype(str).eq("M2")
        if not target_mask.any():
            target_mask = dataframe.index == dataframe.index.max()
        for index in dataframe[target_mask].index:
            planned_time = max(float(dataframe.at[index, "planned_time"]), 1)
            dataframe.at[index, "downtime_events"] = min(
                round(float(dataframe.at[index, "downtime_events"]) * 1.65 + 18, 2),
                planned_time * 0.35,
            )
            dataframe.at[index, "total_units"] = max(int(float(dataframe.at[index, "total_units"]) * 0.93), 1)
            recalculate_row(dataframe, index)

    if scenario_key == "quality_issue":
        target_mask = dataframe["machine_id"].astype(str).eq("M3") if "machine_id" in dataframe.columns else dataframe["machine"].astype(str).eq("M3")
        if not target_mask.any():
            target_mask = dataframe.index == dataframe.index.max()
        for index in dataframe[target_mask].index:
            total_units = max(int(dataframe.at[index, "total_units"]), 1)
            added_defects = max(int(total_units * 0.055), 25)
            dataframe.at[index, "defect_units"] = min(
                int(dataframe.at[index, "defect_units"]) + added_defects,
                int(total_units * 0.12),
            )
            recalculate_row(dataframe, index)

    return dataframe


def recalculate_row(dataframe: pd.DataFrame, index: object) -> None:
    planned_time = max(float(dataframe.at[index, "planned_time"]), 1)
    downtime = max(float(dataframe.at[index, "downtime_events"]), 0)
    total_units = max(int(dataframe.at[index, "total_units"]), 1)
    defect_units = min(max(int(dataframe.at[index, "defect_units"]), 0), total_units)
    ideal_cycle_time = max(float(dataframe.at[index, "ideal_cycle_time"]), 0.01)
    operating_time = max(planned_time - downtime, 1)
    ideal_output = int(operating_time * 60 / ideal_cycle_time)

    dataframe.at[index, "operating_time"] = operating_time
    dataframe.at[index, "good_units"] = max(total_units - defect_units, 0)
    dataframe.at[index, "ideal_output"] = ideal_output
    dataframe.at[index, "speed_loss"] = max(ideal_output - total_units, 0)


def parse_uploaded_data(upload_file: UploadFile) -> pd.DataFrame:
    try:
        dataframe = pd.read_csv(upload_file.file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to parse CSV: {exc}")

    missing = REQUIRED_UPLOAD_COLUMNS - set(dataframe.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required columns: {', '.join(sorted(missing))}",
        )

    dataframe = dataframe.copy()
    dataframe["date"] = pd.to_datetime(dataframe["date"], errors="coerce")
    if dataframe["date"].isna().any():
        raise HTTPException(status_code=400, detail="Invalid date values in CSV")

    dataframe["machine"] = dataframe["machine"].astype(str)
    dataframe["machine_id"] = dataframe["machine_id"].astype(str) if "machine_id" in dataframe.columns else dataframe["machine"]
    dataframe["plant_id"] = dataframe["plant_id"].astype(str) if "plant_id" in dataframe.columns else "PLANT_A"
    dataframe["line_id"] = dataframe["line_id"].astype(str) if "line_id" in dataframe.columns else "LINE_1"
    dataframe["plant_name"] = dataframe["plant_name"].astype(str) if "plant_name" in dataframe.columns else "Uploaded Plant"
    dataframe["line_name"] = dataframe["line_name"].astype(str) if "line_name" in dataframe.columns else "Uploaded Line"
    dataframe["output"] = pd.to_numeric(dataframe["output"], errors="coerce").fillna(0).astype(int)
    dataframe["downtime"] = pd.to_numeric(dataframe["downtime"], errors="coerce").fillna(0).astype(float)
    dataframe["defects"] = pd.to_numeric(dataframe["defects"], errors="coerce").fillna(0).astype(int)
    dataframe["ideal_cycle_time"] = pd.to_numeric(
        dataframe["ideal_cycle_time"], errors="coerce"
    ).fillna(0).astype(float)

    if (dataframe[["output", "downtime", "defects", "ideal_cycle_time"]].isna()).any().any():
        raise HTTPException(status_code=400, detail="Invalid numeric values in CSV")

    dataframe["good_units"] = (dataframe["output"] - dataframe["defects"]).clip(lower=0)
    dataframe["planned_time"] = (
        dataframe["output"] * dataframe["ideal_cycle_time"] / 60.0
    ) + dataframe["downtime"]
    dataframe["downtime_events"] = dataframe["downtime"]
    dataframe["total_units"] = dataframe["output"]
    dataframe["operating_time"] = dataframe["planned_time"] - dataframe["downtime_events"]
    dataframe["defect_units"] = dataframe["total_units"] - dataframe["good_units"]
    dataframe["ideal_output"] = (
        dataframe["operating_time"] * 60 / dataframe["ideal_cycle_time"]
    ).astype(int)
    dataframe["speed_loss"] = (
        dataframe["ideal_output"] - dataframe["total_units"]
    ).clip(lower=0)

    return dataframe


def filter_production_data(
    dataframe: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
    machine_id: str | None = None,
    plant_id: str | None = None,
    line_id: str | None = None,
) -> pd.DataFrame:
    dataframe = dataframe.copy()
    dataframe["date"] = pd.to_datetime(dataframe["date"], errors="coerce")
    if dataframe["date"].isna().any():
        raise HTTPException(status_code=400, detail="Invalid date values in production data")

    if start_date:
        start = pd.to_datetime(start_date, errors="coerce")
        if pd.isna(start):
            raise HTTPException(status_code=400, detail="Invalid start_date")
        dataframe = dataframe[dataframe["date"] >= start]

    if end_date:
        end = pd.to_datetime(end_date, errors="coerce")
        if pd.isna(end):
            raise HTTPException(status_code=400, detail="Invalid end_date")
        dataframe = dataframe[dataframe["date"] <= end]

    if machine_id:
        machine_column = "machine_id" if "machine_id" in dataframe.columns else "machine"
        dataframe = dataframe[dataframe[machine_column].astype(str) == machine_id]

    if plant_id and "plant_id" in dataframe.columns:
        dataframe = dataframe[dataframe["plant_id"].astype(str) == plant_id]

    if line_id and "line_id" in dataframe.columns:
        dataframe = dataframe[dataframe["line_id"].astype(str) == line_id]

    return dataframe


def build_summary_report(dataframe: pd.DataFrame | None = None, scenario: str | None = "normal") -> dict[str, object]:
    dataframe = dataframe if dataframe is not None else get_data_source()
    scenario_key = normalize_scenario(scenario)
    last_updated = datetime.now(timezone.utc).isoformat()
    oee_rows = calculate_oee_rows(dataframe)
    trend_metrics = calculate_oee_trend(oee_rows)
    previous_oee = normalize_oee_value(trend_metrics["previous_oee"])
    current_oee = normalize_oee_value(trend_metrics["current_oee"])
    delta = round(current_oee - previous_oee, 2) if previous_oee is not None else None
    trend_direction = get_trend_direction(delta)
    average_oee = (
        sum(row["oee"] for row in oee_rows) / len(oee_rows)
        if oee_rows
        else 0
    )
    top_losses = sorted(
        aggregate_losses(dataframe),
        key=lambda item: float(item["impact"]),
        reverse=True,
    )
    financial_summary = calculate_financial_summary(dataframe)
    anomaly_alerts = get_anomaly_alerts(dataframe)
    machine_metrics = calculate_machine_metrics(dataframe, oee_rows)
    critical_alerts = build_critical_alerts(top_losses)
    predictive = calculate_predictive_maintenance(dataframe)
    event = build_event(dataframe, {
        "current_oee": current_oee,
        "average_oee": average_oee,
        "financial": financial_summary,
        "machine_metrics": machine_metrics,
    })
    machine_health = build_machine_health({"machine_metrics": machine_metrics}, predictive)
    insight = generate_operations_insight(
        {
            "oee": current_oee,
            "previous_oee": previous_oee,
            "delta": delta,
            "trend_direction": trend_direction,
            "top_losses": top_losses,
            "anomalies": anomaly_alerts,
            "revenue_loss": financial_summary["revenue_loss"],
        }
    )

    return {
        "scenario": scenario_key,
        "last_updated": last_updated,
        "average_oee": normalize_oee_value(round(average_oee, 2)) or 0.0,
        "current_oee": current_oee,
        "previous_oee": previous_oee,
        "delta": delta,
        "trend_direction": trend_direction,
        "top_losses": top_losses[:3],
        "financial": financial_summary,
        "anomalies": anomaly_alerts,
        "machine_metrics": machine_metrics,
        "critical_alerts": critical_alerts,
        "predictive_risk": predictive,
        "machine_health": machine_health,
        "live_event": event,
        "event_history": get_event_history(),
        "scope_options": build_scope_options(dataframe),
        "summary_report": insight,
    }


def build_decision_report(dataframe: pd.DataFrame | None = None) -> dict[str, object]:
    dataframe = dataframe if dataframe is not None else get_data_source()
    return build_decision_report_from_dataframe(dataframe)


def build_decision_report_from_dataframe(dataframe: pd.DataFrame) -> dict[str, object]:
    oee_rows = calculate_oee_rows(dataframe)
    trend_metrics = calculate_oee_trend(oee_rows)
    financial_summary = calculate_financial_summary(dataframe)

    decision = generate_decision_summary(
        {
            "current_oee": trend_metrics["current_oee"],
            "previous_oee": trend_metrics["previous_oee"],
            "machine_oee": calculate_machine_oee(oee_rows),
            "machine_losses": calculate_machine_losses(dataframe),
            "losses": aggregate_losses(dataframe),
            "anomalies": get_anomaly_alerts(dataframe),
            "financial_loss": financial_summary["revenue_loss"],
        }
    )
    top_loss = decision.get("top_loss_driver", [{}])[0] if decision.get("top_loss_driver") else {}
    machine = decision.get("highest_loss_machine", {}).get("machine") or decision.get("worst_machine", {}).get("machine") or "M1"
    financial_impact = float(financial_summary["revenue_loss"])
    expected_oee_gain = round(min(max(95 - float(trend_metrics["current_oee"] or 0), 1.5), 9.5), 1)
    confidence = round(min(0.97, 0.72 + min(financial_impact / 1_500_000, 0.22)), 2)
    estimated_savings = round(financial_impact * min(expected_oee_gain / 14, 0.55), 2)
    priority = str(decision.get("priority", "LOW"))
    issue = str(top_loss.get("loss_category", "Operational Loss")).title()
    action = get_executive_action(issue, priority)
    decision.update(
        {
            "priority": priority,
            "machine": machine,
            "issue": issue,
            "financial_impact": {
                "revenue_loss": round(financial_impact, 2),
                "formatted": f"${financial_impact:,.2f}",
            },
            "recommended_action": action,
            "action": decision.get("action") or action,
            "time_to_action": "within 4 hours" if priority == "HIGH" else "within 24 hours",
            "expected_oee_gain": expected_oee_gain,
            "confidence": confidence,
            "estimated_savings": estimated_savings,
            "formatted_estimated_savings": f"${estimated_savings:,.0f}",
        }
    )
    return decision


def build_streaming_message(dataframe: pd.DataFrame) -> dict[str, object]:
    summary = build_summary_report(dataframe)
    predictive = calculate_predictive_maintenance(dataframe)
    decision_report = build_decision_report_from_dataframe(dataframe)
    trend = decision_report["trend"]
    top_loss_drivers = decision_report["top_loss_driver"]
    anomaly_status = str(decision_report["anomaly"])
    current_oee = float(trend["current_oee"])
    anomaly_detected = anomaly_status != "No active anomaly alerts."

    message = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "oee": current_oee,
        "top_loss": get_top_loss_name(top_loss_drivers),
        "anomaly": anomaly_status,
        "financial_loss": decision_report["financial_impact"]["revenue_loss"],
        "decision": decision_report["decision"],
        "event": summary.get("live_event"),
        "event_history": summary.get("event_history", []),
        "alerts": summary.get("critical_alerts", []),
        "machine_health": build_machine_health(summary, predictive),
    }

    # Alert trigger keeps urgent conditions visible to any streaming client.
    if current_oee < 60 or anomaly_detected:
        message["alert"] = "HIGH PRIORITY ISSUE DETECTED"

    return message


def get_top_loss_name(top_loss_drivers: object) -> str:
    if not isinstance(top_loss_drivers, list) or not top_loss_drivers:
        return "no major loss driver"

    top_loss = top_loss_drivers[0]
    if isinstance(top_loss, dict):
        return str(top_loss.get("loss_category", "unknown loss"))

    return str(top_loss)


def get_trend_direction(delta: float | None) -> str:
    if delta is None:
        return "stable"
    if delta > 0:
        return "increase"
    if delta < 0:
        return "decrease"
    return "stable"


def normalize_oee_value(value: float | None) -> float | None:
    if value is None:
        return None
    return round(min(max(float(value), 75.0), 95.0), 2)


def calculate_oee_rows(dataframe: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for record in dataframe.to_dict(orient="records"):
        metrics = calculate_oee(
            planned_time=record["planned_time"],
            downtime=record["downtime_events"],
            ideal_cycle_time=record["ideal_cycle_time"],
            total_units=record["total_units"],
            good_units=record["good_units"],
        )
        rows.append(
            {
                "date": record["date"],
                "machine": record["machine"],
                **metrics,
            }
        )
    return rows


def calculate_oee_trend(oee_rows: list[dict[str, object]]) -> dict[str, float | None]:
    if not oee_rows:
        return {"current_oee": 0.0, "previous_oee": None, "delta": None}

    by_date: dict[str, list[float]] = {}
    for row in oee_rows:
        by_date.setdefault(str(row["date"]), []).append(float(row["oee"]))

    daily_oee = [
        (production_date, sum(values) / len(values))
        for production_date, values in sorted(by_date.items())
    ]
    current_oee = round(daily_oee[-1][1], 2)
    previous_oee = round(daily_oee[-2][1], 2) if len(daily_oee) >= 2 else None
    delta = round(current_oee - previous_oee, 2) if previous_oee is not None else None

    return {
        "current_oee": current_oee,
        "previous_oee": previous_oee,
        "delta": delta,
    }


def aggregate_losses(dataframe: pd.DataFrame) -> list[dict[str, object]]:
    breakdown: dict[str, dict[str, float | str]] = {}

    for record in dataframe.to_dict(orient="records"):
        row_losses = classify_losses(
            downtime=record["downtime_events"],
            operating_time=record["operating_time"],
            ideal_cycle_time=record["ideal_cycle_time"],
            total_units=record["total_units"],
            good_units=record["good_units"],
            impact_per_unit=REVENUE_PER_UNIT,
        )

        for item in row_losses:
            category = str(item["loss_category"])
            if category not in breakdown:
                breakdown[category] = {
                    "loss_category": category,
                    "duration": 0.0,
                    "impact": 0.0,
                }
            breakdown[category]["duration"] = round(
                float(breakdown[category]["duration"]) + float(item["duration"]),
                2,
            )
            breakdown[category]["impact"] = round(
                float(breakdown[category]["impact"]) + float(item["impact"]),
                2,
            )

    return list(breakdown.values())


def calculate_financial_summary(dataframe: pd.DataFrame) -> dict[str, object]:
    total_lost_units = 0
    total_revenue_loss = 0.0

    for record in dataframe.to_dict(orient="records"):
        result = calculate_revenue_loss(
            operating_time=record["operating_time"],
            ideal_cycle_time=record["ideal_cycle_time"],
            good_units=record["good_units"],
            revenue_per_unit=REVENUE_PER_UNIT,
        )
        total_lost_units += int(result["lost_units"])
        total_revenue_loss += float(result["revenue_loss"])

    revenue_loss = round(total_revenue_loss, 2)
    return {
        "lost_units": total_lost_units,
        "revenue_loss": revenue_loss,
        "formatted": f"${revenue_loss:,.0f}",
    }


def get_anomaly_alerts(dataframe: pd.DataFrame) -> list[dict[str, object]]:
    anomaly_dataframe = detect_anomalies(dataframe)
    alerts = anomaly_dataframe[anomaly_dataframe["anomaly_flag"]]
    return alerts[
        [
            "date",
            "machine",
            "anomaly_flag",
            "anomaly_type",
            "downtime_events",
            "speed_loss",
            "defect_units",
        ]
    ].to_dict(orient="records")


def calculate_machine_oee(oee_rows: list[dict[str, object]]) -> dict[str, float]:
    machine_values: dict[str, list[float]] = {}
    for row in oee_rows:
        machine_values.setdefault(str(row["machine"]), []).append(float(row["oee"]))

    return {
        machine: round(sum(values) / len(values), 2)
        for machine, values in machine_values.items()
    }


def calculate_machine_losses(dataframe: pd.DataFrame) -> dict[str, float]:
    machine_losses: dict[str, float] = {}
    for record in dataframe.to_dict(orient="records"):
        machine = str(record["machine"])
        impact = sum(
            float(loss_item["impact"])
            for loss_item in classify_losses(
                downtime=record["downtime_events"],
                operating_time=record["operating_time"],
                ideal_cycle_time=record["ideal_cycle_time"],
                total_units=record["total_units"],
                good_units=record["good_units"],
                impact_per_unit=REVENUE_PER_UNIT,
            )
        )
        machine_losses[machine] = round(machine_losses.get(machine, 0) + impact, 2)
    return machine_losses


def calculate_machine_metrics(
    dataframe: pd.DataFrame,
    oee_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    metrics = []
    for machine in sorted(dataframe["machine"].astype(str).unique()):
        machine_data = dataframe[dataframe["machine"].astype(str) == machine]
        machine_oee_rows = [row for row in oee_rows if str(row["machine"]) == machine]
        average_oee = (
            sum(float(row["oee"]) for row in machine_oee_rows) / len(machine_oee_rows)
            if machine_oee_rows
            else 0.0
        )
        machine_losses = sorted(
            aggregate_losses(machine_data),
            key=lambda item: float(item["impact"]),
            reverse=True,
        )
        financial = calculate_financial_summary(machine_data)
        metrics.append(
            {
                "machine": machine,
                "oee": normalize_oee_value(round(average_oee, 2)) or 0.0,
                "revenue_loss": financial["revenue_loss"],
                "formatted_revenue_loss": financial["formatted"],
                "top_loss": machine_losses[0]["loss_category"] if machine_losses else "none",
            }
        )
    return metrics


def build_critical_alerts(top_losses: list[dict[str, object]]) -> list[dict[str, object]]:
    alerts = []
    for loss in top_losses[:3]:
        issue = str(loss["loss_category"])
        impact = round(float(loss["impact"]), 2)
        severity = "HIGH" if issue == "breakdown loss" or impact >= 50000 else "MEDIUM"
        alerts.append(
            {
                "issue": issue,
                "severity": severity,
                "action": get_alert_action(issue, severity),
                "financial_impact": impact,
                "formatted_financial_impact": f"${impact:,.0f}",
            }
        )
    return alerts


def get_alert_action(issue: str, severity: str) -> str:
    issue_key = issue.lower()
    if "breakdown" in issue_key:
        return "Dispatch maintenance and protect the next production window."
    if "performance" in issue_key:
        return "Review cycle-time settings and check for micro-stoppages."
    if "quality" in issue_key:
        return "Inspect defect source and hold suspect output for review."
    return "Assign an operations lead to review the loss driver."


def get_executive_action(issue: str, priority: str) -> str:
    issue_key = issue.lower()
    if "breakdown" in issue_key:
        return "Schedule maintenance within 4 hours." if priority == "HIGH" else "Schedule maintenance in the next production window."
    if "performance" in issue_key:
        return "Tune cycle-time settings and validate bottleneck recovery."
    if "quality" in issue_key:
        return "Contain suspect output and run a focused defect-source review."
    return "Assign operations leader to resolve the highest financial loss driver."


def build_scope_options(dataframe: pd.DataFrame) -> dict[str, list[dict[str, str]]]:
    plants = []
    lines = []
    machines = []

    if "plant_id" in dataframe.columns:
        for plant_id in sorted(dataframe["plant_id"].astype(str).unique()):
            plant_rows = dataframe[dataframe["plant_id"].astype(str) == plant_id]
            plants.append(
                {
                    "id": plant_id,
                    "label": str(plant_rows["plant_name"].iloc[0]) if "plant_name" in plant_rows.columns and not plant_rows.empty else plant_id,
                }
            )
    if "line_id" in dataframe.columns:
        for line_id in sorted(dataframe["line_id"].astype(str).unique()):
            line_rows = dataframe[dataframe["line_id"].astype(str) == line_id]
            lines.append(
                {
                    "id": line_id,
                    "label": str(line_rows["line_name"].iloc[0]) if "line_name" in line_rows.columns and not line_rows.empty else line_id,
                    "plant_id": str(line_rows["plant_id"].iloc[0]) if "plant_id" in line_rows.columns and not line_rows.empty else "",
                }
            )

    machine_column = "machine_id" if "machine_id" in dataframe.columns else "machine"
    for machine_id in sorted(dataframe[machine_column].astype(str).unique()):
        machines.append({"id": machine_id, "label": machine_id})

    return {"plants": plants, "lines": lines, "machines": machines}


def get_scoped_data(
    start_date: str | None = None,
    end_date: str | None = None,
    machine_id: str | None = None,
    plant_id: str | None = None,
    line_id: str | None = None,
    scenario: str = "normal",
) -> pd.DataFrame:
    return filter_production_data(
        apply_scenario(get_data_source(), scenario),
        start_date=start_date,
        end_date=end_date,
        machine_id=machine_id,
        plant_id=plant_id,
        line_id=line_id,
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Operations Intelligence Engine API"}


@app.get("/data")
def data(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
    plant_id: str | None = Query(None, description="Filter by plant id"),
    line_id: str | None = Query(None, description="Filter by production line id"),
    scenario: str = Query("normal", description="Plant scenario simulation"),
) -> list[dict[str, object]]:
    data = get_scoped_data(start_date, end_date, machine_id, plant_id, line_id, scenario)
    return data.to_dict(orient="records")


@app.get("/oee")
def oee(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
    plant_id: str | None = Query(None, description="Filter by plant id"),
    line_id: str | None = Query(None, description="Filter by production line id"),
    scenario: str = Query("normal", description="Plant scenario simulation"),
) -> list[dict[str, object]]:
    data = get_scoped_data(start_date, end_date, machine_id, plant_id, line_id, scenario)
    return calculate_oee_rows(data)


@app.get("/loss")
def loss(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
    plant_id: str | None = Query(None, description="Filter by plant id"),
    line_id: str | None = Query(None, description="Filter by production line id"),
    scenario: str = Query("normal", description="Plant scenario simulation"),
) -> list[dict[str, object]]:
    data = get_scoped_data(start_date, end_date, machine_id, plant_id, line_id, scenario)
    return aggregate_losses(data)


@app.get("/financial")
def financial(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
    plant_id: str | None = Query(None, description="Filter by plant id"),
    line_id: str | None = Query(None, description="Filter by production line id"),
    scenario: str = Query("normal", description="Plant scenario simulation"),
) -> dict[str, object]:
    data = get_scoped_data(start_date, end_date, machine_id, plant_id, line_id, scenario)
    return calculate_financial_summary(data)


@app.get("/anomaly")
def anomaly(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
    plant_id: str | None = Query(None, description="Filter by plant id"),
    line_id: str | None = Query(None, description="Filter by production line id"),
    scenario: str = Query("normal", description="Plant scenario simulation"),
) -> list[dict[str, object]]:
    data = get_scoped_data(start_date, end_date, machine_id, plant_id, line_id, scenario)
    return get_anomaly_alerts(data)


@app.get("/ai-summary")
def ai_summary(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
    plant_id: str | None = Query(None, description="Filter by plant id"),
    line_id: str | None = Query(None, description="Filter by production line id"),
    scenario: str = Query("normal", description="Plant scenario simulation"),
) -> dict[str, object]:
    data = get_scoped_data(start_date, end_date, machine_id, plant_id, line_id, scenario)
    return build_summary_report(data, scenario)


@app.get("/ai-decision")
def ai_decision(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
    plant_id: str | None = Query(None, description="Filter by plant id"),
    line_id: str | None = Query(None, description="Filter by production line id"),
    scenario: str = Query("normal", description="Plant scenario simulation"),
) -> dict[str, object]:
    data = get_scoped_data(start_date, end_date, machine_id, plant_id, line_id, scenario)
    return build_decision_report(data)


@app.post("/upload-data")
def upload_data(file: UploadFile = File(...)) -> dict[str, str]:
    global UPLOADED_DATA
    dataframe = parse_uploaded_data(file)
    if dataframe.empty:
        raise HTTPException(status_code=400, detail="Uploaded CSV contains no data")

    UPLOADED_DATA = dataframe
    return {"status": "success", "message": "Data uploaded and ready for analysis."}


@app.get("/machine-summary")
def machine_summary(
    machine_id: str = Query(..., description="Machine identifier"),
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    plant_id: str | None = Query(None, description="Filter by plant id"),
    line_id: str | None = Query(None, description="Filter by production line id"),
    scenario: str = Query("normal", description="Plant scenario simulation"),
) -> dict[str, object]:
    data = get_scoped_data(start_date, end_date, machine_id, plant_id, line_id, scenario)
    if data.empty:
        raise HTTPException(status_code=404, detail="Machine data not found for the requested range")

    oee_rows = calculate_oee_rows(data)
    top_losses = sorted(aggregate_losses(data), key=lambda item: float(item["impact"]), reverse=True)
    anomalies = get_anomaly_alerts(data)
    average_oee = round(sum(row["oee"] for row in oee_rows) / len(oee_rows), 2) if oee_rows else 0.0

    return {
        "machine_id": machine_id,
        "average_oee": average_oee,
        "top_losses": top_losses[:3],
        "anomaly_summary": anomalies,
    }


@app.get("/export-report")
def export_report(
    format: str = Query("json", pattern="^(json|csv|pdf)$"),
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
    plant_id: str | None = Query(None, description="Filter by plant id"),
    line_id: str | None = Query(None, description="Filter by production line id"),
    scenario: str = Query("normal", description="Plant scenario simulation"),
) -> Response:
    data = get_scoped_data(start_date, end_date, machine_id, plant_id, line_id, scenario)
    summary = build_summary_report(data, scenario)
    decision = build_decision_report(data)
    predictive = calculate_predictive_maintenance(data)
    simulation = simulate_action(data, machine_id, "reduce downtime", 20, REVENUE_PER_UNIT) if not data.empty else None
    payload = {
        "average_oee": summary["average_oee"],
        "trend_direction": summary["trend_direction"],
        "revenue_loss": summary["financial"]["revenue_loss"],
        "top_losses": summary["top_losses"],
        "priority": decision.get("priority"),
        "action": decision.get("recommended_action") or decision.get("action"),
        "estimated_impact": decision.get("estimated_impact"),
        "machine_risk": predictive,
        "ai_recommendation": decision,
        "simulation": simulation,
    }

    if format == "csv":
        return Response(
            content=build_report_csv(summary, decision, predictive, simulation),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=operations-executive-report.csv"},
        )

    if format == "pdf":
        return Response(
            content=build_report_pdf(summary, decision, predictive, simulation),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=operations-executive-report.pdf"},
        )

    return payload


@app.get("/predictive-maintenance")
def predictive_maintenance(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
    plant_id: str | None = Query(None, description="Filter by plant id"),
    line_id: str | None = Query(None, description="Filter by production line id"),
    scenario: str = Query("normal", description="Plant scenario simulation"),
) -> list[dict[str, object]]:
    data = get_scoped_data(start_date, end_date, machine_id, plant_id, line_id, scenario)
    return calculate_predictive_maintenance(data)


@app.post("/simulate")
def simulate(payload: SimulationRequest) -> dict[str, object]:
    machine = payload.machine_id or payload.machine
    data = get_scoped_data(
        machine_id=machine,
        plant_id=payload.plant_id,
        line_id=payload.line_id,
        scenario="normal",
    )
    if data.empty:
        raise HTTPException(status_code=404, detail="No production data found for simulation scope")

    try:
        return simulate_action(data, machine, payload.action, payload.improvement_percent, REVENUE_PER_UNIT)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/events/recent")
def recent_events() -> list[dict[str, object]]:
    return get_event_history()


@app.websocket("/ws")
async def websocket_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client.host if websocket.client else "unknown"
    logger.info("WebSocket connected: %s", client)

    try:
        while True:
            try:
                dataframe = get_data_source()
                await websocket.send_json(build_streaming_message(dataframe))
            except Exception as exc:
                logger.exception("WebSocket streaming update failed for %s", client)
                await websocket.send_json(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "error": "streaming_update_failed",
                        "detail": str(exc),
                    }
                )

            await asyncio.sleep(5)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", client)
        return
