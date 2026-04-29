from openai import OpenAI

from app.models import Anomaly, FinancialImpact, Insight, LossItem, OeeMetrics, Telemetry


class InsightProvider:
    async def generate(
        self,
        telemetry: Telemetry,
        oee: OeeMetrics,
        losses: list[LossItem],
        financial: FinancialImpact,
        anomalies: list[Anomaly],
    ) -> Insight:
        raise NotImplementedError


class OpenAIInsightProvider(InsightProvider):
    def __init__(self, api_key: str | None, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def generate(
        self,
        telemetry: Telemetry,
        oee: OeeMetrics,
        losses: list[LossItem],
        financial: FinancialImpact,
        anomalies: list[Anomaly],
    ) -> Insight:
        if not self.api_key:
            return fallback_insight(telemetry, oee, losses, financial, anomalies)

        prompt = build_prompt(telemetry, oee, losses, financial, anomalies)
        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an operations excellence analyst. Be concise and actionable."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        return Insight(
            provider="openai",
            summary=text.strip()[:700],
            likely_causes=[loss.category for loss in sorted(losses, key=lambda item: item.dollars, reverse=True)[:3]],
            recommended_actions=[
                "Verify the top loss category at the machine within the next production interval.",
                "Compare current defect and speed signals against the last known stable run.",
            ],
        )


def build_prompt(
    telemetry: Telemetry,
    oee: OeeMetrics,
    losses: list[LossItem],
    financial: FinancialImpact,
    anomalies: list[Anomaly],
) -> str:
    top_losses = ", ".join(f"{loss.category}: ${loss.dollars}" for loss in sorted(losses, key=lambda item: item.dollars, reverse=True)[:3])
    anomaly_text = ", ".join(anomaly.type for anomaly in anomalies) or "none"
    return (
        f"OEE={oee.oee:.1%}, availability={oee.availability:.1%}, performance={oee.performance:.1%}, "
        f"quality={oee.quality:.1%}. Last event: {telemetry.last_event_message}. "
        f"Top losses: {top_losses}. Total financial loss=${financial.total_loss_dollars}. "
        f"Anomalies: {anomaly_text}. Provide root cause insight and next actions."
    )


def fallback_insight(
    telemetry: Telemetry,
    oee: OeeMetrics,
    losses: list[LossItem],
    financial: FinancialImpact,
    anomalies: list[Anomaly],
) -> Insight:
    top_loss = max(losses, key=lambda item: item.dollars)
    anomaly_note = "No active anomaly is above threshold."
    if anomalies:
        anomaly_note = f"{anomalies[0].message}"

    return Insight(
        provider="fallback",
        summary=(
            f"OEE is {oee.oee:.1%}. The largest current loss is {top_loss.category.lower()} "
            f"at ${top_loss.dollars:,.2f}. Total estimated impact is ${financial.total_loss_dollars:,.2f}. "
            f"{anomaly_note}"
        ),
        likely_causes=[
            top_loss.category,
            "Recent event pattern: " + telemetry.last_event_type.value,
            "Cycle time variance" if telemetry.actual_cycle_time_seconds > telemetry.ideal_cycle_time_seconds else "Quality leakage",
        ],
        recommended_actions=[
            f"Start with {top_loss.category.lower()} and validate the last event: {telemetry.last_event_message}",
            "Check operator log, material feed, and machine fault history for the last 15 minutes.",
            "Escalate if the same anomaly remains active for three consecutive intervals.",
        ],
    )
