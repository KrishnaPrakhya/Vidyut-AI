from __future__ import annotations

import numpy as np

from services.sim.domain import Device, Household, HouseholdTier
from services.sim.network import NetworkContext
from services.sim.scenario import N_TICKS, Scenario

HOUSEHOLDS_PER_DT = 70

DEVICE_SPECS = {
    "ac": dict(rated_kw=1.5, deferrable_window_min=45, comfort_cost_per_min=0.9),
    "water_heater": dict(rated_kw=2.0, deferrable_window_min=120, comfort_cost_per_min=0.25),
    "ev_charger": dict(rated_kw=3.3, deferrable_window_min=240, comfort_cost_per_min=0.1),
    "pump": dict(rated_kw=0.75, deferrable_window_min=180, comfort_cost_per_min=0.15),
    "bess": dict(rated_kw=2.5, deferrable_window_min=60, comfort_cost_per_min=0.02),
}

_MORNING = np.exp(-0.5 * ((np.arange(N_TICKS) - 28) / 6.0) ** 2)
_EVENING = np.exp(-0.5 * ((np.arange(N_TICKS) - 76) / 9.0) ** 2)
_NOON = np.exp(-0.5 * ((np.arange(N_TICKS) - 52) / 14.0) ** 2)


def _base_shape(rng: np.random.Generator) -> np.ndarray:
    morning_w = rng.uniform(0.35, 0.65)
    evening_w = rng.uniform(0.85, 1.25)
    noon_w = rng.uniform(0.15, 0.45)
    shape = morning_w * _MORNING + evening_w * _EVENING + noon_w * _NOON
    jitter = rng.normal(1.0, 0.05, N_TICKS)
    return np.clip(shape * jitter, 0.0, None)


def _assign_tier(rng: np.random.Generator, scenario: Scenario) -> HouseholdTier:
    draw = rng.random()
    if draw < scenario.critical_share:
        return "critical"
    if draw < scenario.critical_share + scenario.essential_share:
        return "essential"
    return "standard"


def _build_devices(
    rng: np.random.Generator, scenario: Scenario, tier: HouseholdTier, ac_density: float
) -> list[Device]:
    devices: list[Device] = []
    connected = rng.random() < scenario.connected_device_penetration

    weights = np.array([0.35, 0.45 * ac_density, 0.20 * ac_density**2])
    n_ac = int(rng.choice([0, 1, 2], p=weights / weights.sum()))
    for _ in range(n_ac):
        devices.append(_make_device("ac", rng, controllable=connected and tier != "critical"))

    if rng.random() < 0.55:
        devices.append(_make_device("water_heater", rng, controllable=connected))
    if rng.random() < scenario.ev_penetration:
        devices.append(_make_device("ev_charger", rng, controllable=connected))
    if rng.random() < 0.30:
        devices.append(_make_device("pump", rng, controllable=connected))
    if rng.random() < 0.04:
        devices.append(_make_device("bess", rng, controllable=connected))
    return devices


def _make_device(kind: str, rng: np.random.Generator, controllable: bool) -> Device:
    spec = DEVICE_SPECS[kind]
    return Device(
        kind=kind,
        rated_kw=float(spec["rated_kw"] * rng.uniform(0.85, 1.15)),
        controllable=controllable,
        deferrable_window_min=int(spec["deferrable_window_min"]),
        comfort_cost_per_min=float(spec["comfort_cost_per_min"] * rng.uniform(0.9, 1.1)),
    )


def build_population(
    ctx: NetworkContext, scenario: Scenario, rng: np.random.Generator
) -> dict[str, Household]:
    households: dict[str, Household] = {}
    feeder_affluence = {
        feeder_id: float(np.clip(rng.lognormal(0.0, 0.28), 0.6, 1.7))
        for feeder_id in ctx.dt_ids_of_feeder
    }
    for dt_id in ctx.dt_ids:
        dt = ctx.dts[dt_id]
        affluence = feeder_affluence[ctx.feeder_of_dt[dt_id]]
        ac_density = float(np.clip(affluence * rng.lognormal(0.0, 0.22), 0.35, 2.4))
        for k in range(HOUSEHOLDS_PER_DT):
            hh_id = f"{dt_id}-H{k + 1:03d}"
            tier = _assign_tier(rng, scenario)
            ami = rng.random() < scenario.ami_penetration
            profile = _base_shape(rng) * rng.uniform(0.55, 1.45) + scenario.night_base_kw
            household = Household(
                id=hh_id,
                dt_id=dt_id,
                tier=tier,
                base_profile_kw=profile,
                devices=_build_devices(rng, scenario, tier, ac_density),
                ami=ami,
                meter_load_limit_supported=ami and rng.random() < 0.8,
            )
            households[hh_id] = household
            dt.households.append(hh_id)
    return households
