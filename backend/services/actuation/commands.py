from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ActuationLevel = Literal["price_signal", "device", "load_limit", "disconnect"]

LEVEL_MECHANISM = {
    "price_signal": "tod_price_broadcast",
    "device": "connected_device",
    "load_limit": "meter_load_limit",
    "disconnect": "service_disconnect",
}


@dataclass
class ActuationCommand:
    household_id: str
    dt_id: str
    level: ActuationLevel
    kw_reduction: float
    issued_tick: int
    expires_tick: int
    reason_code: str
    device_kind: str | None = None

    def active_at(self, tick: int) -> bool:
        return self.issued_tick <= tick < self.expires_tick

    @property
    def mechanism(self) -> str:
        return LEVEL_MECHANISM[self.level]


@dataclass
class ActuationState:
    commands: list[ActuationCommand] = field(default_factory=list)

    def issue(self, command: ActuationCommand) -> None:
        self.commands.append(command)

    def active(self, tick: int) -> list[ActuationCommand]:
        return [c for c in self.commands if c.active_at(tick)]

    def reduction_by_household(self, tick: int) -> dict[str, float]:
        reductions: dict[str, float] = {}
        for command in self.commands:
            if command.active_at(tick):
                reductions[command.household_id] = (
                    reductions.get(command.household_id, 0.0) + command.kw_reduction
                )
        return reductions

    def households_disconnected(self, tick: int) -> set[str]:
        return {
            c.household_id
            for c in self.commands
            if c.active_at(tick) and c.level == "disconnect"
        }

    def households_active(self, tick: int) -> set[str]:
        return {command.household_id for command in self.commands if command.active_at(tick)}

    def prune(self, tick: int) -> None:
        self.commands = [c for c in self.commands if c.expires_tick > tick]
