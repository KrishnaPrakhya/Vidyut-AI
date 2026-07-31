from __future__ import annotations

import argparse
from dataclasses import dataclass

from services.dispatch.outbox import Outbox
from services.forecast.naive import DampedTrendForecaster
from services.sim.controllers.base import Controller
from services.sim.controllers.baseline import BaselineController
from services.sim.controllers.vidyut import VidyutController
from services.sim.injection import Injection, apply_injections
from services.sim.metrics import ArmSnapshot, RunTotals, finalise, tick_snapshot
from services.sim.scenario import N_TICKS
from services.sim.world import (
    World,
    apply_loads,
    apply_scheduled_faults,
    build_world,
    solve_power_flow,
)

ARMS = ("baseline", "vidyut")


@dataclass
class ArmResult:
    world: World
    controller: Controller
    snapshots: list[ArmSnapshot]
    totals: RunTotals

    @property
    def outbox(self) -> Outbox:
        return getattr(self.controller, "outbox", Outbox())


@dataclass
class RunResult:
    scenario: str
    seed: int
    arms: dict[str, ArmResult]


def make_controller(arm: str, world: World) -> Controller:
    if arm == "baseline":
        return BaselineController()
    return VidyutController(forecaster=DampedTrendForecaster(n_dt=len(world.dt_ids)))


def simulate_arm(
    arm: str,
    scenario: str,
    seed: int,
    ticks: int = N_TICKS,
    params: dict[str, float] | None = None,
    injections: list[Injection] | None = None,
) -> ArmResult:
    world = build_world(arm, scenario, seed, params)
    if injections:
        apply_injections(world, injections)

    controller = make_controller(arm, world)
    snapshots: list[ArmSnapshot] = []

    for tick in range(ticks):
        apply_scheduled_faults(world, tick)
        _, dt_kw, _ = apply_loads(world, tick)
        result = solve_power_flow(world)
        if not result.converged:
            world.nonconverged_ticks += 1

        if hasattr(controller, "forecaster"):
            controller.forecaster.observe(tick, dt_kw)

        events = controller.act(world, tick, result)
        snapshot = tick_snapshot(world, tick, result, dt_kw, events)
        snapshot.forecast = getattr(controller, "last_forecast", None)
        snapshots.append(snapshot)
        world.actuation.prune(tick)

    return ArmResult(
        world=world,
        controller=controller,
        snapshots=snapshots,
        totals=finalise(world, snapshots),
    )


def simulate(
    scenario: str,
    seed: int,
    ticks: int = N_TICKS,
    params: dict[str, float] | None = None,
    injections: list[Injection] | None = None,
) -> RunResult:
    return RunResult(
        scenario=scenario,
        seed=seed,
        arms={
            arm: simulate_arm(arm, scenario, seed, ticks, params, injections) for arm in ARMS
        },
    )


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def print_metrics_table(result: RunResult) -> None:
    baseline = result.arms["baseline"].totals
    vidyut = result.arms["vidyut"].totals

    rows = [
        ("Energy delivered kWh", baseline.served_kwh, vidyut.served_kwh, 0),
        ("Unserved energy kWh", baseline.unserved_kwh, vidyut.unserved_kwh, 1),
        ("Unserved energy cost Rs", baseline.unserved_cost_rs, vidyut.unserved_cost_rs, 0),
        ("Homes dark, peak count", baseline.peak_homes_dark, vidyut.peak_homes_dark, 0),
        ("Homes dark, household-minutes", baseline.homes_dark_minutes, vidyut.homes_dark_minutes, 0),
        ("Critical-load uptime %", baseline.critical_uptime_pct, vidyut.critical_uptime_pct, 3),
        ("Max transformer loading %", baseline.max_trafo_loading_pct, vidyut.max_trafo_loading_pct, 1),
        ("Feeder spread, mean %", baseline.mean_spread_pct, vidyut.mean_spread_pct, 1),
        ("Feeder spread, max %", baseline.max_spread_pct, vidyut.max_spread_pct, 1),
        ("Peak served kVA", baseline.peak_kva, vidyut.peak_kva, 0),
        ("Network losses kWh", baseline.total_losses_kwh, vidyut.total_losses_kwh, 1),
        ("Losses % of delivered", baseline.losses_pct_of_delivered, vidyut.losses_pct_of_delivered, 2),
        ("Households affected", baseline.households_curtailed, vidyut.households_curtailed, 0),
        ("Worst household burden, min", baseline.max_household_burden_min, vidyut.max_household_burden_min, 0),
        ("Curtailment Gini, affected", baseline.gini_affected, vidyut.gini_affected, 4),
        ("Curtailment Gini, all households", baseline.gini, vidyut.gini, 4),
        ("Non-converged ticks", baseline.nonconverged_ticks, vidyut.nonconverged_ticks, 0),
    ]

    width = max(len(name) for name, *_ in rows)
    print(f"\nscenario={result.scenario}  seed={result.seed}\n")
    print(f"{'metric'.ljust(width)}  {'baseline':>14}  {'vidyut':>14}  {'delta':>14}")
    print("-" * (width + 50))
    for name, base_value, vid_value, digits in rows:
        delta = vid_value - base_value
        print(
            f"{name.ljust(width)}  {_fmt(base_value, digits):>14}  "
            f"{_fmt(vid_value, digits):>14}  {_fmt(delta, digits):>14}"
        )

    print("\nhousehold-minutes of intervention, by severity")
    levels = ["price_signal", "device", "load_limit", "disconnect"]
    for level in levels:
        base_minutes = baseline.minutes_by_level.get(level, 0.0)
        vid_minutes = vidyut.minutes_by_level.get(level, 0.0)
        if base_minutes or vid_minutes:
            print(f"  {level.ljust(14)}  {_fmt(base_minutes, 0):>14}  {_fmt(vid_minutes, 0):>14}")

    share = result.arms["vidyut"].totals.addressable_share_of_load
    print(f"\naddressable share of load: {share * 100:.1f}%")
    print(f"vidyut events by tier: {vidyut.events_by_tier}")
    print(f"baseline events by tier: {baseline.events_by_tier}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="services.sim.run")
    parser.add_argument("--scenario", default="heatwave")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=N_TICKS)
    args = parser.parse_args()

    print_metrics_table(simulate(args.scenario, args.seed, args.ticks))


if __name__ == "__main__":
    main()
