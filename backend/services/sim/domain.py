from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

DeviceKind = Literal["ac", "water_heater", "ev_charger", "pump", "bess"]
HouseholdTier = Literal["critical", "essential", "standard"]


@dataclass
class Device:
    kind: DeviceKind
    rated_kw: float
    controllable: bool
    deferrable_window_min: int
    comfort_cost_per_min: float


@dataclass
class Household:
    id: str
    dt_id: str
    tier: HouseholdTier
    base_profile_kw: np.ndarray
    devices: list[Device]
    ami: bool
    meter_load_limit_supported: bool
    curtailment_debt_min: float = 0.0

    @property
    def addressable(self) -> bool:
        return any(d.controllable for d in self.devices) or (
            self.ami and self.meter_load_limit_supported
        )

    @property
    def has_connected_device(self) -> bool:
        return any(d.controllable for d in self.devices)


@dataclass
class DistributionTransformer:
    id: str
    feeder_id: str
    rating_kva: float
    households: list[str] = field(default_factory=list)


@dataclass
class TieSwitch:
    id: str
    bus_a: str
    bus_b: str
    closed: bool = False
