from __future__ import annotations

import urllib.error

import pytest
from pandapower.auxiliary import LoadflowNotConverged

from services.api.store import RunRecord, RunStore
from services.dispatch.n8n import dispatch
from services.dispatch.outbox import Notification, Outbox
from services.sim.topology import _build_switch_graph
from services.sim.world import build_world, solve_power_flow


def notification() -> Notification:
    return Notification(
        tick=1,
        clock="00:15",
        channel="test",
        event_type="test",
        dt_id="F1-DT01",
        feeder_id="F1",
        households=1,
        reason_code="TEST",
        message="test",
    )


def test_run_store_returns_detached_record_snapshots() -> None:
    store = RunStore(max_workers=1)
    record = RunRecord("r1", "normal", 42, 1, {})
    with store._lock:
        store._runs[record.run_id] = record

    left = store.get("r1")
    right = store.get("r1")

    assert left is not right
    left.params["peak_multiplier"] = 2.0
    assert right.params == {}


def test_switch_graph_is_cached_on_network_context() -> None:
    world = build_world("vidyut", "normal", 42)
    assert _build_switch_graph(world.ctx) is _build_switch_graph(world.ctx)


def test_unexpected_power_flow_error_propagates(monkeypatch) -> None:
    world = build_world("vidyut", "normal", 42)
    monkeypatch.setattr("services.sim.world.pp.runpp", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bug")))
    with pytest.raises(RuntimeError, match="bug"):
        solve_power_flow(world)


def test_expected_nonconvergence_is_reported(monkeypatch) -> None:
    world = build_world("vidyut", "normal", 42)
    monkeypatch.setattr(
        "services.sim.world.pp.runpp",
        lambda *args, **kwargs: (_ for _ in ()).throw(LoadflowNotConverged("no solution")),
    )
    assert solve_power_flow(world).converged is False


def test_dispatch_retries_transient_failure(monkeypatch) -> None:
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://dispatch.invalid")
    monkeypatch.setenv("N8N_WEBHOOK_TOKEN", "test-token")
    monkeypatch.setattr("services.dispatch.n8n.time.sleep", lambda seconds: None)
    attempts = []

    def post(url, payload):
        attempts.append(payload)
        if len(attempts) < 3:
            raise urllib.error.URLError("temporary")

    monkeypatch.setattr("services.dispatch.n8n._post", post)
    outbox = Outbox([notification()])
    report = dispatch("r1", outbox, notification_ids=[9])

    assert report.delivered == 1
    assert len(attempts) == 3
    assert attempts[0]["idempotency_key"] == attempts[2]["idempotency_key"]
