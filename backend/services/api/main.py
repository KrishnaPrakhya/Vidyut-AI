from __future__ import annotations

import asyncio
import math
import os
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from services.api.models_registry import read_artifacts
from services.api.report import build_report_pdf
from services.api.schemas import (
    CreateRunRequest,
    CreateRunResponse,
    DeliveryReceiptRequest,
    EventVerificationRequest,
    FlexibilityEstimateRequest,
    InjectRequest,
    delta_payload,
    tick_payload,
    totals_payload,
)
from services.api.store import store
from services.dispatch.n8n import dispatch
from services.observability import (
    engine_status,
    estimate_weather_opportunity,
    registered_availability_profile,
    registered_envelope,
    verify_event,
)
from services.persistence.engine import check as db_check
from services.persistence.engine import create_schema, session_scope
from services.persistence.queries import (
    fairness_leaderboard_rows,
    household_history,
    household_profile,
)
from services.persistence.repository import (
    pending_notification_ids,
    record_notification_dispatch,
    update_notification_delivery,
)
from services.sim.injection import Injection
from services.sim.scenario import available_scenarios
from services.timebase import TICK_HOURS

DEFAULT_PLAYBACK_TICKS_PER_SECOND = 4.0

@asynccontextmanager
async def lifespan(_: FastAPI):
    status = create_schema()
    if status.configured and not status.reachable:
        print(f"database configured but unreachable, continuing in memory: {status.error}")
    yield


app = FastAPI(title="Vidyut", version="0.1.0", lifespan=lifespan)
cors_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "scenarios": available_scenarios(),
        "database": db_check().to_dict(),
    }


@app.get("/api/scenarios")
def scenarios() -> dict:
    return {"scenarios": available_scenarios()}


@app.get("/api/observability/status")
def observability_status() -> dict:
    return engine_status()


