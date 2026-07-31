from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from services.api.schemas import delta_payload, tick_payload, totals_payload
from services.sim.run import RunResult, simulate
from services.sim.scenario import N_TICKS

RECORDED_DIR = Path(__file__).resolve().parents[2] / "data" / "recorded"


def build_recording(result: RunResult) -> dict:
    ticks = len(result.arms["baseline"].snapshots)
    baseline = result.arms["baseline"].totals
    vidyut = result.arms["vidyut"].totals

    return {
        "meta": {
            "schema_version": 2,
            "scenario": result.scenario,
            "seed": result.seed,
            "ticks": ticks,
            "arms": list(result.arms.keys()),
            "params": result.params,
            "injections": [injection.to_dict() for injection in result.injections],
            "simulation_version": os.environ.get(
                "VIDYUT_SIM_VERSION", "development"
            ),
            "simulated": True,
        },
        "ticks": [
            tick_payload(
                {name: arm.snapshots[t] for name, arm in result.arms.items()}, t
            )
            for t in range(ticks)
        ],
        "summary": {
            "arms": {
                "baseline": totals_payload(baseline),
                "vidyut": totals_payload(vidyut),
            },
            "deltas": delta_payload(baseline, vidyut),
        },
        "notifications": [n.to_dict() for n in result.arms["vidyut"].outbox.pending()],
    }


def write_recording(scenario: str, seed: int, ticks: int = N_TICKS) -> Path:
    result = simulate(scenario, seed, ticks)
    recording = build_recording(result)

    RECORDED_DIR.mkdir(parents=True, exist_ok=True)
    path = RECORDED_DIR / f"{scenario}-{seed}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(recording, f, separators=(",", ":"))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(prog="services.sim.record")
    parser.add_argument("--scenario", default="heatwave")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=N_TICKS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    scenarios = ["normal", "heatwave", "ev_surge"] if args.all else [args.scenario]
    for scenario in scenarios:
        path = write_recording(scenario, args.seed, args.ticks)
        size_kb = path.stat().st_size / 1024
        print(f"wrote {path.relative_to(RECORDED_DIR.parents[1])}  ({size_kb:,.0f} kB)")


if __name__ == "__main__":
    main()
