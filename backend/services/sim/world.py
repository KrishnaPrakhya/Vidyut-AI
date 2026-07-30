from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandapower as pp

from services.actuation.commands import ActuationState
from services.sim.demand import DemandModel, build_demand_model, design_day_peak_kw, natural_demand_kw
from services.sim.domain import Household
from services.sim.ledger import FairnessLedger
from services.sim.network import NetworkContext, build_network, resize_transformers, set_dt_load_kw
from services.sim.population import build_population
from services.sim.rng import make_rngs
from services.sim.scenario import Scenario, load_scenario

TICK_HOURS = 0.25
SAFE_LIMIT_FRACTION = 0.90


@dataclass
class PowerFlowResult:
    converged: bool
    vm_pu_min: float
    vm_pu_max: float
    trafo_loading_pct: np.ndarray
    line_loading_pct: np.ndarray
    feeder_loading_pct: dict[str, float]
    feeder_losses_kw: dict[str, float]
    losses_kw: float


@dataclass
class World:
    arm: str
    scenario: Scenario
    seed: int
    ctx: NetworkContext
    households: dict[str, Household]
    demand: DemandModel
    ledger: FairnessLedger
    actuation: ActuationState
    rngs: dict[str, np.random.Generator]
    dt_index_of_household: np.ndarray
    dt_row: dict[str, int]
    feeder_head_line: dict[str, int]
    dt_energized: dict[str, bool] = field(default_factory=dict)
    dt_reenergize_tick: dict[str, int] = field(default_factory=dict)
    unserved_kwh: float = 0.0
    served_kwh: float = 0.0
    critical_household_dark_minutes: float = 0.0
    homes_dark_minutes: float = 0.0
    nonconverged_ticks: int = 0

    @property
    def dt_ids(self) -> list[str]:
        return self.ctx.dt_ids

    def rating_kw(self, dt_id: str) -> float:
        return self.ctx.dts[dt_id].rating_kva * 0.95

    def safe_limit_kw(self, dt_id: str) -> float:
        return SAFE_LIMIT_FRACTION * self.rating_kw(dt_id)


def build_world(arm: str, scenario_name: str, seed: int) -> World:
    rngs = make_rngs(seed)
    scenario = load_scenario(scenario_name)
    ctx = build_network(rngs["topology"])
    households = build_population(ctx, scenario, rngs["population"])
    demand = build_demand_model(households, scenario, rngs["profiles"])

    dt_of_household = {hh_id: households[hh_id].dt_id for hh_id in demand.household_ids}
    resize_transformers(ctx, design_day_peak_kw(demand, dt_of_household), rngs["topology"])

    dt_row = {dt_id: i for i, dt_id in enumerate(ctx.dt_ids)}
    dt_index_of_household = np.array(
        [dt_row[dt_of_household[hh_id]] for hh_id in demand.household_ids], dtype=int
    )
    feeder_head_line = {
        feeder_id: ctx.dt_section_line[
            next(d for d in dt_ids if ctx.dt_parent[d] is None)
        ]
        for feeder_id, dt_ids in ctx.dt_ids_of_feeder.items()
    }

    return World(
        arm=arm,
        scenario=scenario,
        seed=seed,
        ctx=ctx,
        households=households,
        demand=demand,
        ledger=FairnessLedger(),
        actuation=ActuationState(),
        rngs=rngs,
        dt_index_of_household=dt_index_of_household,
        dt_row=dt_row,
        feeder_head_line=feeder_head_line,
        dt_energized={dt_id: True for dt_id in ctx.dt_ids},
        dt_reenergize_tick={},
    )


def household_demand_kw(world: World, t: int) -> np.ndarray:
    demand = natural_demand_kw(world.demand, t)
    reductions = world.actuation.reduction_by_household(t)
    if reductions:
        rows = np.array([world.demand.row_of[h] for h in reductions], dtype=int)
        values = np.array(list(reductions.values()))
        demand[rows] = np.maximum(demand[rows] - values, 0.0)
    return demand


def aggregate_to_dt(world: World, household_kw: np.ndarray) -> np.ndarray:
    return np.bincount(
        world.dt_index_of_household, weights=household_kw, minlength=len(world.dt_ids)
    )


def solve_power_flow(world: World) -> PowerFlowResult:
    net = world.ctx.net
    try:
        pp.runpp(net, numba=False)
    except Exception:
        n_trafo, n_line = len(net.trafo), len(net.line)
        return PowerFlowResult(
            converged=False,
            vm_pu_min=float("nan"),
            vm_pu_max=float("nan"),
            trafo_loading_pct=np.full(n_trafo, np.nan),
            line_loading_pct=np.full(n_line, np.nan),
            feeder_loading_pct={f: float("nan") for f in world.feeder_head_line},
            feeder_losses_kw={f: float("nan") for f in world.feeder_head_line},
            losses_kw=float("nan"),
        )

    trafo_loading = net.res_trafo.loading_percent.to_numpy()
    line_loading = net.res_line.loading_percent.to_numpy()
    line_losses_kw = net.res_line.pl_mw.to_numpy() * 1000.0

    feeder_loading = {
        feeder_id: float(line_loading[line_idx])
        for feeder_id, line_idx in world.feeder_head_line.items()
    }
    feeder_losses = {
        feeder_id: float(
            sum(line_losses_kw[world.ctx.dt_section_line[d]] for d in dt_ids)
        )
        for feeder_id, dt_ids in world.ctx.dt_ids_of_feeder.items()
    }

    return PowerFlowResult(
        converged=True,
        vm_pu_min=float(net.res_bus.vm_pu.min()),
        vm_pu_max=float(net.res_bus.vm_pu.max()),
        trafo_loading_pct=trafo_loading,
        line_loading_pct=line_loading,
        feeder_loading_pct=feeder_loading,
        feeder_losses_kw=feeder_losses,
        losses_kw=float(line_losses_kw.sum()),
    )


def apply_loads(world: World, t: int) -> tuple[np.ndarray, np.ndarray, int]:
    household_kw = household_demand_kw(world, t)
    disconnected = world.actuation.households_disconnected(t)

    served = household_kw.copy()
    homes_dark = 0

    if disconnected:
        rows = np.array([world.demand.row_of[h] for h in disconnected], dtype=int)
        world.unserved_kwh += float(served[rows].sum()) * TICK_HOURS
        world.homes_dark_minutes += 15.0 * len(disconnected)
        homes_dark += len(disconnected)
        served[rows] = 0.0

    dt_kw = aggregate_to_dt(world, served)

    for dt_id, energized in world.dt_energized.items():
        if energized:
            continue
        row = world.dt_row[dt_id]
        dark_households = [
            h for h in world.ctx.dts[dt_id].households if h not in disconnected
        ]
        world.unserved_kwh += float(dt_kw[row]) * TICK_HOURS
        world.homes_dark_minutes += 15.0 * len(dark_households)
        world.critical_household_dark_minutes += 15.0 * sum(
            1 for h in dark_households if world.households[h].tier == "critical"
        )
        homes_dark += len(dark_households)
        dt_kw[row] = 0.0

    for dt_id in world.dt_ids:
        set_dt_load_kw(world.ctx, dt_id, float(dt_kw[world.dt_row[dt_id]]))

    world.served_kwh += float(dt_kw.sum()) * TICK_HOURS
    return household_kw, dt_kw, homes_dark
