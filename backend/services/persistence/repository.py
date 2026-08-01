from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from services.persistence.models import (
    ControlAction,
    Device,
    DistributionTransformerRow,
    DtTickReading,
    FairnessLedger,
    FairnessLedgerHistory,
    Feeder,
    FeederTickReading,
    Household,
    HouseholdImpact,
    Notification,
    NotificationDelivery,
    Run,
    RunArmTotal,
    RunInjection,
    TickMetric,
    TopologyChange,
)
from services.sim.ledger import DEBT_WEIGHT
from services.timebase import clock_of

CHUNK = 2000


def _bulk(session: Session, model, rows: list[dict]) -> None:
    for start in range(0, len(rows), CHUNK):
        session.execute(insert(model), rows[start : start + CHUNK])


def load_fairness_balances(
    session: Session | None, exclude_run_id: str | None = None
) -> dict[str, float]:
    if session is None:
        return {}
    rows = session.execute(
        select(FairnessLedger.household_id, FairnessLedger.cumulative_debt_min)
    ).all()
    balances = {household_id: float(debt) for household_id, debt in rows}
    if exclude_run_id is None:
        return balances
    prior = session.execute(
        select(
            FairnessLedgerHistory.household_id,
            FairnessLedgerHistory.debt_delta,
        ).where(FairnessLedgerHistory.run_id == exclude_run_id)
    ).all()
    for household_id, delta in prior:
        balances[household_id] = max(
            balances.get(household_id, 0.0) - float(delta), 0.0
        )
    return {household_id: debt for household_id, debt in balances.items() if debt > 0.0}


def sync_network_master(session: Session, world) -> None:
    feeders = [
        {"id": feeder_id, "substation": "SUB", "nominal_kv": 11.0}
        for feeder_id in world.ctx.dt_ids_of_feeder
    ]
    session.execute(
        pg_insert(Feeder).values(feeders).on_conflict_do_nothing(index_elements=["id"])
    )

    transformers = [
        {"id": dt.id, "feeder_id": dt.feeder_id, "rating_kva": float(dt.rating_kva)}
        for dt in world.ctx.dts.values()
    ]
    transformer_insert = pg_insert(DistributionTransformerRow)
    session.execute(
        transformer_insert.values(transformers).on_conflict_do_update(
            index_elements=["id"],
            set_={"rating_kva": transformer_insert.excluded.rating_kva},
        )
    )

    households = [
        {
            "id": household.id,
            "dt_id": household.dt_id,
            "tier": household.tier,
            "ami": household.ami,
            "meter_load_limit_supported": household.meter_load_limit_supported,
            "has_connected_device": household.has_connected_device,
            "addressable": household.addressable,
        }
        for household in world.households.values()
    ]
    household_insert = pg_insert(Household)
    for start in range(0, len(households), CHUNK):
        session.execute(
            household_insert
            .values(households[start : start + CHUNK])
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "dt_id": household_insert.excluded.dt_id,
                    "tier": household_insert.excluded.tier,
                    "ami": household_insert.excluded.ami,
                    "meter_load_limit_supported": (
                        household_insert.excluded.meter_load_limit_supported
                    ),
                    "has_connected_device": household_insert.excluded.has_connected_device,
                    "addressable": household_insert.excluded.addressable,
                },
            )
        )

    household_ids = list(world.households)
    session.execute(delete(Device).where(Device.household_id.in_(household_ids)))
    devices = [
        {
            "household_id": household.id,
            "kind": device.kind,
            "rated_kw": float(device.rated_kw),
            "controllable": device.controllable,
            "deferrable_window_min": device.deferrable_window_min,
            "comfort_cost_per_min": float(device.comfort_cost_per_min),
        }
        for household in world.households.values()
        for device in household.devices
    ]
    _bulk(session, Device, devices)


