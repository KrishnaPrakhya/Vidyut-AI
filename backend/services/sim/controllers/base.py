from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from services.sim.world import PowerFlowResult, World


class ReasonCode:
    BASELINE_DT_OVERLOAD = "BASELINE_DT_OVERLOAD"
    BASELINE_RESTORE = "BASELINE_RESTORE"
    STEADY_STATE_SHIFT = "STEADY_STATE_SHIFT"
    RECONFIGURATION = "RECONFIGURATION"
    PRICE_SIGNAL_PEAK = "PRICE_SIGNAL_PEAK"
    PRE_EMPTIVE_THERMAL = "PRE_EMPTIVE_THERMAL"
    ESCALATION_LOAD_LIMIT = "ESCALATION_LOAD_LIMIT"
    LAST_RESORT_ROTATION = "LAST_RESORT_ROTATION"
    NOT_ADDRESSABLE = "NOT_ADDRESSABLE"


@dataclass
class TickEvent:
    tier: int
    action: str
    target: str
    kw: float
    households: int
    reason_code: str
    detail: str = ""
    forecast_kw: float | None = None
    safe_limit_kw: float | None = None


@dataclass
class ControllerState:
    events: list[TickEvent] = field(default_factory=list)

    def emit(
        self,
        tier: int,
        action: str,
        target: str,
        kw: float,
        households: int,
        reason_code: str,
        detail: str = "",
        forecast_kw: float | None = None,
        safe_limit_kw: float | None = None,
    ) -> None:
        self.events.append(
            TickEvent(
                tier,
                action,
                target,
                round(kw, 2),
                households,
                reason_code,
                detail,
                round(forecast_kw, 3) if forecast_kw is not None else None,
                round(safe_limit_kw, 3) if safe_limit_kw is not None else None,
            )
        )

    def drain(self) -> list[TickEvent]:
        events, self.events = self.events, []
        return events


class Controller(Protocol):
    name: str

    def act(self, world: World, tick: int, result: PowerFlowResult) -> list[TickEvent]: ...
