from __future__ import annotations

import ast
from pathlib import Path

from services.dispatch.n8n import dispatch
from services.dispatch.outbox import Notification, Outbox, clock_of

SIM_DIR = Path(__file__).resolve().parents[1] / "services" / "sim"


def _notification() -> Notification:
    return Notification(
        tick=76,
        clock=clock_of(76),
        channel="tod_price_broadcast",
        event_type="price_signal",
        dt_id="F1-DT03",
        feeder_id="F1",
        households=32,
        reason_code="PRICE_SIGNAL_PEAK",
        message="Peak tariff applies for the next 60 minutes.",
    )


def test_clock_formatting() -> None:
    assert clock_of(0) == "00:00"
    assert clock_of(42) == "10:30"
    assert clock_of(95) == "23:45"


def test_dispatch_without_webhook_is_a_noop(monkeypatch) -> None:
    monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
    outbox = Outbox()
    outbox.add(_notification())

    report = dispatch("run-1", outbox)
    assert report.status == "not_configured"
    assert report.delivered == 0


def test_dispatch_survives_unreachable_webhook(monkeypatch) -> None:
    monkeypatch.setenv("N8N_WEBHOOK_URL", "http://127.0.0.1:9/unreachable")
    outbox = Outbox()
    outbox.add(_notification())

    report = dispatch("run-1", outbox)
    assert report.status == "unreachable"
    assert report.delivered == 0
    assert report.error


def test_successful_dispatch_acknowledges_notifications(monkeypatch) -> None:
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://dispatch.invalid")
    monkeypatch.setattr("services.dispatch.n8n._post", lambda url, payload: None)
    outbox = Outbox()
    outbox.add(_notification())

    report = dispatch("run-1", outbox)

    assert report.status == "delivered"
    assert report.delivered == 1
    assert outbox.pending() == []


def test_dispatch_includes_persistent_notification_id(monkeypatch) -> None:
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://dispatch.invalid")
    payloads = []
    monkeypatch.setattr(
        "services.dispatch.n8n._post", lambda url, payload: payloads.append(payload)
    )
    outbox = Outbox()
    outbox.add(_notification())

    report = dispatch("run-1", outbox, notification_ids=[731])

    assert report.delivered == 1
    assert payloads[0]["notifications"][0]["notification_id"] == 731


def test_simulation_never_calls_the_network() -> None:
    forbidden = ("requests", "httpx", "urllib.request", "aiohttp", "socket")
    for path in SIM_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not any(name.startswith(f) for f in forbidden), (
                    f"{path.name} imports {name}; the tick loop must make no network calls"
                )
