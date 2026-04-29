from __future__ import annotations


def generate_decision_summary(data: dict) -> dict[str, object]:
    current_oee = float(data.get("current_oee", 0))
    previous_oee = float(data.get("previous_oee", current_oee))
    losses = sorted(
        data.get("losses", []),
        key=lambda loss: float(loss.get("impact", 0)),
        reverse=True,
    )
    machine_oee = data.get("machine_oee", {})
    machine_losses = data.get("machine_losses", {})
    anomalies = data.get("anomalies", [])
    financial_loss = float(data.get("financial_loss", 0))

    trend = analyze_trend(current_oee, previous_oee)
    loss_contribution = prioritize_losses(losses)
    top_loss_drivers = loss_contribution[:2]
    worst_machine = get_machine_by_oee(machine_oee, reverse=False)
    best_machine = get_machine_by_oee(machine_oee, reverse=True)
    highest_loss_machine = get_highest_loss_machine(machine_losses)
    anomaly_text = summarize_anomalies(anomalies)
    decision = recommend_decision(top_loss_drivers)

    top_driver_name = (
        top_loss_drivers[0]["loss_category"]
        if top_loss_drivers
        else "no major loss driver"
    )

    return {
        "trend": trend,
        "top_loss_driver": top_loss_drivers,
        "loss_contribution": loss_contribution,
        "worst_machine": worst_machine,
        "best_machine": best_machine,
        "highest_loss_machine": highest_loss_machine,
        "anomaly": anomaly_text,
        "financial_impact": {
            "revenue_loss": round(financial_loss, 2),
            "formatted": f"${financial_loss:,.2f}",
        },
        "decision": decision,
        "summary_text": (
            f"OEE is {current_oee:.2f}%, a {trend['direction']} of "
            f"{trend['delta']:+.2f} points versus the previous {previous_oee:.2f}%. "
            f"The top loss driver is {top_driver_name}, with total financial impact of "
            f"${financial_loss:,.2f}. {decision}"
        ),
    }


def analyze_trend(current_oee: float, previous_oee: float) -> dict[str, float | str]:
    delta = round(current_oee - previous_oee, 2)
    if delta > 0:
        direction = "increase"
    elif delta < 0:
        direction = "decrease"
    else:
        direction = "stable"

    return {
        "current_oee": round(current_oee, 2),
        "previous_oee": round(previous_oee, 2),
        "delta": delta,
        "direction": direction,
    }


def prioritize_losses(losses: list[dict]) -> list[dict[str, float | str]]:
    total_impact = sum(float(loss.get("impact", 0)) for loss in losses)
    prioritized = []

    # Contribution shows which losses explain the largest share of financial impact.
    for loss in losses:
        impact = float(loss.get("impact", 0))
        contribution = (impact / total_impact) * 100 if total_impact > 0 else 0
        prioritized.append(
            {
                "loss_category": str(loss.get("loss_category", "unknown loss")),
                "impact": round(impact, 2),
                "contribution_percent": round(contribution, 2),
            }
        )

    return prioritized


def get_machine_by_oee(machine_oee: dict[str, float], reverse: bool) -> dict[str, float | str]:
    if not machine_oee:
        return {"machine": "unknown", "oee": 0.0}

    machine, oee = sorted(
        machine_oee.items(),
        key=lambda item: float(item[1]),
        reverse=reverse,
    )[0]
    return {"machine": machine, "oee": round(float(oee), 2)}


def get_highest_loss_machine(machine_losses: dict[str, float]) -> dict[str, float | str]:
    if not machine_losses:
        return {"machine": "unknown", "impact": 0.0}

    machine, impact = sorted(
        machine_losses.items(),
        key=lambda item: float(item[1]),
        reverse=True,
    )[0]
    return {"machine": machine, "impact": round(float(impact), 2)}


def summarize_anomalies(anomalies: list[dict] | list[str]) -> str:
    if not anomalies:
        return "No active anomaly alerts."

    first_anomaly = anomalies[0]
    if isinstance(first_anomaly, dict):
        anomaly_type = first_anomaly.get("anomaly_type") or first_anomaly.get("type")
        machine = first_anomaly.get("machine", "unknown machine")
        return f"{anomaly_type} detected on {machine}."

    return f"{first_anomaly} detected."


def recommend_decision(top_loss_drivers: list[dict]) -> str:
    if not top_loss_drivers:
        return "Continue monitoring because no dominant loss driver is present."

    highest_loss = str(top_loss_drivers[0]["loss_category"]).lower()

    # Recommendation logic maps the highest financial loss category to an action.
    if "breakdown" in highest_loss:
        return "Recommend maintenance intervention on the highest-loss machine."
    if "speed" in highest_loss or "performance" in highest_loss:
        return "Recommend process optimization to recover speed and cycle-time losses."
    if "quality" in highest_loss or "defect" in highest_loss:
        return "Recommend quality control review to reduce rejects and rework."

    return "Recommend supervisor review of the top loss driver."
