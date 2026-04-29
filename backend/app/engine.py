import asyncio
from datetime import datetime, timezone

from app.anomaly import AnomalyDetector
from app.config import Settings
from app.financial import calculate_financial_impact
from app.insights import OpenAIInsightProvider
from app.losses import classify_losses
from app.models import OperationsSnapshot
from app.oee import calculate_oee
from app.simulator import SyntheticMachineSimulator


class OperationsEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.simulator = SyntheticMachineSimulator(
            planned_production_minutes=settings.planned_production_minutes,
            ideal_cycle_time_seconds=settings.ideal_cycle_time_seconds,
        )
        self.detector = AnomalyDetector()
        self.insights = OpenAIInsightProvider(settings.openai_api_key, settings.openai_model)
        self._snapshot: OperationsSnapshot | None = None
        self._lock = asyncio.Lock()

    async def tick(self, force_insight: bool = False) -> OperationsSnapshot:
        async with self._lock:
            machine, telemetry = self.simulator.next()
            oee = calculate_oee(telemetry)
            losses = classify_losses(telemetry, self.settings.unit_value_dollars)
            financial = calculate_financial_impact(
                telemetry,
                self.settings.unit_value_dollars,
                self.settings.operating_cost_per_hour_dollars,
            )
            anomalies = self.detector.detect(telemetry, oee)

            should_refresh_insight = (
                force_insight
                or self._snapshot is None
                or bool(anomalies)
                or self.simulator.state.tick % 10 == 0
            )
            insight = self._snapshot.insight if self._snapshot else None
            if should_refresh_insight or insight is None:
                insight = await self.insights.generate(telemetry, oee, losses, financial, anomalies)

            self._snapshot = OperationsSnapshot(
                timestamp=datetime.now(timezone.utc).isoformat(),
                machine=machine,
                telemetry=telemetry,
                oee=oee,
                losses=losses,
                financialImpact=financial,
                anomalies=anomalies,
                insight=insight,
            )
            return self._snapshot

    async def snapshot(self) -> OperationsSnapshot:
        if self._snapshot is None:
            return await self.tick()
        return self._snapshot
