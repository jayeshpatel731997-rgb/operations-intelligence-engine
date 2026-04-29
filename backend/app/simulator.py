from __future__ import annotations

import random
from dataclasses import dataclass

from app.models import EventType, Machine, MachineState, Telemetry


@dataclass
class SimulatorState:
    elapsed_minutes: float = 120.0
    downtime_minutes: float = 10.0
    total_count: int = 2700
    good_count: int = 2625
    reject_count: int = 75
    tick: int = 0


class SyntheticMachineSimulator:
    def __init__(
        self,
        planned_production_minutes: int,
        ideal_cycle_time_seconds: float,
    ) -> None:
        self.planned_production_minutes = planned_production_minutes
        self.ideal_cycle_time_seconds = ideal_cycle_time_seconds
        self.state = SimulatorState()
        self.random = random.Random(42)

    def next(self) -> tuple[Machine, Telemetry]:
        self.state.tick += 1
        self.state.elapsed_minutes = min(self.state.elapsed_minutes + 1, self.planned_production_minutes)
        event_type = self._event_type()
        machine_state = self._machine_state(event_type)
        actual_cycle = self._actual_cycle_time(event_type)

        produced = 0
        defects = 0
        if machine_state == MachineState.running:
            produced = max(int(60 / actual_cycle + self.random.randint(-3, 3)), 0)
            defect_rate = 0.02
            if event_type in {EventType.startup_reject, EventType.production_reject}:
                defect_rate = 0.1
            defects = min(int(produced * defect_rate), produced)
            self.state.total_count += produced
            self.state.reject_count += defects
            self.state.good_count += produced - defects
        else:
            self.state.downtime_minutes += 1

        runtime = max(self.state.elapsed_minutes - self.state.downtime_minutes, 0)
        target_rate = 60 / self.ideal_cycle_time_seconds
        current_rate = 0 if machine_state != MachineState.running else produced
        machine = Machine(
            id="LINE-01",
            name="Filling Line 01",
            state=machine_state,
            current_product="SKU-1842",
            operator="A Shift",
        )
        telemetry = Telemetry(
            runtime_minutes=runtime,
            planned_production_minutes=self.planned_production_minutes,
            downtime_minutes=self.state.downtime_minutes,
            total_count=self.state.total_count,
            good_count=self.state.good_count,
            reject_count=self.state.reject_count,
            ideal_cycle_time_seconds=self.ideal_cycle_time_seconds,
            actual_cycle_time_seconds=actual_cycle,
            current_rate_per_minute=current_rate,
            target_rate_per_minute=target_rate,
            last_event_type=event_type,
            last_event_message=self._event_message(event_type),
        )
        return machine, telemetry

    def _event_type(self) -> EventType:
        tick = self.state.tick
        if tick % 29 == 0:
            return EventType.breakdown
        if tick % 23 == 0:
            return EventType.setup_adjustment
        if tick % 17 == 0:
            return EventType.production_reject
        if tick % 13 == 0:
            return EventType.reduced_speed
        if tick % 11 == 0:
            return EventType.small_stop
        if tick % 7 == 0:
            return EventType.startup_reject
        return EventType.normal

    def _machine_state(self, event_type: EventType) -> MachineState:
        if event_type == EventType.breakdown:
            return MachineState.stopped
        if event_type == EventType.setup_adjustment:
            return MachineState.changeover
        if event_type == EventType.small_stop:
            return MachineState.starved
        return MachineState.running

    def _actual_cycle_time(self, event_type: EventType) -> float:
        if event_type == EventType.reduced_speed:
            return round(self.ideal_cycle_time_seconds * 1.35, 2)
        if event_type in {EventType.startup_reject, EventType.production_reject}:
            return round(self.ideal_cycle_time_seconds * 1.08, 2)
        return round(self.ideal_cycle_time_seconds * self.random.uniform(0.96, 1.08), 2)

    @staticmethod
    def _event_message(event_type: EventType) -> str:
        messages = {
            EventType.breakdown: "Main filler faulted and required operator intervention.",
            EventType.setup_adjustment: "Changeover adjustment is extending planned setup time.",
            EventType.small_stop: "Short material starvation detected at infeed.",
            EventType.reduced_speed: "Line is running below ideal cycle speed.",
            EventType.startup_reject: "Startup stabilization produced elevated rejects.",
            EventType.production_reject: "Vision inspection reject rate increased.",
            EventType.normal: "Line is running within the expected operating band.",
        }
        return messages[event_type]
