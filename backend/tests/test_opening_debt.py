from __future__ import annotations

import pytest

from services.sim.ledger import FairnessLedger
from services.sim.run import simulate_arm
from services.sim.world import build_world

TICKS = 52
ROTATION_TICKS = 84


def test_ledger_separates_prior_debt_from_this_run() -> None:
    ledger = FairnessLedger(opening_debt={"H1": 400.0})
    ledger.charge(
        tick=0, household_id="H1", dt_id="DT", level="device", kw=1.0, minutes=30.0,
        reason_code="TEST",
    )

    assert ledger.accrued_of("H1") == 30.0
    assert ledger.debt_of("H1") == 430.0
    assert ledger.accrued_of("H2") == 0.0
    assert ledger.debt_of("H2") == 0.0


def test_normalised_debt_ranks_against_standing_not_accrual() -> None:
    ledger = FairnessLedger(opening_debt={"heavy": 1000.0, "light": 0.0})
    ledger.charge(
        tick=0, household_id="light", dt_id="DT", level="device", kw=1.0, minutes=30.0,
        reason_code="TEST",
    )

    assert ledger.normalised_debt("heavy") == pytest.approx(1.0)
    assert ledger.normalised_debt("light") < 0.1


def test_opening_debt_is_filtered_to_known_households() -> None:
    clean = build_world("vidyut", "heatwave", 42)
    household_id = next(iter(clean.households))
    world = build_world(
        "vidyut",
        "heatwave",
        42,
        None,
        {"ghost-household": 900.0, household_id: 120.0},
    )
    assert "ghost-household" not in world.ledger.opening_debt
    assert world.ledger.opening_debt[household_id] == 120.0


def test_household_identity_changes_with_population_seed() -> None:
    seed_42 = build_world("vidyut", "heatwave", 42)
    seed_7 = build_world("vidyut", "heatwave", 7)
    assert set(seed_42.households).isdisjoint(seed_7.households)


def test_metrics_report_this_run_only_not_carried_debt() -> None:
    clean = simulate_arm("vidyut", "heatwave", 42, TICKS)
    burdened_ids = list(clean.world.ledger.debt_min)[:200]
    opening = {household_id: 5000.0 for household_id in burdened_ids}

    carried = simulate_arm("vidyut", "heatwave", 42, TICKS, opening_debt=opening)

    assert carried.totals.max_household_burden_min < 5000.0
    assert carried.world.ledger.debt_of(burdened_ids[0]) >= 5000.0


def test_carried_debt_changes_who_is_selected() -> None:
    clean = simulate_arm("vidyut", "heatwave", 42, ROTATION_TICKS)
    disconnected = sorted(
        {r.household_id for r in clean.world.ledger.records if r.level == "disconnect"}
    )
    assert disconnected, "no disconnections in the window; tier 3 starts around tick 71"

    opening = {household_id: 4000.0 for household_id in disconnected}
    carried = simulate_arm("vidyut", "heatwave", 42, ROTATION_TICKS, opening_debt=opening)
    carried_disconnected = {
        r.household_id for r in carried.world.ledger.records if r.level == "disconnect"
    }

    repeated = carried_disconnected & set(disconnected)
    assert len(repeated) < len(disconnected), (
        "carrying debt did not change the rotation; the ledger is not influencing selection"
    )


def test_critical_tier_stays_protected_under_carried_debt() -> None:
    world = simulate_arm("vidyut", "heatwave", 42, TICKS).world
    opening = {household_id: 9000.0 for household_id in world.households}

    carried = simulate_arm("vidyut", "heatwave", 42, TICKS, opening_debt=opening).world
    for record in carried.ledger.records:
        if record.level in ("disconnect", "load_limit"):
            assert carried.households[record.household_id].tier != "critical"
    assert carried.critical_household_dark_minutes == 0.0
