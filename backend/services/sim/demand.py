from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from services.sim.domain import Household
from services.sim.scenario import N_TICKS, Scenario
from services.timebase import TICK_MINUTES

BASELINE_THERMAL_STRESS = 0.22
SHIFTABLE_KINDS = ("water_heater", "ev_charger", "pump", "bess")

RUN_DURATION_TICKS = {
    "water_heater": (2, 4),
    "ev_charger": (8, 16),
    "pump": (2, 5),
    "bess": (4, 8),
}

NATURAL_START_RANGE = {
    "water_heater": (24, 34),
    "ev_charger": (72, 88),
    "pump": (20, 30),
    "bess": (70, 84),
}


@dataclass
class DeferrableRun:
    hh_id: str
    kind: str
    rated_kw: float
    natural_start: int
    duration_ticks: int
    window_ticks: int
    controllable: bool
    comfort_cost_per_min: float
    start: int = 0

    def draws_at(self, t: int) -> bool:
        return self.start <= t < self.start + self.duration_ticks


@dataclass
class ThermostaticLoad:
    hh_id: str
    rated_kw: float
    controllable: bool
    comfort_cost_per_min: float


@dataclass
class DemandModel:
    scenario: Scenario
    household_ids: list[str]
    row_of: dict[str, int]
    base_kw: np.ndarray
    thermal_stress: np.ndarray
    thermostatic: list[ThermostaticLoad]
    deferrable: list[DeferrableRun]
    thermostatic_rows: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=int))
    thermostatic_kw: np.ndarray = field(default_factory=lambda: np.empty(0))


def _thermal_stress_curve(scenario: Scenario) -> np.ndarray:
    ticks = np.arange(N_TICKS)
    start, end = scenario.peak_start_tick, scenario.peak_end_tick
    span = max(end - start, 1)
    ramp = max(int(0.25 * span), 1)

    window = np.zeros(N_TICKS)
    window[(ticks >= start + ramp) & (ticks <= end - ramp)] = 1.0
    up = (ticks >= start) & (ticks < start + ramp)
    window[up] = 0.5 * (1 - np.cos(np.pi * (ticks[up] - start) / ramp))
    down = (ticks > end - ramp) & (ticks <= end)
    window[down] = 0.5 * (1 - np.cos(np.pi * (end - ticks[down]) / ramp))

    stress = BASELINE_THERMAL_STRESS + (scenario.peak_multiplier - 1.0) * window
    return np.clip(stress, 0.0, 1.0)


def build_demand_model(
    households: dict[str, Household], scenario: Scenario, rng: np.random.Generator
) -> DemandModel:
    household_ids = list(households.keys())
    row_of = {hh_id: i for i, hh_id in enumerate(household_ids)}
    base_kw = np.stack([households[h].base_profile_kw for h in household_ids])

    thermostatic: list[ThermostaticLoad] = []
    deferrable: list[DeferrableRun] = []

    for hh_id in household_ids:
        hh = households[hh_id]
        for device in hh.devices:
            if device.kind == "ac":
                thermostatic.append(
                    ThermostaticLoad(
                        hh_id=hh_id,
                        rated_kw=device.rated_kw,
                        controllable=device.controllable,
                        comfort_cost_per_min=device.comfort_cost_per_min,
                    )
                )
                continue
            lo, hi = RUN_DURATION_TICKS[device.kind]
            duration = int(rng.integers(lo, hi + 1))
            s_lo, s_hi = NATURAL_START_RANGE[device.kind]
            natural_start = int(rng.integers(s_lo, s_hi + 1))
            deferrable.append(
                DeferrableRun(
                    hh_id=hh_id,
                    kind=device.kind,
                    rated_kw=device.rated_kw,
                    natural_start=natural_start,
                    duration_ticks=duration,
                    window_ticks=device.deferrable_window_min // TICK_MINUTES,
                    controllable=device.controllable,
                    comfort_cost_per_min=device.comfort_cost_per_min,
                    start=natural_start,
                )
            )

    model = DemandModel(
        scenario=scenario,
        household_ids=household_ids,
        row_of=row_of,
        base_kw=base_kw,
        thermal_stress=_thermal_stress_curve(scenario),
        thermostatic=thermostatic,
        deferrable=deferrable,
    )
    model.thermostatic_rows = np.array([row_of[t.hh_id] for t in thermostatic], dtype=int)
    model.thermostatic_kw = np.array([t.rated_kw for t in thermostatic])
    return model


def natural_demand_kw(model: DemandModel, t: int) -> np.ndarray:
    demand = model.base_kw[:, t].copy()
    if model.thermostatic_rows.size:
        np.add.at(demand, model.thermostatic_rows, model.thermostatic_kw * model.thermal_stress[t])
    for run in model.deferrable:
        if run.draws_at(t):
            demand[model.row_of[run.hh_id]] += run.rated_kw
    return demand


def design_day_peak_kw(model: DemandModel, dt_of_household: dict[str, str]) -> dict[str, float]:
    demand = model.base_kw.copy()
    if model.thermostatic_rows.size:
        np.add.at(demand, model.thermostatic_rows, BASELINE_THERMAL_STRESS * model.thermostatic_kw[:, None])
    for run in model.deferrable:
        if run.kind == "ev_charger":
            continue
        row = model.row_of[run.hh_id]
        demand[row, run.natural_start : run.natural_start + run.duration_ticks] += run.rated_kw

    peaks: dict[str, float] = {}
    for hh_id, row in model.row_of.items():
        dt_id = dt_of_household[hh_id]
        peaks.setdefault(dt_id, np.zeros(N_TICKS))
        peaks[dt_id] += demand[row]
    return {dt_id: float(profile.max()) for dt_id, profile in peaks.items()}


def horizon_demand_kw(model: DemandModel, t0: int, horizon: int) -> np.ndarray:
    end = min(t0 + horizon, N_TICKS)
    return np.stack([natural_demand_kw(model, t) for t in range(t0, end)], axis=1)
