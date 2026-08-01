from __future__ import annotations

from types import SimpleNamespace

from services.dispatch.digest import build_operator_digest
from services.dispatch.outbox import Notification, Outbox


def _dt(identifier: str, dark: int):
    return SimpleNamespace(id=identifier, households_dark=dark)


def test_operator_digest_is_explicitly_simulated_and_has_no_recipient() -> None:
    notification = Notification(
        tick=67,
        clock="16:45",
        channel="tod_price_broadcast",
        event_type="price_signal",
        dt_id="F1-DT17",
        feeder_id="F1",
        households=32,
        reason_code="PRICE_SIGNAL_PEAK",
        message="Delay flexible demand for the next 60 minutes.",
    )
    baseline = SimpleNamespace(
        snapshots=[SimpleNamespace(dts=[_dt("F1-DT17", 70)])],
        totals=SimpleNamespace(homes_dark_minutes=1050.0),
    )
    vidyut = SimpleNamespace(
        snapshots=[SimpleNamespace(dts=[_dt("F1-DT17", 0)])],
        totals=SimpleNamespace(
            homes_dark_minutes=0.0,
            critical_uptime_pct=100.0,
        ),
        outbox=Outbox([notification]),
    )
    record = SimpleNamespace(
        run_id="run-1",
        scenario="heatwave",
        seed=42,
        result=SimpleNamespace(arms={"baseline": baseline, "vidyut": vidyut}),
    )

    payload = build_operator_digest(
        record,
        [731],
        "https://api.example/callback",
        "https://n8n-api.example/report",
        "https://operator.example/report",
    )

    assert "simulated" in payload["email"]["subject"].lower()
    assert "not sent to a resident" in payload["email"]["text"].lower()
    assert payload["digest"]["peak_outage_avoided"]["homes_kept_powered"] == 70
    assert payload["notification_ids"] == [731]
    assert payload["report_url"] == "https://n8n-api.example/report"
    assert payload["public_report_url"] == "https://operator.example/report"
    assert "https://operator.example/report" in payload["email"]["html"]
    assert "https://n8n-api.example/report" not in payload["email"]["html"]
    assert "recipient" not in payload
