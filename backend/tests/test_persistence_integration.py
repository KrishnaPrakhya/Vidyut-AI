from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from services.api.store import RunRecord
from services.persistence.engine import check, create_schema, session_scope
from services.persistence.models import (
    ControlAction,
    DtTickReading,
    FairnessLedger,
    FairnessLedgerHistory,
    Household,
    HouseholdImpact,
    Notification,
    Run,
    RunArmTotal,
    TickMetric,
    TopologyChange,
)
from services.persistence.queries import (
    fairness_leaderboard_rows,
    household_history,
    household_profile,
)
from services.persistence.repository import delete_run, load_fairness_balances, save_run
from services.sim.run import simulate

TICKS = 52
CREATED_RUN_IDS: list[str] = []

pytestmark = pytest.mark.skipif(
    not check().reachable, reason="no reachable DATABASE_URL; integration tests skipped"
)


@pytest.fixture(scope="module", autouse=True)
def schema():
    create_schema()
    yield
    with session_scope() as session:
        for run_id in reversed(CREATED_RUN_IDS):
            delete_run(session, run_id)


def _persist_run(ticks: int = TICKS) -> str:
    run_id = uuid.uuid4().hex[:12]
    record = RunRecord(
        run_id=run_id, scenario="heatwave", seed=42, ticks=ticks, params={}, status="ready"
    )
    with session_scope() as session:
        opening_debt = load_fairness_balances(session)
    record.result = simulate("heatwave", 42, ticks, opening_debt=opening_debt)
    with session_scope() as session:
        save_run(session, record, record.result)
    CREATED_RUN_IDS.append(run_id)
    return run_id


def _count(session, model, run_id: str) -> int:
    return session.execute(
        select(func.count()).select_from(model).where(model.run_id == run_id)
    ).scalar_one()


def test_a_run_writes_every_table_of_the_audit_spine() -> None:
    run_id = _persist_run()
    with session_scope() as session:
        assert session.get(Run, run_id) is not None
        assert _count(session, RunArmTotal, run_id) == 2
        assert _count(session, TickMetric, run_id) == TICKS * 2
        assert _count(session, DtTickReading, run_id) == TICKS * 60 * 2
        assert _count(session, ControlAction, run_id) > 0
        assert _count(session, HouseholdImpact, run_id) > 0
        assert _count(session, Notification, run_id) > 0
        assert _count(session, TopologyChange, run_id) > 0
        household_ids = {
            value
            for value in session.execute(
                select(HouseholdImpact.household_id).where(
                    HouseholdImpact.run_id == run_id
                )
            ).scalars()
        }
        prefix = next(iter(household_ids)).split("-", 1)[0]
        assert (
            session.execute(
                select(func.count())
                .select_from(Household)
                .where(Household.id.like(f"{prefix}-%"))
            ).scalar_one()
            == 4200
        )


def test_every_impact_carries_a_reason_and_a_standing() -> None:
    run_id = _persist_run()
    with session_scope() as session:
        impacts = (
            session.execute(select(HouseholdImpact).where(HouseholdImpact.run_id == run_id))
            .scalars()
            .all()
        )
        assert impacts
        for impact in impacts:
            assert impact.reason_code
            assert impact.standing_percentile is not None
            assert 0.0 <= float(impact.standing_percentile) <= 100.0
            assert float(impact.debt_charged) == pytest.approx(
                float(impact.minutes) * float(impact.debt_weight)
            )


