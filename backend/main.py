from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ai_agent import generate_operations_insight
from ai_decision import generate_decision_summary
from anomaly import detect_anomalies
from data_generator import generate_production_data
from financial import calculate_revenue_loss
from loss_classifier import classify_losses
from oee_engine import calculate_oee


REVENUE_PER_UNIT = 18.5
logger = logging.getLogger("operations_intelligence.websocket")

app = FastAPI(title="Operations Intelligence Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_production_data() -> pd.DataFrame:
    dataframe = generate_production_data(days=30, seed=None)
    dataframe["operating_time"] = dataframe["planned_time"] - dataframe["downtime_events"]
    dataframe["defect_units"] = dataframe["total_units"] - dataframe["good_units"]
    dataframe["ideal_output"] = (
        dataframe["operating_time"] * 60 / dataframe["ideal_cycle_time"]
    ).astype(int)
    dataframe["speed_loss"] = (
        dataframe["ideal_output"] - dataframe["total_units"]
    ).clip(lower=0)
    return dataframe


def build_summary_report() -> dict[str, object]:
    dataframe = get_production_data()
    oee_rows = calculate_oee_rows(dataframe)
    trend_metrics = calculate_oee_trend(oee_rows)
    previous_oee = trend_metrics["previous_oee"]
    current_oee = trend_metrics["current_oee"]
    delta = trend_metrics["delta"]
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
        "average_oee": round(average_oee, 2),
        "current_oee": current_oee,
        "previous_oee": previous_oee,
        "delta": delta,
        "trend_direction": trend_direction,
        "top_losses": top_losses[:3],
        "financial": financial_summary,
        "anomalies": anomaly_alerts,
        "summary_report": insight,
    }


def build_decision_report() -> dict[str, object]:
    dataframe = get_production_data()
    return build_decision_report_from_dataframe(dataframe)


def build_decision_report_from_dataframe(dataframe: pd.DataFrame) -> dict[str, object]:
    oee_rows = calculate_oee_rows(dataframe)
    trend_metrics = calculate_oee_trend(oee_rows)
    financial_summary = calculate_financial_summary(dataframe)

    return generate_decision_summary(
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


def build_streaming_message(dataframe: pd.DataFrame) -> dict[str, object]:
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


def calculate_financial_summary(dataframe: pd.DataFrame) -> dict[str, float]:
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

    return {
        "lost_units": total_lost_units,
        "revenue_loss": round(total_revenue_loss, 2),
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


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Operations Intelligence Engine API"}


@app.get("/data")
def data() -> list[dict[str, object]]:
    return get_production_data().to_dict(orient="records")


@app.get("/oee")
def oee() -> list[dict[str, object]]:
    return calculate_oee_rows(get_production_data())


@app.get("/loss")
def loss() -> list[dict[str, object]]:
    return aggregate_losses(get_production_data())


@app.get("/financial")
def financial() -> dict[str, float]:
    return calculate_financial_summary(get_production_data())


@app.get("/anomaly")
def anomaly() -> list[dict[str, object]]:
    return get_anomaly_alerts(get_production_data())


@app.get("/ai-summary")
def ai_summary() -> dict[str, object]:
    return build_summary_report()


@app.get("/ai-decision")
def ai_decision() -> dict[str, object]:
    return build_decision_report()


@app.websocket("/ws")
async def websocket_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client.host if websocket.client else "unknown"
    logger.info("WebSocket connected: %s", client)

    try:
        while True:
            try:
                dataframe = get_production_data()
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
