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


def test_recorded_replays_are_discoverable_and_readable(client: TestClient) -> None:
    catalog = client.get("/api/recordings")
    assert catalog.status_code == 200
    rows = catalog.json()["recordings"]
    assert {"normal", "heatwave", "ev_surge"} <= {
        row["scenario"] for row in rows
    }

    replay = client.get("/api/recordings/heatwave?seed=42")
    assert replay.status_code == 200
    assert replay.json()["meta"]["ticks"] == 96
    assert len(replay.json()["ticks"]) == 96


def test_unknown_recording_is_rejected(client: TestClient) -> None:
    assert client.get("/api/recordings/monsoon?seed=42").status_code == 404
    assert client.get("/api/recordings/heatwave?seed=999").status_code == 404


def test_unknown_scenario_is_rejected(client: TestClient) -> None:
    response = client.post("/api/runs", json={"scenario": "monsoon", "seed": 1})
    assert response.status_code == 404


def test_out_of_range_param_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/runs", json={"scenario": "normal", "params": {"ami_penetration": 1.7}}
    )
    assert response.status_code == 422


REQUIRED_FORECAST_MODELS = {"seasonal_naive", "chronos_finetuned"}


def test_models_endpoint_is_honest_about_what_is_trained(client: TestClient) -> None:
    body = client.get("/api/models").json()
    assert set(body["models"]) == {"forecast"}
    assert body["observability"]["ready"] is True

    for name, artifact in body["models"].items():
        if artifact["trained"]:
            continue
        assert any(
            phrase in artifact["message"]
            for phrase in ("not found", "not valid JSON", "unavailable")
        )
        assert "MASE" not in json.dumps(artifact), (
            f"{name} is untrained but the payload carries metrics; the page would show "
            f"numbers with nothing behind them"
        )


def test_trained_forecast_artifact_has_everything_the_page_needs(client: TestClient) -> None:
    forecast = client.get("/api/models").json()["models"]["forecast"]
    if not forecast["trained"]:
        pytest.skip("forecast model not trained in this checkout")

    assert REQUIRED_FORECAST_MODELS <= set(forecast["models"])
    for name, scores in forecast["models"].items():
        assert scores["MASE"] is not None and scores["MASE"] > 0, name

    assert forecast["cold_start"]["history_days"] > 0
    assert forecast["n_series"] > 0 and forecast["n_obs"] > 0
    assert forecast["holdout"]

    provenance = forecast["data"]
    assert provenance["real_measurements"] is True
    assert provenance["synthetic_training_data"] is False, (
        "a headline metric trained on synthetic data must never reach the models page"
    )


def test_forecast_beats_the_naive_baseline(client: TestClient) -> None:
    forecast = client.get("/api/models").json()["models"]["forecast"]
    if not forecast["trained"]:
        pytest.skip("forecast model not trained in this checkout")

    naive = forecast["models"]["seasonal_naive"]["MASE"]
    tuned = forecast["models"]["chronos_finetuned"]["MASE"]
    assert tuned < naive, (
        f"the trained model ({tuned}) is no better than seasonal naive ({naive}); "
        f"the models page would be claiming an improvement that does not exist"
    )


def test_model_registry_distinguishes_evaluation_from_runtime(
    client: TestClient,
) -> None:
    models = client.get("/api/models").json()["models"]
    assert models["forecast"]["trained"] is True
    assert models["forecast"]["evaluation_only"] is True
    assert models["forecast"]["runtime_ready"] is False


def test_observability_status_states_its_boundary(client: TestClient) -> None:
    body = client.get("/api/observability/status").json()
    assert body["ready"] is True
    assert body["component"] == "flexibility_assurance"
    assert any("does not identify" in boundary for boundary in body["boundaries"])


def test_observability_estimate_and_verification_endpoints(client: TestClient) -> None:
    temperatures = [
        [21 + day, 22 + day, 24 + day, 27 + day, 30 + day, 32 + day, 28 + day, 24 + day]
        for day in range(7)
    ]
    loads = [
        [8 + 1.2 * max(value - 24, 0) for value in day]
        for day in temperatures
    ]
    estimate = client.post(
        "/api/observability/flexibility/estimate",
        json={
            "aggregate_kw": loads,
            "ambient_c": temperatures,
            "registered_capacity_kw": 5.0,
        },
    )
    assert estimate.status_code == 200
    assert estimate.json()["ready"] is True
    assert estimate.json()["source"] == "estimated"

    history = [[value] * 8 for value in (100, 110, 120, 130, 140)]
    observed = [125, 125, 125, 125, 105, 105, 125, 125]
    verification = client.post(
        "/api/observability/events/verify",
        json={
            "history_kw": history,
            "observed_kw": observed,
            "event_start_index": 4,
            "event_end_index": 6,
            "committed_reduction_kw": 20,
        },
    )
    assert verification.status_code == 200
    assert verification.json()["realised_reduction_kw"] == pytest.approx(20.0)
    assert verification.json()["source"] == "verified"


def test_summary_reports_both_arms_and_deltas(client: TestClient, ready_run: str) -> None:
    body = client.get(f"/api/runs/{ready_run}/summary").json()
    assert body["ready"] is True
    assert set(body["arms"]) == {"baseline", "vidyut"}
    assert "unserved_kwh" in body["deltas"]
    assert body["arms"]["vidyut"]["critical_uptime_pct"] == pytest.approx(100.0)


def test_run_flexibility_uses_registered_devices(client: TestClient, ready_run: str) -> None:
    body = client.get(f"/api/runs/{ready_run}/flexibility").json()
    assert body["registered"]["source"] == "registered"
    assert body["registered"]["capacity_kw"] > 0
    assert len(body["available"]["profile_kw"]) == SHORT_RUN_TICKS
    assert body["realised"]["source"] == "simulation_measurement"


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


def test_injection_requires_a_ready_run(client: TestClient) -> None:
    run_id = client.post(
        "/api/runs", json={"scenario": "normal", "seed": 8}
    ).json()["run_id"]
    response = client.post(
        f"/api/runs/{run_id}/inject",
        json={"type": "heatwave", "magnitude": 0.4, "from_tick": 2},
    )
    assert response.status_code == 409


def test_fault_injection_rejects_unknown_transformer(
    client: TestClient, ready_run: str
) -> None:
    response = client.post(
        f"/api/runs/{ready_run}/inject",
        json={"type": "dt_fault", "magnitude": 1.0, "dt_id": "missing"},
    )
    assert response.status_code == 422


def test_injection_tick_must_be_inside_short_run(
    client: TestClient, ready_run: str
) -> None:
    response = client.post(
        f"/api/runs/{ready_run}/inject",
        json={"type": "heatwave", "magnitude": 0.5, "from_tick": SHORT_RUN_TICKS},
    )
    assert response.status_code == 422


def test_websocket_rejects_invalid_playback_parameters(
    client: TestClient, ready_run: str
) -> None:
    with client.websocket_connect(f"/ws/runs/{ready_run}?speed=nan") as ws:
        message = ws.receive_json()
        assert message["type"] == "error"