def save_run(session: Session, record, result) -> None:
    run_id = record.run_id
    _rollback_fairness_ledger(session, run_id)
    session.execute(delete(Run).where(Run.run_id == run_id))
    session.flush()

    session.add(
        Run(
            run_id=run_id,
            scenario=record.scenario,
            seed=record.seed,
            ticks=record.ticks,
            params=record.params or {},
            status="ready",
            error=record.error,
            sim_version=os.environ.get("VIDYUT_SIM_VERSION", "development"),
            completed_at=datetime.now(timezone.utc),
        )
    )
    session.flush()

    if record.injections:
        _bulk(
            session,
            RunInjection,
            [
                {"run_id": run_id, "sequence": i, **injection.to_dict()}
                for i, injection in enumerate(record.injections)
            ],
        )

    sync_network_master(session, result.arms["vidyut"].world)

    for arm, arm_result in result.arms.items():
        _save_arm(session, run_id, arm, arm_result)

    _save_notifications(session, run_id, result.arms["vidyut"])
    _update_fairness_ledger(session, run_id, result.arms["vidyut"])


def delete_run(session: Session, run_id: str) -> None:
    _rollback_fairness_ledger(session, run_id)
    session.execute(delete(Run).where(Run.run_id == run_id))


def _save_arm(session: Session, run_id: str, arm: str, arm_result) -> None:
    totals = asdict(arm_result.totals)
    totals.pop("spread_series", None)
    totals.pop("arm", None)
    totals["events_by_tier"] = {str(k): v for k, v in totals["events_by_tier"].items()}
    session.add(RunArmTotal(run_id=run_id, arm=arm, **totals))

    tick_rows, dt_rows, feeder_rows, action_rows = [], [], [], []
    for tick, snapshot in enumerate(arm_result.snapshots):
        metrics = asdict(snapshot.metrics)
        tick_rows.append({"run_id": run_id, "arm": arm, "tick": tick, **metrics})

        for dt in snapshot.dts:
            row = asdict(dt)
            row["dt_id"] = row.pop("id")
            dt_rows.append({"run_id": run_id, "arm": arm, "tick": tick, **row})
        for feeder in snapshot.feeders:
            row = asdict(feeder)
            row["feeder_id"] = row.pop("id")
            feeder_rows.append({"run_id": run_id, "arm": arm, "tick": tick, **row})

        for event in snapshot.events:
            action_rows.append(
                {
                    "run_id": run_id,
                    "arm": arm,
                    "tick": tick,
                    "clock": clock_of(tick),
                    **asdict(event),
                }
            )

    _bulk(session, TickMetric, tick_rows)
    _bulk(session, DtTickReading, dt_rows)
    _bulk(session, FeederTickReading, feeder_rows)
    _bulk(
        session,
        TopologyChange,
        [
            {"run_id": run_id, "arm": arm, **asdict(change)}
            for change in arm_result.world.topology_changes
        ],
    )

    action_ids: dict[tuple[int, str, str], int] = {}
    for row in action_rows:
        action = ControlAction(**row)
        session.add(action)
        session.flush()
        action_ids[(row["tick"], row["target"], row["reason_code"])] = action.id

    _save_impacts(session, run_id, arm, arm_result, action_ids)


def _save_impacts(
    session: Session, run_id: str, arm: str, arm_result, action_ids: dict
) -> None:
    world = arm_result.world
    ledger = world.ledger

    members_of_dt: dict[str, list[str]] = {}
    for household_id, household in world.households.items():
        members_of_dt.setdefault(household.dt_id, []).append(household_id)

    running_debt: dict[str, float] = dict(ledger.opening_debt)

    rows = []
    for record in sorted(ledger.records, key=lambda r: r.tick):
        weight = DEBT_WEIGHT.get(record.level, 1.0)
        debt_at_decision = running_debt.get(record.household_id, 0.0)
        neighbours = members_of_dt.get(record.dt_id, [])
        percentile = (
            100.0
            * sum(1 for other in neighbours if running_debt.get(other, 0.0) < debt_at_decision)
            / max(len(neighbours), 1)
        )
        running_debt[record.household_id] = debt_at_decision + float(record.minutes) * weight
        rows.append(
            {
                "action_id": action_ids.get(
                    (record.tick, record.dt_id, record.reason_code)
                ),
                "run_id": run_id,
                "arm": arm,
                "tick": record.tick,
                "household_id": record.household_id,
                "dt_id": record.dt_id,
                "level": record.level,
                "device_kind": record.device_kind,
                "kw_reduction": float(record.kw),
                "minutes": float(record.minutes),
                "debt_weight": weight,
                "debt_charged": float(record.minutes) * weight,
                "standing_percentile": round(percentile, 3),
                "reason_code": record.reason_code,
            }
        )
    _bulk(session, HouseholdImpact, rows)


