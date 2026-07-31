from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from services.sim.demand import build_demand_model, natural_demand_kw
from services.sim.scenario import N_TICKS, load_scenario
from services.sim.world import build_world

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
FREQ = "15min"
START = "2025-04-01 00:00:00"

DAY_MIX = [
    ("normal", 0.60),
    ("heatwave", 0.25),
    ("ev_surge", 0.15),
]


def _scenario_for_day(day: int, rng: np.random.Generator) -> str:
    names = [name for name, _ in DAY_MIX]
    weights = [weight for _, weight in DAY_MIX]
    return str(rng.choice(names, p=weights))


DAILY_VARIATION_SIGMA = 0.12


def day_load_kw(world, scenario: str, day_rng: np.random.Generator) -> np.ndarray:
    model = build_demand_model(world.households, load_scenario(scenario), day_rng)
    n_dt = len(world.dt_ids)
    n_households = len(world.households)

    daily_factor = np.clip(
        day_rng.normal(1.0, DAILY_VARIATION_SIGMA, size=n_households), 0.6, 1.5
    )

    loads = np.zeros((n_dt, N_TICKS))
    for tick in range(N_TICKS):
        household_kw = natural_demand_kw(model, tick) * daily_factor
        loads[:, tick] = np.bincount(
            world.dt_index_of_household, weights=household_kw, minlength=n_dt
        )
    return loads


def build_dataset(days: int, base_seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(base_seed)
    start = pd.Timestamp(START)

    world = build_world("forecast", "normal", base_seed)
    dt_ids = world.dt_ids
    per_day: list[np.ndarray] = []
    day_scenarios: list[str] = []

    for day in range(days):
        scenario = _scenario_for_day(day, rng)
        loads = day_load_kw(world, scenario, np.random.default_rng(base_seed * 1000 + day))
        per_day.append(loads)
        day_scenarios.append(scenario)
        print(f"  day {day + 1:>3}/{days}  {scenario:<9} peak={loads.max():.0f} kW")

    series = np.concatenate(per_day, axis=1)
    timestamps = pd.date_range(start=start, periods=series.shape[1], freq=FREQ)

    frames = []
    for row, dt_id in enumerate(dt_ids):
        frames.append(
            pd.DataFrame(
                {
                    "item_id": dt_id,
                    "timestamp": timestamps,
                    "target": np.round(series[row], 4),
                }
            )
        )

    frame = pd.concat(frames, ignore_index=True)
    frame.attrs["day_scenarios"] = day_scenarios
    return frame


def build_holdout(base_seed: int, holdout_seed: int, days: int) -> pd.DataFrame:
    world = build_world("forecast", "normal", base_seed)
    loads = day_load_kw(world, "heatwave", np.random.default_rng(holdout_seed))
    dt_ids = world.dt_ids
    start = pd.Timestamp(START) + pd.Timedelta(days=days)
    timestamps = pd.date_range(start=start, periods=N_TICKS, freq=FREQ)
    return pd.concat(
        [
            pd.DataFrame(
                {"item_id": dt_id, "timestamp": timestamps, "target": np.round(loads[row], 4)}
            )
            for row, dt_id in enumerate(dt_ids)
        ],
        ignore_index=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="ml.export_forecast_data")
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--holdout-seed", type=int, default=9001)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"building {args.days} days of natural DT demand")
    train = build_dataset(args.days, args.seed)
    holdout = build_holdout(args.seed, args.holdout_seed, args.days)

    train_path = OUTPUT_DIR / "dt_load_train.csv"
    holdout_path = OUTPUT_DIR / "dt_load_heatwave_holdout.csv"
    train.to_csv(train_path, index=False)
    holdout.to_csv(holdout_path, index=False)

    print()
    print(f"train   {train_path}  {len(train):,} rows  {train.item_id.nunique()} series")
    print(f"holdout {holdout_path}  {len(holdout):,} rows  {holdout.item_id.nunique()} series")
    print(f"span    {train.timestamp.min()} to {train.timestamp.max()}")
    print("upload both to Kaggle as a private dataset named vidyut-dt-load")


if __name__ == "__main__":
    main()