@app.post("/api/observability/flexibility/estimate")
def estimate_flexibility(request: FlexibilityEstimateRequest) -> dict:
    try:
        result = estimate_weather_opportunity(
            request.aggregate_kw,
            request.ambient_c,
            request.registered_capacity_kw,
            request.setpoint_c,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.to_dict()


@app.post("/api/observability/events/verify")
def verify_flexibility_event(request: EventVerificationRequest) -> dict:
    try:
        result = verify_event(
            request.history_kw,
            request.observed_kw,
            request.event_start_index,
            request.event_end_index,
            request.committed_reduction_kw,
            request.method,
            request.adjustment_intervals,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.to_dict()


@app.post("/api/runs", response_model=CreateRunResponse)
def create_run(request: CreateRunRequest) -> CreateRunResponse:
    if request.scenario not in available_scenarios():
        raise HTTPException(status_code=404, detail=f"unknown scenario {request.scenario!r}")
    record = store.create(
        scenario=request.scenario,
        seed=request.seed,
        ticks=request.ticks,
        params=request.params.overrides(),
        carry_debt=request.carry_debt,
    )
    return CreateRunResponse(run_id=record.run_id, status=record.status)


@app.get("/api/runs")
def list_runs() -> dict:
    return {"runs": store.list_runs()}


def _require_record(run_id: str):
    record = store.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record


@app.get("/api/runs/{run_id}")
def run_status(run_id: str) -> dict:
    return _require_record(run_id).summary_stub()


@app.get("/api/runs/{run_id}/summary")
def run_summary(run_id: str) -> dict:
    record = _require_record(run_id)
    if record.status == "failed":
        raise HTTPException(status_code=500, detail=record.error or "simulation failed")
    if record.result is None:
        return {**record.summary_stub(), "ready": False}

    baseline = record.result.arms["baseline"].totals
    vidyut = record.result.arms["vidyut"].totals
    return {
        **record.summary_stub(),
        "ready": True,
        "arms": {"baseline": totals_payload(baseline), "vidyut": totals_payload(vidyut)},
        "deltas": delta_payload(baseline, vidyut),
    }


@app.get("/api/runs/{run_id}/flexibility")
def run_flexibility(run_id: str) -> dict:
    record = _require_record(run_id)
    if record.result is None:
        raise HTTPException(status_code=409, detail="run is not ready")
    arm = record.result.arms["vidyut"]
    envelope = registered_envelope(arm.world.households.values())
    availability = registered_availability_profile(arm.world, len(arm.snapshots))
    return {
        "run_id": run_id,
        "registered": envelope.to_dict(),
        "available": {
            "profile_kw": availability,
            "peak_kw": round(max(availability, default=0.0), 3),
            "energy_kwh": round(sum(availability) * TICK_HOURS, 3),
            "source": "registered_schedule",
            "method": "active_controllable_load",
        },
        "realised": {
            "reduction_kwh": round(arm.world.flexibility_kwh, 3),
            "source": "simulation_measurement",
            "method": "natural_minus_controlled_load",
        },
    }


@app.post("/api/runs/{run_id}/inject")
def inject(run_id: str, request: InjectRequest) -> dict:
    record = _require_record(run_id)
    if record.status != "ready" or record.result is None:
        raise HTTPException(status_code=409, detail="run must be ready before injection")
    if request.dt_id is not None:
        dt_ids = set(record.result.arms["vidyut"].world.dt_ids)
        if request.dt_id not in dt_ids:
            raise HTTPException(status_code=422, detail="unknown distribution transformer")
    from_tick = request.from_tick if request.from_tick is not None else 0
    if from_tick >= record.ticks:
        raise HTTPException(
            status_code=422,
            detail="injection tick must be inside the run",
        )
    injection = Injection(
        type=request.type,
        magnitude=request.magnitude,
        from_tick=from_tick,
        dt_id=request.dt_id,
    )
    updated = store.inject(run_id, injection)
    if updated is None:
        raise HTTPException(status_code=409, detail="run is no longer ready")
    return {
        "run_id": run_id,
        "status": updated.status,
        "injections": [i.to_dict() for i in updated.injections],
        "resimulating_from_tick": from_tick,
    }


@app.get("/api/runs/{run_id}/events")
def run_events(
    run_id: str,
    arm: str = Query(default="vidyut"),
    tier: int | None = Query(default=None),
    dt_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    record = _require_record(run_id)
    if record.result is None:
        return {"run_id": run_id, "ready": False, "events": [], "total": 0}
    if arm not in record.result.arms:
        raise HTTPException(status_code=404, detail=f"unknown arm {arm!r}")

    rows = []
    for tick, snapshot in enumerate(record.result.arms[arm].snapshots):
        for event in snapshot.events:
            if tier is not None and event.tier != tier:
                continue
            if dt_id is not None and dt_id not in event.target:
                continue
            rows.append({"t": tick, **asdict(event)})

    return {
        "run_id": run_id,
        "ready": True,
        "arm": arm,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "events": rows[offset : offset + limit],
    }


@app.get("/api/runs/{run_id}/notifications")
def run_notifications(run_id: str) -> dict:
    record = _require_record(run_id)
    if record.result is None:
        return {"run_id": run_id, "ready": False, "notifications": []}

    outbox = record.result.arms["vidyut"].outbox
    return {
        "run_id": run_id,
        "ready": True,
        "count": len(outbox.pending()),
        "notifications": [n.to_dict() for n in outbox.pending()],
    }


@app.post("/api/runs/{run_id}/notifications/dispatch")
def dispatch_notifications(run_id: str) -> dict:
    record = _require_record(run_id)
    if record.result is None:
        raise HTTPException(status_code=409, detail="run is not ready")
    notification_ids: list[int] = []
    try:
        with session_scope() as session:
            if session is not None:
                notification_ids = pending_notification_ids(session, run_id)
    except Exception:
        notification_ids = []
    report = dispatch(
        run_id,
        record.result.arms["vidyut"].outbox,
        notification_ids=notification_ids,
    )
    if report.delivered and notification_ids:
        with session_scope() as session:
            if session is not None:
                record_notification_dispatch(
                    session, notification_ids[: report.delivered]
                )
    return {"run_id": run_id, **report.to_dict()}


@app.post("/api/notifications/{notification_id}/delivery")
def notification_delivery(
    notification_id: int, request: DeliveryReceiptRequest
) -> dict:
    with session_scope() as session:
        if session is None:
            raise HTTPException(
                status_code=503,
                detail="delivery receipts require a database",
            )
        try:
            delivery = update_notification_delivery(
                session,
                notification_id,
                request.status,
                request.provider_message_id,
                request.error,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if delivery is None:
            raise HTTPException(status_code=404, detail="notification not found")
        session.flush()
        return {
            "notification_id": notification_id,
            "status": delivery.status,
            "provider_message_id": delivery.provider_message_id,
        }


@app.get("/api/runs/{run_id}/report")
def run_report(run_id: str) -> Response:
    record = _require_record(run_id)
    if record.result is None:
        raise HTTPException(status_code=409, detail="run is not ready")

    pdf = build_report_pdf(run_id, record, record.result)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="vidyut-{record.scenario}-{record.seed}-{run_id}.pdf"'
            )
        },
    )


@app.get("/api/households/{household_id}")
def household(
    household_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    with session_scope() as session:
        if session is None:
            raise HTTPException(
                status_code=503,
                detail="household history requires a database; DATABASE_URL is not configured",
            )
        profile = household_profile(session, household_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="household not found")
        return {**profile, "history": household_history(session, household_id, limit, offset)}


@app.get("/api/fairness/leaderboard")
def fairness_leaderboard(
    dt_id: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
) -> dict:
    with session_scope() as session:
        if session is None:
            raise HTTPException(
                status_code=503,
                detail="fairness leaderboard requires a database; DATABASE_URL is not configured",
            )
        return {"dt_id": dt_id, "households": fairness_leaderboard_rows(session, dt_id, limit)}


@app.get("/api/models")
def models() -> dict:
    return read_artifacts()


@app.websocket("/ws/runs/{run_id}")
async def stream_run(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    record = store.get(run_id)
    if record is None:
        await websocket.send_json({"type": "error", "detail": "run not found"})
        await websocket.close()
        return

    try:
        speed = float(
            websocket.query_params.get("speed", DEFAULT_PLAYBACK_TICKS_PER_SECOND)
        )
        start_tick = int(websocket.query_params.get("from_tick", 0))
        if not math.isfinite(speed) or speed < 0.1 or speed > 200.0:
            raise ValueError
        if start_tick < 0 or start_tick > record.ticks:
            raise ValueError
    except (TypeError, ValueError):
        await websocket.send_json(
            {"type": "error", "detail": "invalid speed or from_tick"}
        )
        await websocket.close(code=1008)
        return

    await websocket.send_json({"type": "status", "status": record.status})
    ready = await asyncio.to_thread(store.wait_ready, run_id)
    record = store.get(run_id)
    result = record.result if record is not None else None
    if not ready or record is None or result is None:
        await websocket.send_json(
            {
                "type": "error",
                "detail": (
                    record.error if record is not None else "simulation did not complete"
                )
                or "simulation did not complete",
            }
        )
        await websocket.close()
        return

    await websocket.send_json(
        {
            "type": "ready",
            "run_id": run_id,
            "scenario": record.scenario,
            "seed": record.seed,
            "ticks": record.ticks,
            "injections": [i.to_dict() for i in record.injections],
        }
    )

    interval = 1.0 / max(speed, 0.1)
    arms = result.arms

    try:
        for tick in range(start_tick, record.ticks):
            snapshots = {name: arm.snapshots[tick] for name, arm in arms.items()}
            await websocket.send_json({"type": "tick", **tick_payload(snapshots, tick)})
            await asyncio.sleep(interval)

        baseline = arms["baseline"].totals
        vidyut = arms["vidyut"].totals
        await websocket.send_json(
            {
                "type": "complete",
                "arms": {
                    "baseline": totals_payload(baseline),
                    "vidyut": totals_payload(vidyut),
                },
                "deltas": delta_payload(baseline, vidyut),
            }
        )
    except WebSocketDisconnect:
        return
