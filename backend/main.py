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

from ai_agent import generate_operations_insight
from ai_decision import generate_decision_summary
from anomaly import detect_anomalies
from data_generator import generate_production_data
from financial import calculate_revenue_loss
from loss_classifier import classify_losses
from oee_engine import calculate_oee


REVENUE_PER_UNIT = 18.5
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


def get_data_source() -> pd.DataFrame:
    if UPLOADED_DATA is not None:
        return apply_live_variation(UPLOADED_DATA.copy())
    return apply_live_variation(get_production_data())


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
) -> pd.DataFrame:
    if start_date:
        start = pd.to_datetime(start_date, errors="coerce")
        if start is pd.NaT:
            raise HTTPException(status_code=400, detail="Invalid start_date")
        dataframe = dataframe[dataframe["date"] >= start]

    if end_date:
        end = pd.to_datetime(end_date, errors="coerce")
        if end is pd.NaT:
            raise HTTPException(status_code=400, detail="Invalid end_date")
        dataframe = dataframe[dataframe["date"] <= end]

    if machine_id:
        dataframe = dataframe[dataframe["machine"] == machine_id]

    return dataframe


def build_summary_report(dataframe: pd.DataFrame | None = None) -> dict[str, object]:
    dataframe = dataframe if dataframe is not None else get_data_source()
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
        "last_updated": last_updated,
        "average_oee": normalize_oee_value(round(average_oee, 2)) or 0.0,
        "current_oee": current_oee,
        "previous_oee": previous_oee,
        "delta": delta,
        "trend_direction": trend_direction,
        "top_losses": top_losses[:3],
        "financial": financial_summary,
        "anomalies": anomaly_alerts,
        "summary_report": insight,
    }


def build_decision_report(dataframe: pd.DataFrame | None = None) -> dict[str, object]:
    dataframe = dataframe if dataframe is not None else get_data_source()
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


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Operations Intelligence Engine API"}


@app.get("/data")
def data(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
) -> list[dict[str, object]]:
    data = filter_production_data(get_data_source(), start_date, end_date, machine_id)
    return data.to_dict(orient="records")


@app.get("/oee")
def oee(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
) -> list[dict[str, object]]:
    data = filter_production_data(get_data_source(), start_date, end_date, machine_id)
    return calculate_oee_rows(data)


@app.get("/loss")
def loss(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
) -> list[dict[str, object]]:
    data = filter_production_data(get_data_source(), start_date, end_date, machine_id)
    return aggregate_losses(data)


@app.get("/financial")
def financial(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
) -> dict[str, float]:
    data = filter_production_data(get_data_source(), start_date, end_date, machine_id)
    return calculate_financial_summary(data)


@app.get("/anomaly")
def anomaly(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
) -> list[dict[str, object]]:
    data = filter_production_data(get_data_source(), start_date, end_date, machine_id)
    return get_anomaly_alerts(data)


@app.get("/ai-summary")
def ai_summary(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
) -> dict[str, object]:
    data = filter_production_data(get_data_source(), start_date, end_date, machine_id)
    return build_summary_report(data)


@app.get("/ai-decision")
def ai_decision(
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
) -> dict[str, object]:
    data = filter_production_data(get_data_source(), start_date, end_date, machine_id)
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
) -> dict[str, object]:
    data = filter_production_data(get_data_source(), start_date, end_date, machine_id)
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
    format: str = Query("json", regex="^(json|csv)$"),
    start_date: str | None = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date filter YYYY-MM-DD"),
    machine_id: str | None = Query(None, description="Filter by machine id"),
) -> Response:
    data = filter_production_data(get_data_source(), start_date, end_date, machine_id)
    summary = build_summary_report(data)
    decision = build_decision_report(data)
    payload = {
        "average_oee": summary["average_oee"],
        "trend_direction": summary["trend_direction"],
        "revenue_loss": summary["financial"]["revenue_loss"],
        "top_losses": summary["top_losses"],
        "priority": decision.get("priority"),
        "action": decision.get("action"),
        "estimated_impact": decision.get("estimated_impact"),
    }

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["metric", "value"])
        writer.writerow(["average_oee", payload["average_oee"]])
        writer.writerow(["trend_direction", payload["trend_direction"]])
        writer.writerow(["revenue_loss", payload["revenue_loss"]])
        writer.writerow(["priority", payload["priority"]])
        writer.writerow(["action", payload["action"]])
        writer.writerow(["estimated_impact", payload["estimated_impact"]])
        for loss in payload["top_losses"]:
            writer.writerow([f"top_loss_{loss['loss_category']}", loss["impact"]])

        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=operations-report.csv"},
        )

    return payload


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
