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


OVERRIDABLE = {
    "ami_penetration",
    "connected_device_penetration",
    "ev_penetration",
    "critical_share",
    "essential_share",
    "peak_multiplier",
    "tariff_rs_per_kwh",
}


def available_scenarios() -> list[str]:
    return sorted(path.stem for path in SCENARIO_DIR.glob("*.yaml"))


def load_scenario(name: str, overrides: dict[str, float] | None = None) -> Scenario:
    path = SCENARIO_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"unknown scenario {name!r}")
    with path.open() as f:
        raw = yaml.safe_load(f)

    for key, value in (overrides or {}).items():
        if key in OVERRIDABLE and value is not None:
            raw[key] = value

    return Scenario(name=name, **raw)
