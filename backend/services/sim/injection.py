from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

InjectionType = Literal["heatwave", "ev_surge", "cloud_cover", "dt_fault"]

CLOUD_COVER_KW_PER_HOUSEHOLD = 0.45
DT_FAULT_TICKS = 6


@dataclass
class Injection:
    type: InjectionType
    magnitude: float
    from_tick: int
    dt_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "magnitude": self.magnitude,
            "from_tick": self.from_tick,
            "dt_id": self.dt_id,
        }


def apply_injections(world, injections: list[Injection]) -> None:
    for injection in injections:
        if injection.type == "heatwave":
            _amplify_thermal_stress(world, injection)
        elif injection.type == "ev_surge":
            _amplify_ev_charging(world, injection)
        elif injection.type == "cloud_cover":
            _remove_rooftop_solar(world, injection)
        elif injection.type == "dt_fault":
            _schedule_dt_fault(world, injection)


def _amplify_thermal_stress(world, injection: Injection) -> None:
    stress = world.demand.thermal_stress
    window = slice(injection.from_tick, None)
    stress[window] = np.clip(stress[window] * (1.0 + injection.magnitude), 0.0, 1.0)


def _amplify_ev_charging(world, injection: Injection) -> None:
    for run in world.demand.deferrable:
        if run.kind != "ev_charger":
            continue
        if run.start + run.duration_ticks < injection.from_tick:
            continue
        run.rated_kw *= 1.0 + injection.magnitude


def _remove_rooftop_solar(world, injection: Injection) -> None:
    added_kw = CLOUD_COVER_KW_PER_HOUSEHOLD * injection.magnitude
    world.demand.base_kw[:, injection.from_tick :] += added_kw


def _schedule_dt_fault(world, injection: Injection) -> None:
    dt_id = injection.dt_id
    if dt_id is None:
        loads = world.demand.base_kw.sum(axis=1)
        totals = np.bincount(
            world.dt_index_of_household, weights=loads, minlength=len(world.dt_ids)
        )
        dt_id = world.dt_ids[int(np.argmax(totals))]

    world.scheduled_faults.append(
        (dt_id, injection.from_tick, injection.from_tick + DT_FAULT_TICKS)
    )