def _save_notifications(session: Session, run_id: str, arm_result) -> None:
    notifications = arm_result.outbox.pending()
    if not notifications:
        return
    _bulk(
        session,
        Notification,
        [{"run_id": run_id, **notification.to_dict()} for notification in notifications],
    )


def pending_notification_ids(session: Session, run_id: str) -> list[int]:
    latest_delivery = (
        select(
            NotificationDelivery.notification_id,
            func.max(NotificationDelivery.id).label("delivery_id"),
        )
        .group_by(NotificationDelivery.notification_id)
        .subquery()
    )
    return list(
        session.execute(
            select(Notification.id)
            .outerjoin(
                latest_delivery,
                latest_delivery.c.notification_id == Notification.id,
            )
            .outerjoin(
                NotificationDelivery,
                NotificationDelivery.id == latest_delivery.c.delivery_id,
            )
            .where(
                Notification.run_id == run_id,
                or_(
                    latest_delivery.c.delivery_id.is_(None),
                    NotificationDelivery.status == "failed",
                ),
            )
            .order_by(Notification.id)
        ).scalars()
    )


def record_notification_dispatch(
    session: Session, notification_ids: list[int], provider: str = "n8n"
) -> None:
    now = datetime.now(timezone.utc)
    _bulk(
        session,
        NotificationDelivery,
        [
            {
                "notification_id": notification_id,
                "provider": provider,
                "status": "dispatched",
                "dispatched_at": now,
            }
            for notification_id in notification_ids
        ],
    )


