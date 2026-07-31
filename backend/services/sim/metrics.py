from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from services.sim.controllers.base import TickEvent
from services.sim.ledger import gini
from services.sim.world import PowerFlowResult, World
from services.timebase import TICK_HOURS, TICK_MINUTES

POWER_FACTOR = 0.95


@dataclass
class FeederSnapshot:
    id: str
    loading_pct: float
    losses_kw: float


@dataclass
class DtSnapshot:
    id: str
    loading_pct: float
    energized: bool
    households_dark: int


@dataclass
class ArmMetrics:
    converged: bool = True
    peak_kva: float = 0.0
    spread_pct: float = 0.0
    losses_kw: float = 0.0
    homes_dark: int = 0
    critical_uptime_pct: float = 100.0
    unserved_kwh: float = 0.0
    gini: float = 0.0
    max_trafo_loading_pct: float = 0.0


@dataclass
class ArmSnapshot:
    feeders: list[FeederSnapshot]
    dts: list[DtSnapshot]
    tie_switches: list[dict]
    metrics: ArmMetrics
    events: list[TickEvent]
    forecast: dict | None = None


@dataclass
class RunTotals:
    arm: str
    peak_kva: float = 0.0
    max_trafo_loading_pct: float = 0.0
    total_losses_kwh: float = 0.0
    mean_spread_pct: float = 0.0
    max_spread_pct: float = 0.0
    homes_dark_minutes: float = 0.0
    peak_homes_dark: int = 0
    critical_uptime_pct: float = 100.0
    unserved_kwh: float = 0.0
    demanded_kwh: float = 0.0
    flexibility_kwh: float = 0.0
    energy_balance_error_kwh: float = 0.0
    unserved_cost_rs: float = 0.0
    served_kwh: float = 0.0
    losses_pct_of_delivered: float = 0.0
    gini: float = 0.0
    gini_affected: float = 0.0
    max_household_burden_min: float = 0.0
    households_curtailed: int = 0
    nonconverged_ticks: int = 0
    addressable_share_of_load: float = 0.0
    minutes_by_level: dict[str, float] = field(default_factory=dict)
    events_by_tier: dict[int, int] = field(default_factory=dict)
    spread_series: list[float] = field(default_factory=list)


def tick_snapshot(
    world: World, tick: int, result: PowerFlowResult, dt_kw: np.ndarray, events: list[TickEvent]
) -> ArmSnapshot:
    feeders = [
        FeederSnapshot(
            id=feeder_id,
            loading_pct=round(result.feeder_loading_pct[feeder_id], 1),
            losses_kw=round(result.feeder_losses_kw[feeder_id], 2),
        )
        for feeder_id in world.ctx.dt_ids_of_feeder
    ]

    disconnected = world.actuation.households_disconnected(tick)
    dts: list[DtSnapshot] = []
    for dt_id in world.dt_ids:
        trafo_idx = world.ctx.dt_trafo_idx[dt_id]
        energized = world.dt_energized[dt_id]
        households = world.ctx.dts[dt_id].households
        dark = (
            len(households)
            if not energized
            else sum(1 for h in households if h in disconnected)
        )
        loading = (
            float(result.trafo_loading_pct[trafo_idx]) if result.converged else float("nan")
        )
        dts.append(
            DtSnapshot(
                id=dt_id,
                loading_pct=round(loading, 1) if result.converged else 0.0,
                energized=energized,
                households_dark=dark,
            )
        )

    loadings = [f.loading_pct for f in feeders]
    spread = max(loadings) - min(loadings) if result.converged else 0.0
    total_kw = float(dt_kw.sum())
    homes_dark = sum(d.households_dark for d in dts)

    metrics = ArmMetrics(
        converged=result.converged,
        peak_kva=round(total_kw / POWER_FACTOR, 1),
        spread_pct=round(spread, 1),
        losses_kw=round(result.losses_kw, 2) if result.converged else 0.0,
        homes_dark=homes_dark,
        critical_uptime_pct=round(critical_uptime(world, tick), 3),
        unserved_kwh=round(world.unserved_kwh, 2),
        gini=round(current_gini(world), 4),
        max_trafo_loading_pct=(
            round(float(np.nanmax(result.trafo_loading_pct)), 1) if result.converged else 0.0
        ),
    )

    tie_switches = [
        {"id": ts_id, "closed": bool(world.ctx.net.switch.at[idx, "closed"])}
        for ts_id, idx in world.ctx.tie_switch_pp_idx.items()
    ]

    return ArmSnapshot(
        feeders=feeders, dts=dts, tie_switches=tie_switches, metrics=metrics, events=events
    )


