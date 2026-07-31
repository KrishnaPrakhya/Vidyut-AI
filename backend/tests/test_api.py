from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from services.api.main import app

SHORT_RUN_TICKS = 6
READY_TIMEOUT_SECONDS = 180.0


def wait_ready(client: TestClient, run_id: str) -> str:
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status = client.get(f"/api/runs/{run_id}").json()["status"]
        if status in ("ready", "failed"):
            return status
        time.sleep(0.5)
    return "timeout"


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def ready_run(client: TestClient) -> str:
    response = client.post(
        "/api/runs", json={"scenario": "heatwave", "seed": 42, "ticks": SHORT_RUN_TICKS}
    )
    run_id = response.json()["run_id"]
    assert client.get(f"/api/runs/{run_id}/summary").status_code == 200
    assert wait_ready(client, run_id) == "ready"
    return run_id


def test_health_lists_scenarios(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert {"normal", "heatwave", "ev_surge"} <= set(body["scenarios"])


def test_unknown_scenario_is_rejected(client: TestClient) -> None:
    response = client.post("/api/runs", json={"scenario": "monsoon", "seed": 1})
    assert response.status_code == 404


def test_out_of_range_param_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/runs", json={"scenario": "normal", "params": {"ami_penetration": 1.7}}
    )
    assert response.status_code == 422


def test_models_endpoint_reports_untrained_state_honestly(client: TestClient) -> None:
    body = client.get("/api/models").json()
    assert "forecast" in body["models"]
    forecast = body["models"]["forecast"]
    if not forecast["trained"]:
        assert "not found" in forecast["message"]
        assert "MASE" not in json.dumps(forecast)


def test_summary_reports_both_arms_and_deltas(client: TestClient, ready_run: str) -> None:
    body = client.get(f"/api/runs/{ready_run}/summary").json()
    assert body["ready"] is True
    assert set(body["arms"]) == {"baseline", "vidyut"}
    assert "unserved_kwh" in body["deltas"]
    assert body["arms"]["vidyut"]["critical_uptime_pct"] == pytest.approx(100.0)


def test_events_are_filterable(client: TestClient, ready_run: str) -> None:
    body = client.get(f"/api/runs/{ready_run}/events?arm=vidyut&limit=5").json()
    assert body["ready"] is True
    assert len(body["events"]) <= 5
    for event in body["events"]:
        assert event["reason_code"]
        assert "t" in event


def test_every_event_carries_a_human_readable_reason(client: TestClient, ready_run: str) -> None:
    body = client.get(f"/api/runs/{ready_run}/events?arm=vidyut&limit=1000").json()
    for event in body["events"]:
        assert event["detail"], f"event {event['action']} has no explanation"


def test_missing_run_returns_404(client: TestClient) -> None:
    assert client.get("/api/runs/deadbeef/summary").status_code == 404


def test_report_renders_a_pdf(client: TestClient, ready_run: str) -> None:
    response = client.get(f"/api/runs/{ready_run}/report")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 2000


def test_report_rejects_a_run_that_is_not_ready(client: TestClient) -> None:
    run_id = client.post("/api/runs", json={"scenario": "heatwave", "seed": 5}).json()["run_id"]
    response = client.get(f"/api/runs/{run_id}/report")
    assert response.status_code in (200, 409)


def test_websocket_streams_one_message_per_tick(client: TestClient, ready_run: str) -> None:
    ticks: list[int] = []
    with client.websocket_connect(f"/ws/runs/{ready_run}?speed=200") as ws:
        while True:
            message = ws.receive_json()
            if message["type"] == "tick":
                ticks.append(message["t"])
                assert set(message["arms"]) == {"baseline", "vidyut"}
                assert len(message["arms"]["vidyut"]["dts"]) == 60
                assert len(message["arms"]["vidyut"]["feeders"]) == 3
            elif message["type"] == "complete":
                assert "deltas" in message
                break
            elif message["type"] == "error":
                pytest.fail(message["detail"])

    assert ticks == list(range(SHORT_RUN_TICKS))


def test_websocket_rejects_unknown_run(client: TestClient) -> None:
    with client.websocket_connect("/ws/runs/nonexistent") as ws:
        assert ws.receive_json()["type"] == "error"


def test_injection_triggers_resimulation(client: TestClient) -> None:
    run_id = client.post(
        "/api/runs", json={"scenario": "normal", "seed": 42, "ticks": SHORT_RUN_TICKS}
    ).json()["run_id"]
    assert wait_ready(client, run_id) == "ready"

    response = client.post(
        f"/api/runs/{run_id}/inject", json={"type": "heatwave", "magnitude": 0.6, "from_tick": 2}
    )
    assert response.status_code == 200
    assert response.json()["injections"][0]["type"] == "heatwave"

    assert wait_ready(client, run_id) == "ready"
    summary = client.get(f"/api/runs/{run_id}/summary").json()
    assert summary["ready"] is True
    assert summary["injections"][0]["type"] == "heatwave"