def update_notification_delivery(
    session: Session,
    notification_id: int,
    status: str,
    provider_message_id: str | None,
    error: str | None,
) -> NotificationDelivery | None:
    delivery = session.execute(
        select(NotificationDelivery)
        .where(NotificationDelivery.notification_id == notification_id)
        .order_by(NotificationDelivery.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if delivery is None:
        if session.get(Notification, notification_id) is None:
            return None
        delivery = NotificationDelivery(
            notification_id=notification_id,
            provider="n8n",
            status=status,
        )
        session.add(delivery)
    transitions = {
        "queued": {"queued", "dispatched", "failed"},
        "dispatched": {"dispatched", "delivered", "failed"},
        "failed": {"dispatched", "failed"},
        "delivered": {"delivered"},
    }
    if status not in transitions.get(delivery.status, {status}):
        raise ValueError(
            f"delivery status cannot change from {delivery.status} to {status}"
        )
    delivery.status = status
    delivery.provider_message_id = provider_message_id
    delivery.error = error
    if status == "delivered":
        delivery.delivered_at = datetime.now(timezone.utc)
    return delivery


def notification_ids_for_run(session: Session, run_id: str) -> set[int]:
    return set(
        session.execute(
            select(Notification.id).where(Notification.run_id == run_id)
        ).scalars()
    )


def notification_delivery_summary(session: Session, run_id: str) -> dict:
    all_deliveries = list(
        session.execute(
            select(NotificationDelivery)
            .join(Notification, Notification.id == NotificationDelivery.notification_id)
            .where(Notification.run_id == run_id)
            .order_by(NotificationDelivery.id)
        ).scalars()
    )
    latest_by_notification: dict[int, NotificationDelivery] = {}
    for delivery in all_deliveries:
        latest_by_notification[delivery.notification_id] = delivery
    deliveries = list(latest_by_notification.values())
    counts: dict[str, int] = {}
    for delivery in deliveries:
        counts[delivery.status] = counts.get(delivery.status, 0) + 1
    if not deliveries:
        status = "not_dispatched"
    elif counts.get("failed"):
        status = "failed"
    elif counts.get("delivered") == len(deliveries):
        status = "delivered"
    else:
        status = "dispatched"
    delivered_at = max(
        (row.delivered_at for row in deliveries if row.delivered_at is not None),
        default=None,
    )
    provider_message_id = next(
        (
            row.provider_message_id
            for row in reversed(deliveries)
            if row.provider_message_id
        ),
        None,
    )
    error = next(
        (row.error for row in reversed(deliveries) if row.error),
        None,
    )
    return {
        "status": status,
        "total": len(deliveries),
        "counts": counts,
        "delivered_at": delivered_at.isoformat() if delivered_at else None,
        "provider_message_id": provider_message_id,
        "error": error,
    }


def _update_fairness_ledger(session: Session, run_id: str, arm_result) -> None:
    ledger = arm_result.world.ledger
    if not ledger.debt_min:
        return

    now = datetime.now(timezone.utc)
    household_ids = list(ledger.debt_min.keys())
    existing = {
        row.household_id: row
        for row in session.execute(
            select(FairnessLedger).where(FairnessLedger.household_id.in_(household_ids))
        )
        .scalars()
        .all()
    }

    minutes_by_household: dict[str, dict[str, float]] = {}
    events_by_household: dict[str, int] = {}
    for record in ledger.records:
        bucket = minutes_by_household.setdefault(record.household_id, {})
        bucket[record.level] = bucket.get(record.level, 0.0) + float(record.minutes)
        events_by_household[record.household_id] = (
            events_by_household.get(record.household_id, 0) + 1
        )

    history = []
    for household_id, delta in ledger.debt_min.items():
        row = existing.get(household_id)
        before = float(row.cumulative_debt_min) if row else 0.0
        after = before + float(delta)

        levels = minutes_by_household.get(household_id, {})
        if row is None:
            session.add(
                FairnessLedger(
                    household_id=household_id,
                    dt_id=arm_result.world.households[household_id].dt_id,
                    cumulative_debt_min=after,
                    events_count=events_by_household.get(household_id, 0),
                    minutes_by_level=levels,
                    first_curtailed_at=now,
                    last_curtailed_at=now,
                )
            )
        else:
            merged = dict(row.minutes_by_level or {})
            for level, minutes in levels.items():
                merged[level] = merged.get(level, 0.0) + minutes
            row.cumulative_debt_min = after
            row.events_count = (row.events_count or 0) + events_by_household.get(
                household_id, 0
            )
            row.minutes_by_level = merged
            row.last_curtailed_at = now

        history.append(
            {
                "household_id": household_id,
                "run_id": run_id,
                "debt_before": before,
                "debt_delta": float(delta),
                "debt_after": after,
            }
        )

    _bulk(session, FairnessLedgerHistory, history)


def _rollback_fairness_ledger(session: Session, run_id: str) -> None:
    history = (
        session.execute(
            select(FairnessLedgerHistory).where(
                FairnessLedgerHistory.run_id == run_id
            )
        )
        .scalars()
        .all()
    )
    if not history:
        return

    impacts = (
        session.execute(
            select(HouseholdImpact).where(
                HouseholdImpact.run_id == run_id,
                HouseholdImpact.arm == "vidyut",
            )
        )
        .scalars()
        .all()
    )
    minutes: dict[str, dict[str, float]] = {}
    counts: dict[str, int] = {}
    for impact in impacts:
        levels = minutes.setdefault(impact.household_id, {})
        levels[impact.level] = levels.get(impact.level, 0.0) + float(impact.minutes)
        counts[impact.household_id] = counts.get(impact.household_id, 0) + 1

    for entry in history:
        row = session.get(FairnessLedger, entry.household_id)
        if row is None:
            continue
        remaining = max(
            float(row.cumulative_debt_min) - float(entry.debt_delta), 0.0
        )
        if remaining <= 1e-9:
            session.delete(row)
            continue
        by_level = dict(row.minutes_by_level or {})
        for level, value in minutes.get(entry.household_id, {}).items():
            updated = max(float(by_level.get(level, 0.0)) - value, 0.0)
            if updated <= 1e-9:
                by_level.pop(level, None)
            else:
                by_level[level] = updated
        row.cumulative_debt_min = remaining
        row.events_count = max(
            int(row.events_count or 0) - counts.get(entry.household_id, 0), 0
        )
        row.minutes_by_level = by_level
    session.flush()