def critical_uptime(world: World, tick: int) -> float:
    n_critical = sum(1 for h in world.households.values() if h.tier == "critical")
    if n_critical == 0:
        return 100.0
    elapsed_minutes = (tick + 1) * TICK_MINUTES
    possible = n_critical * elapsed_minutes
    return 100.0 * (1.0 - world.critical_household_dark_minutes / possible)


def current_gini(world: World) -> float:
    debts = np.array(
        [world.ledger.accrued_of(hh_id) for hh_id in world.households], dtype=float
    )
    return gini(debts)


def addressable_share_of_load(world: World) -> float:
    peak_tick = int(np.argmax(world.demand.base_kw.sum(axis=0)))
    demand = world.demand.base_kw[:, peak_tick]
    addressable = np.array(
        [world.households[h].addressable for h in world.demand.household_ids], dtype=bool
    )
    total = float(demand.sum())
    if total <= 0.0:
        return 0.0
    return float(demand[addressable].sum() / total)


def finalise(world: World, snapshots: list[ArmSnapshot]) -> RunTotals:
    totals = RunTotals(arm=world.arm)
    totals.peak_kva = max(s.metrics.peak_kva for s in snapshots)
    totals.max_trafo_loading_pct = max(s.metrics.max_trafo_loading_pct for s in snapshots)
    totals.total_losses_kwh = sum(s.metrics.losses_kw for s in snapshots) * TICK_HOURS
    totals.spread_series = [s.metrics.spread_pct for s in snapshots]
    totals.mean_spread_pct = float(np.mean(totals.spread_series))
    totals.max_spread_pct = float(np.max(totals.spread_series))
    totals.homes_dark_minutes = world.homes_dark_minutes
    totals.peak_homes_dark = max(s.metrics.homes_dark for s in snapshots)
    totals.critical_uptime_pct = critical_uptime(world, len(snapshots) - 1)
    totals.unserved_kwh = world.unserved_kwh
    totals.demanded_kwh = world.demanded_kwh
    totals.flexibility_kwh = world.flexibility_kwh
    totals.energy_balance_error_kwh = abs(
        world.demanded_kwh
        - world.served_kwh
        - world.flexibility_kwh
        - world.unserved_kwh
    )
    totals.unserved_cost_rs = world.unserved_kwh * world.scenario.tariff_rs_per_kwh
    totals.served_kwh = world.served_kwh
    totals.losses_pct_of_delivered = (
        100.0 * totals.total_losses_kwh / world.served_kwh if world.served_kwh > 0 else 0.0
    )

    debts = np.array(list(world.ledger.debt_min.values()), dtype=float)
    totals.gini = current_gini(world)
    totals.gini_affected = gini(debts)
    totals.max_household_burden_min = float(debts.max()) if debts.size else 0.0
    totals.households_curtailed = len(world.ledger.debt_min)
    totals.nonconverged_ticks = world.nonconverged_ticks
    totals.addressable_share_of_load = addressable_share_of_load(world)

    minutes: dict[str, float] = {}
    for record in world.ledger.records:
        minutes[record.level] = minutes.get(record.level, 0.0) + record.minutes
    totals.minutes_by_level = minutes

    by_tier: dict[int, int] = {}
    for snapshot in snapshots:
        for event in snapshot.events:
            by_tier[event.tier] = by_tier.get(event.tier, 0) + 1
    totals.events_by_tier = dict(sorted(by_tier.items()))
    return totals