def test_standing_is_measured_at_decision_time_not_at_end_of_run() -> None:
    run_id = _persist_run()
    with session_scope() as session:
        impacts = (
            session.execute(
                select(HouseholdImpact)
                .where(
                    HouseholdImpact.run_id == run_id,
                    HouseholdImpact.arm == "vidyut",
                )
                .order_by(HouseholdImpact.tick, HouseholdImpact.id)
            )
            .scalars()
            .all()
        )
        running_debt = load_fairness_balances(session, exclude_run_id=run_id)
        prefix = impacts[0].household_id.split("-", 1)[0]
        members: dict[str, list[str]] = {}
        for household_id, dt_id in session.execute(
            select(Household.id, Household.dt_id).where(
                Household.id.like(f"{prefix}-%")
            )
        ):
            members.setdefault(dt_id, []).append(household_id)

    for impact in impacts:
        debt = running_debt.get(impact.household_id, 0.0)
        neighbours = members[impact.dt_id]
        expected = round(
            100.0
            * sum(1 for member in neighbours if running_debt.get(member, 0.0) < debt)
            / len(neighbours),
            3,
        )
        assert float(impact.standing_percentile) == pytest.approx(expected)
        running_debt[impact.household_id] = debt + float(impact.debt_charged)


def test_critical_tier_is_never_recorded_as_disconnected() -> None:
    run_id = _persist_run()
    with session_scope() as session:
        rows = session.execute(
            select(Household.tier)
            .join(HouseholdImpact, HouseholdImpact.household_id == Household.id)
            .where(
                HouseholdImpact.run_id == run_id,
                HouseholdImpact.level.in_(("disconnect", "load_limit")),
            )
        ).scalars()
        assert "critical" not in set(rows)


def test_fairness_debt_accumulates_across_runs() -> None:
    _persist_run()
    with session_scope() as session:
        after_first = load_fairness_balances(session)
        total_first = sum(after_first.values())

    run_b = _persist_run()
    with session_scope() as session:
        after_second = load_fairness_balances(session)
        assert sum(after_second.values()) > total_first

        histories = (
            session.execute(
                select(FairnessLedgerHistory)
                .where(FairnessLedgerHistory.run_id == run_b)
                .order_by(FairnessLedgerHistory.id)
            )
            .scalars()
            .all()
        )
        assert histories
        for history in histories:
            assert float(history.debt_before) == pytest.approx(
                after_first.get(history.household_id, 0.0)
            )
            ledger = session.get(FairnessLedger, history.household_id)
            assert float(ledger.cumulative_debt_min) == pytest.approx(
                float(history.debt_after)
            )


def test_household_profile_and_history_are_queryable() -> None:
    _persist_run()
    with session_scope() as session:
        balances = load_fairness_balances(session)
        household_id = max(balances, key=balances.get)

        profile = household_profile(session, household_id)
        assert profile["household_id"] == household_id
        assert profile["tier"] in ("standard", "essential", "critical")
        assert set(profile["addressability"]) == {
            "ami",
            "meter_load_limit_supported",
            "has_connected_device",
            "addressable",
        }
        assert profile["ledger"]["cumulative_debt_min"] > 0
        assert 0.0 <= profile["ledger"]["standing_percentile_on_dt"] <= 100.0

        history = household_history(session, household_id, limit=5)
        assert history["total"] > 0
        assert history["events"]
        for event in history["events"]:
            assert event["reason_code"]
            assert event["explanation"]
            assert event["explanation"].startswith("At ")

        assert household_profile(session, "does-not-exist") is None


def test_leaderboard_orders_by_accumulated_debt() -> None:
    _persist_run()
    with session_scope() as session:
        rows = fairness_leaderboard_rows(session, limit=10)
        assert rows
        debts = [row["cumulative_debt_min"] for row in rows]
        assert debts == sorted(debts, reverse=True)


def test_reruns_replace_rather_than_duplicate() -> None:
    run_id = _persist_run()
    with session_scope() as session:
        before = _count(session, DtTickReading, run_id)
        debt_before = sum(load_fairness_balances(session).values())

    record = RunRecord(
        run_id=run_id, scenario="heatwave", seed=42, ticks=TICKS, params={}, status="ready"
    )
    record.result = simulate("heatwave", 42, TICKS)
    with session_scope() as session:
        save_run(session, record, record.result)
        assert _count(session, DtTickReading, run_id) == before
        assert sum(load_fairness_balances(session).values()) == pytest.approx(debt_before)
