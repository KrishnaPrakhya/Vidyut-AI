from __future__ import annotations

from dataclasses import asdict

import pytest

from services.sim.run import simulate


def _comparable(totals) -> dict:
    data = asdict(totals)
    data.pop("spread_series")
    return data


@pytest.mark.parametrize("scenario", ["normal", "heatwave", "ev_surge"])
def test_same_seed_produces_identical_metrics(scenario: str) -> None:
    first = simulate(scenario, seed=42)
    second = simulate(scenario, seed=42)

    for arm in ("baseline", "vidyut"):
        assert _comparable(first.arms[arm].totals) == _comparable(second.arms[arm].totals)


def test_different_seeds_diverge() -> None:
    first = simulate("heatwave", seed=42)
    second = simulate("heatwave", seed=7)
    assert first.arms["vidyut"].totals.unserved_kwh != second.arms["vidyut"].totals.unserved_kwh


def test_both_arms_face_identical_demand() -> None:
    result = simulate("heatwave", seed=42, ticks=1)
    baseline = result.arms["baseline"].world
    vidyut = result.arms["vidyut"].world

    assert baseline.demand.household_ids == vidyut.demand.household_ids
    assert (baseline.demand.base_kw == vidyut.demand.base_kw).all()
    assert [d.rating_kva for d in baseline.ctx.dts.values()] == [
        d.rating_kva for d in vidyut.ctx.dts.values()
    ]
