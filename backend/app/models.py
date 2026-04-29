from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MachineState(str, Enum):
    running = "running"
    stopped = "stopped"
    changeover = "changeover"
    starved = "starved"


class EventType(str, Enum):
    breakdown = "breakdown"
    setup_adjustment = "setup_adjustment"
    small_stop = "small_stop"
    reduced_speed = "reduced_speed"
    startup_reject = "startup_reject"
    production_reject = "production_reject"
    normal = "normal"


class Machine(BaseModel):
    id: str
    name: str
    state: MachineState
    current_product: str
    operator: str


class Telemetry(BaseModel):
    runtime_minutes: float
    planned_production_minutes: float
    downtime_minutes: float
    total_count: int
    good_count: int
    reject_count: int
    ideal_cycle_time_seconds: float
    actual_cycle_time_seconds: float
    current_rate_per_minute: float
    target_rate_per_minute: float
    last_event_type: EventType
    last_event_message: str


class OeeMetrics(BaseModel):
    availability: float = Field(ge=0, le=1)
    performance: float = Field(ge=0, le=1)
    quality: float = Field(ge=0, le=1)
    oee: float = Field(ge=0, le=1)


class LossItem(BaseModel):
    category: str
    minutes: float
    units: int
    dollars: float
    description: str


class FinancialImpact(BaseModel):
    lost_units: int
    revenue_loss_dollars: float
    operating_loss_dollars: float
    total_loss_dollars: float


class Anomaly(BaseModel):
    type: str
    severity: Literal["low", "medium", "high"]
    message: str
    value: float
    baseline: float


class Insight(BaseModel):
    provider: str
    summary: str
    likely_causes: list[str]
    recommended_actions: list[str]


class OperationsSnapshot(BaseModel):
    timestamp: str
    machine: Machine
    telemetry: Telemetry
    oee: OeeMetrics
    losses: list[LossItem]
    financialImpact: FinancialImpact
    anomalies: list[Anomaly]
    insight: Insight
