from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.persistence.models import (
    ControlAction,
    Device,
    FairnessLedger,
    Household,
    HouseholdImpact,
    Run,
)
from services.timebase import clock_of

LEVEL_SENTENCE = {
    "price_signal": "a peak tariff was broadcast to your area; no action was required of you",
    "device": "a connected appliance was briefly curtailed",
    "load_limit": "a temporary load ceiling was applied to your supply",
    "disconnect": "your supply was interrupted as a last resort",
}


def household_profile(session: Session, household_id: str) -> dict | None:
    household = session.get(Household, household_id)
    if household is None:
        return None

    devices = (
        session.execute(select(Device).where(Device.household_id == household_id))
        .scalars()
        .all()
    )
    ledger = session.get(FairnessLedger, household_id)

    peers = session.execute(
        select(func.count(), func.coalesce(func.avg(FairnessLedger.cumulative_debt_min), 0.0))
        .where(FairnessLedger.dt_id == household.dt_id)
    ).one()

    standing = None
    if ledger is not None:
        ranked = session.execute(
            select(func.count()).where(
                FairnessLedger.dt_id == household.dt_id,
                FairnessLedger.cumulative_debt_min < ledger.cumulative_debt_min,
            )
        ).scalar_one()
        standing = round(100.0 * ranked / max(peers[0], 1), 1)

    return {
        "household_id": household.id,
        "dt_id": household.dt_id,
        "tier": household.tier,
        "addressability": {
            "ami": household.ami,
            "meter_load_limit_supported": household.meter_load_limit_supported,
            "has_connected_device": household.has_connected_device,
            "addressable": household.addressable,
        },
        "devices": [
            {
                "kind": device.kind,
                "rated_kw": float(device.rated_kw),
                "controllable": device.controllable,
            }
            for device in devices
        ],
        "ledger": {
            "cumulative_debt_min": float(ledger.cumulative_debt_min) if ledger else 0.0,
            "minutes_by_level": (ledger.minutes_by_level or {}) if ledger else {},
            "first_curtailed_at": (
                ledger.first_curtailed_at.isoformat() if ledger and ledger.first_curtailed_at else None
            ),
            "last_curtailed_at": (
                ledger.last_curtailed_at.isoformat() if ledger and ledger.last_curtailed_at else None
            ),
            "standing_percentile_on_dt": standing,
            "dt_peer_count": peers[0],
            "dt_average_debt_min": round(float(peers[1]), 1),
        },
    }


def household_history(
    session: Session, household_id: str, limit: int = 200, offset: int = 0
) -> dict:
    total = session.execute(
        select(func.count()).where(HouseholdImpact.household_id == household_id)
    ).scalar_one()

    rows = session.execute(
        select(HouseholdImpact, ControlAction, Run)
        .outerjoin(ControlAction, ControlAction.id == HouseholdImpact.action_id)
        .join(Run, Run.run_id == HouseholdImpact.run_id)
        .where(HouseholdImpact.household_id == household_id)
        .order_by(Run.created_at.desc(), HouseholdImpact.tick.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    events = []
    for impact, action, run in rows:
        minutes = float(impact.minutes)
        clock = clock_of(impact.tick)
        events.append(
            {
                "run_id": impact.run_id,
                "scenario": run.scenario,
                "arm": impact.arm,
                "tick": impact.tick,
                "clock": clock,
                "level": impact.level,
                "minutes": minutes,
                "kw_reduction": float(impact.kw_reduction),
                "debt_weight": float(impact.debt_weight),
                "debt_charged": float(impact.debt_charged),
                "standing_percentile_at_decision": (
                    float(impact.standing_percentile)
                    if impact.standing_percentile is not None
                    else None
                ),
                "reason_code": impact.reason_code,
                "detail": action.detail if action else None,
                "forecast_kw": float(action.forecast_kw) if action and action.forecast_kw else None,
                "safe_limit_kw": (
                    float(action.safe_limit_kw) if action and action.safe_limit_kw else None
                ),
                "explanation": explain(impact, action, clock),
            }
        )

    return {"total": total, "offset": offset, "limit": limit, "events": events}


def fairness_leaderboard_rows(
    session: Session, dt_id: str | None = None, limit: int = 25
) -> list[dict]:
    statement = select(FairnessLedger).order_by(FairnessLedger.cumulative_debt_min.desc())
    if dt_id is not None:
        statement = statement.where(FairnessLedger.dt_id == dt_id)

    return [
        {
            "household_id": row.household_id,
            "dt_id": row.dt_id,
            "cumulative_debt_min": float(row.cumulative_debt_min),
            "minutes_by_level": row.minutes_by_level or {},
            "last_curtailed_at": (
                row.last_curtailed_at.isoformat() if row.last_curtailed_at else None
            ),
        }
        for row in session.execute(statement.limit(limit)).scalars().all()
    ]


def explain(impact, action, clock: str) -> str:
    sentence = LEVEL_SENTENCE.get(impact.level, "your supply was adjusted")
    standing = impact.standing_percentile
    where = ""
    if standing is not None:
        percentile = float(standing)
        if percentile <= 25.0:
            where = (
                " You had borne less curtailment than most homes on your transformer, "
                "which is why you were selected this time."
            )
        elif percentile >= 75.0:
            where = (
                " You had already borne more than most homes on your transformer, so you were "
                "near the back of the queue."
            )
        else:
            where = " Your accumulated share was around the middle for your transformer."

    reason = ""
    if action is not None and action.forecast_kw and action.safe_limit_kw:
        reason = (
            f" Transformer {impact.dt_id} was forecast to reach "
            f"{float(action.forecast_kw):.0f} kW against a safe limit of "
            f"{float(action.safe_limit_kw):.0f} kW."
        )

    return (
        f"At {clock}, {sentence} for {float(impact.minutes):.0f} minutes.{reason}{where}"
    ).strip()
