from __future__ import annotations


def generate_operations_insight(data: dict) -> str:
    oee = data.get("oee", 0)
    previous_oee = data.get("previous_oee")
    delta = data.get("delta")
    trend_direction = data.get("trend_direction", "stable")
    top_losses = data.get("top_losses", [])
    anomalies = data.get("anomalies", [])

    top_loss = _get_top_loss(top_losses)
    estimated_loss = _get_estimated_loss(top_losses, data)
    anomaly_text = _format_anomaly_text(anomalies)
    recommendation = _recommend_action(top_loss, anomalies)
    trend_text = _format_trend_text(previous_oee, delta, trend_direction)

    return (
        f"OEE is {oee:.2f}% and {trend_text}. "
        f"Estimated revenue loss is ${estimated_loss:,.2f}, with {anomaly_text}. "
        f"The main driver is {top_loss}; recommend {recommendation}."
    )


def _get_top_loss(top_losses: list[dict] | list[str]) -> str:
    if not top_losses:
        return "no major loss category"

    first_loss = top_losses[0]
    if isinstance(first_loss, dict):
        return str(
            first_loss.get("loss_category")
            or first_loss.get("category")
            or "unknown loss"
        )

    return str(first_loss)


def _get_estimated_loss(top_losses: list[dict] | list[str], data: dict) -> float:
    if "revenue_loss" in data:
        return float(data["revenue_loss"])

    if not top_losses or not isinstance(top_losses[0], dict):
        return 0.0

    return float(top_losses[0].get("impact", 0))


def _format_anomaly_text(anomalies: list[dict] | list[str]) -> str:
    if not anomalies:
        return "no active anomaly alerts"

    first_anomaly = anomalies[0]
    if isinstance(first_anomaly, dict):
        anomaly_type = first_anomaly.get("anomaly_type") or first_anomaly.get("type")
        return f"anomaly detected: {anomaly_type}"

    return f"anomaly detected: {first_anomaly}"


def _format_trend_text(previous_oee: float | None, delta: float | None, trend_direction: str) -> str:
    if previous_oee is None or delta is None:
        return "trend direction is not yet available"

    return (
        f"the trend is {trend_direction} versus previous OEE of "
        f"{previous_oee:.2f}% with a {delta:+.2f} point delta"
    )


def _recommend_action(top_loss: str, anomalies: list[dict] | list[str]) -> str:
    text = f"{top_loss} {anomalies}".lower()

    if "breakdown" in text or "downtime" in text:
        return "immediate maintenance review on the affected machine"
    if "quality" in text or "defect" in text:
        return "quality inspection and process parameter checks"
    if "performance" in text or "speed" in text:
        return "cycle-time review and operator speed-loss investigation"

    return "supervisor review of the largest production loss"


if __name__ == "__main__":
    print(
        generate_operations_insight(
            {
                "oee": 72.4,
                "top_losses": [
                    {"loss_category": "breakdown loss", "impact": 18000}
                ],
                "anomalies": [
                    {"anomaly_type": "downtime spike"}
                ],
            }
        )
    )
