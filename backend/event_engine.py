from __future__ import annotations

from datetime import datetime, timezone
from itertools import count

import pandas as pd


EVENT_HISTORY: list[dict[str, object]] = []
_EVENT_COUNTER = count()


EVENT_TEMPLATES = [
    ("Throughput drift", "MEDIUM", "Line speed below expected band"),
    ("Downtime spike", "HIGH", "Maintenance response window opened"),
    ("Quality excursion", "MEDIUM", "Defect signal above rolling baseline"),
    ("Recovered cell", "LOW", "Machine returned to stable operating band"),
    ("Constraint shift", "MEDIUM", "Bottleneck moved to downstream operation"),
]


def build_event(dataframe: pd.DataFrame, summary: dict[str, object]) -> dict[str, object]:
    index = next(_EVENT_COUNTER)
    template = EVENT_TEMPLATES[index % len(EVENT_TEMPLATES)]
    machine_metrics = summary.get("machine_metrics") or []
    machine = "M1"
    if machine_metrics:
        machine = str(sorted(machine_metrics, key=lambda item: float(item.get("revenue_loss", 0)), reverse=True)[0].get("machine", "M1"))

    event = {
        "id": f"evt-{index + 1:05d}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "machine": machine,
        "title": template[0],
        "severity": template[1],
        "description": template[2],
        "oee": summary.get("current_oee", summary.get("average_oee", 0)),
        "financial_impact": summary.get("financial", {}).get("revenue_loss", 0),
    }
    EVENT_HISTORY.insert(0, event)
    del EVENT_HISTORY[25:]
    return event


def build_machine_health(summary: dict[str, object], predictive: list[dict[str, object]]) -> list[dict[str, object]]:
    risks = {str(item.get("machine")): item for item in predictive}
    health = []
    for metric in summary.get("machine_metrics", []) or []:
        machine = str(metric.get("machine", "unknown"))
        risk = risks.get(machine, {})
        oee = float(metric.get("oee", 0))
        severity = str(risk.get("severity", "LOW"))
        status = "Critical" if severity == "HIGH" else "Watch" if severity == "MEDIUM" or oee < 82 else "Healthy"
        health.append(
            {
                "machine": machine,
                "oee": round(oee, 1),
                "status": status,
                "severity": severity,
                "risk": risk.get("failure_risk", 0),
                "top_loss": metric.get("top_loss", "none"),
            }
        )
    return health


def get_event_history() -> list[dict[str, object]]:
    return EVENT_HISTORY[:]
