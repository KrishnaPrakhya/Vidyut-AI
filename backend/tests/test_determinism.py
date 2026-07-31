from __future__ import annotations

from dataclasses import asdict

import pytest

from services.sim.run import simulate
from services.sim.run import simulate_arm


def _comparable(totals) -> dict:
    data = asdict(totals)
    data.pop("spread_series")
    return data


@pytest.mark.parametrize("scenario", ["normal", "heatwave", "ev_surge"])
def test_same_seed_produces_identical_metrics(scenario: str) -> None:
    run_a = simulate(scenario, seed=42)
    run_b = simulate(scenario, seed=42)

    for arm in ("baseline", "vidyut"):
        assert _comparable(run_a.arms[arm].totals) == _comparable(run_b.arms[arm].totals)


def test_different_seeds_diverge() -> None:
    run_a = simulate("heatwave", seed=42)
    run_b = simulate("heatwave", seed=7)
    assert run_a.arms["vidyut"].totals.unserved_kwh != run_b.arms["vidyut"].totals.unserved_kwh


def test_both_arms_face_identical_demand() -> None:
    result = simulate("heatwave", seed=42, ticks=1)
    baseline = result.arms["baseline"].world
    vidyut = result.arms["vidyut"].world

    assert baseline.demand.household_ids == vidyut.demand.household_ids
    assert (baseline.demand.base_kw == vidyut.demand.base_kw).all()
    assert [d.rating_kva for d in baseline.ctx.dts.values()] == [
        d.rating_kva for d in vidyut.ctx.dts.values()
    ]


def test_baseline_outage_duration_matches_the_ledger() -> None:
    result = simulate_arm("baseline", "heatwave", 42)
    assert result.totals.homes_dark_minutes == pytest.approx(
        result.totals.minutes_by_level["disconnect"]
    )
