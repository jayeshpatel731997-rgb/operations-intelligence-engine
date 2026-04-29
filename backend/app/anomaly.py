from collections import deque

from app.models import Anomaly, OeeMetrics, Telemetry


class AnomalyDetector:
    def __init__(self, window_size: int = 20) -> None:
        self.window_size = window_size
        self.oee_history: deque[float] = deque(maxlen=window_size)
        self.reject_history: deque[float] = deque(maxlen=window_size)
        self.downtime_history: deque[float] = deque(maxlen=window_size)
        self.speed_history: deque[float] = deque(maxlen=window_size)

    def detect(self, telemetry: Telemetry, oee: OeeMetrics) -> list[Anomaly]:
        anomalies: list[Anomaly] = []
        reject_rate = telemetry.reject_count / max(telemetry.total_count, 1)
        speed_ratio = telemetry.actual_cycle_time_seconds / max(telemetry.ideal_cycle_time_seconds, 1e-9)

        oee_baseline = self._mean(self.oee_history, default=oee.oee)
        reject_baseline = self._mean(self.reject_history, default=reject_rate)
        downtime_baseline = self._mean(self.downtime_history, default=telemetry.downtime_minutes)
        speed_baseline = self._mean(self.speed_history, default=speed_ratio)

        if len(self.oee_history) >= 5 and oee.oee < oee_baseline - 0.12:
            anomalies.append(
                Anomaly(type="oee_drop", severity="high", message="OEE dropped sharply below the rolling baseline.", value=oee.oee, baseline=round(oee_baseline, 4))
            )
        if len(self.reject_history) >= 5 and reject_rate > reject_baseline + 0.025:
            anomalies.append(
                Anomaly(type="defect_spike", severity="medium", message="Reject rate is elevated versus recent production.", value=round(reject_rate, 4), baseline=round(reject_baseline, 4))
            )
        if len(self.downtime_history) >= 5 and telemetry.downtime_minutes > downtime_baseline + 8:
            anomalies.append(
                Anomaly(type="downtime_spike", severity="high", message="Downtime accumulation is rising faster than normal.", value=round(telemetry.downtime_minutes, 2), baseline=round(downtime_baseline, 2))
            )
        if len(self.speed_history) >= 5 and speed_ratio > max(speed_baseline + 0.12, 1.18):
            anomalies.append(
                Anomaly(type="speed_degradation", severity="medium", message="Actual cycle time is materially slower than ideal.", value=round(speed_ratio, 4), baseline=round(speed_baseline, 4))
            )

        self.oee_history.append(oee.oee)
        self.reject_history.append(reject_rate)
        self.downtime_history.append(telemetry.downtime_minutes)
        self.speed_history.append(speed_ratio)
        return anomalies

    @staticmethod
    def _mean(values: deque[float], default: float) -> float:
        if not values:
            return default
        return sum(values) / len(values)
