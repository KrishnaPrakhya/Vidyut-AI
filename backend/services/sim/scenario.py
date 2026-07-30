from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"

N_TICKS = 96


@dataclass
class Scenario:
    name: str
    ami_penetration: float
    connected_device_penetration: float
    ev_penetration: float
    critical_share: float
    essential_share: float
    peak_start_tick: int
    peak_end_tick: int
    peak_multiplier: float
    night_base_kw: float
    tariff_rs_per_kwh: float

    @property
    def standard_share(self) -> float:
        return 1.0 - self.critical_share - self.essential_share


def load_scenario(name: str) -> Scenario:
    path = SCENARIO_DIR / f"{name}.yaml"
    with path.open() as f:
        raw = yaml.safe_load(f)
    return Scenario(name=name, **raw)
