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
    _by_tick: dict[int, list[ActuationCommand]] = field(
        default_factory=dict, init=False, repr=False
    )
    _reductions_by_tick: dict[int, dict[str, float]] = field(
        default_factory=dict, init=False, repr=False
    )
    _disconnected_by_tick: dict[int, set[str]] = field(
        default_factory=dict, init=False, repr=False
    )
    _households_by_tick: dict[int, set[str]] = field(
        default_factory=dict, init=False, repr=False
    )

    def issue(self, command: ActuationCommand) -> None:
        self.commands.append(command)
        for tick in range(command.issued_tick, command.expires_tick):
            self._by_tick.setdefault(tick, []).append(command)
            reductions = self._reductions_by_tick.setdefault(tick, {})
            reductions[command.household_id] = (
                reductions.get(command.household_id, 0.0) + command.kw_reduction
            )
            self._households_by_tick.setdefault(tick, set()).add(command.household_id)
            if command.level == "disconnect":
                self._disconnected_by_tick.setdefault(tick, set()).add(
                    command.household_id
                )

    def active(self, tick: int) -> list[ActuationCommand]:
        return list(self._by_tick.get(tick, ()))

    def reduction_by_household(self, tick: int) -> dict[str, float]:
        return dict(self._reductions_by_tick.get(tick, {}))

    def households_disconnected(self, tick: int) -> set[str]:
        return set(self._disconnected_by_tick.get(tick, ()))

    def households_active(self, tick: int) -> set[str]:
        return set(self._households_by_tick.get(tick, ()))

    def prune(self, tick: int) -> None:
        self.commands = [c for c in self.commands if c.expires_tick > tick]
        self._by_tick.pop(tick, None)
        self._reductions_by_tick.pop(tick, None)
        self._disconnected_by_tick.pop(tick, None)
        self._households_by_tick.pop(tick, None)
