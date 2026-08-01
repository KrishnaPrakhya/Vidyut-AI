from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Any

from services.timebase import clock_of

if TYPE_CHECKING:
    from services.api.store import RunRecord


def _peak_outage_avoided(record: RunRecord) -> dict[str, Any]:
    assert record.result is not None
    baseline = record.result.arms["baseline"]
    vidyut = record.result.arms["vidyut"]
    best = {
        "tick": 0,
        "clock": clock_of(0),
        "dt_id": None,
        "baseline_homes_dark": 0,
        "vidyut_homes_dark": 0,
        "homes_kept_powered": 0,
    }
    for tick, (baseline_snapshot, vidyut_snapshot) in enumerate(
        zip(baseline.snapshots, vidyut.snapshots, strict=True)
    ):
        vidyut_by_dt = {row.id: row for row in vidyut_snapshot.dts}
        for baseline_dt in baseline_snapshot.dts:
            vidyut_dt = vidyut_by_dt.get(baseline_dt.id)
            if vidyut_dt is None:
                continue
            avoided = max(
                baseline_dt.households_dark - vidyut_dt.households_dark, 0
            )
            if avoided > best["homes_kept_powered"]:
                best = {
                    "tick": tick,
                    "clock": clock_of(tick),
                    "dt_id": baseline_dt.id,
                    "baseline_homes_dark": baseline_dt.households_dark,
                    "vidyut_homes_dark": vidyut_dt.households_dark,
                    "homes_kept_powered": avoided,
                }
    return best


def build_operator_digest(
    record: RunRecord,
    notification_ids: list[int],
    callback_url: str,
    report_url: str,
    public_report_url: str | None = None,
) -> dict[str, Any]:
    """Build a transport-ready digest without receiving or retaining an email address."""
    if record.result is None:
        raise ValueError("run is not ready")

    outbox = record.result.arms["vidyut"].outbox
    notifications = outbox.pending()
    baseline = record.result.arms["baseline"].totals
    vidyut = record.result.arms["vidyut"].totals
    peak = _peak_outage_avoided(record)
    transformers = sorted({row.dt_id for row in notifications})
    household_opportunities = sum(row.households for row in notifications)
    preview = notifications[0].to_dict() if notifications else None
    scenario_label = record.scenario.replace("_", " ").title()
    operator_report_url = public_report_url or report_url
    subject = (
        f"Vidyut — simulated {scenario_label} run digest · seed {record.seed}"
    )

    if peak["homes_kept_powered"]:
        peak_line = (
            f"Peak comparison at {peak['clock']} on {peak['dt_id']}: "
            f"the baseline left {peak['baseline_homes_dark']} homes dark; "
            f"Vidyut left {peak['vidyut_homes_dark']} dark."
        )
    else:
        peak_line = "No transformer-level outage divergence occurred in this run."

    preview_message = preview["message"] if preview else "No resident message was queued."
    text = "\n".join(
        [
            "VIDYUT — SIMULATED OPERATOR DIGEST",
            "",
            f"Scenario: {scenario_label}",
            f"Seed: {record.seed}",
            (
                f"Dispatch summary: {len(notifications)} simulated broadcasts across "
                f"{len(transformers)} transformers ({household_opportunities} household "
                "notification opportunities)."
            ),
            peak_line,
            f"Critical-load uptime: {vidyut.critical_uptime_pct:.3f}%.",
            (
                f"Dark-home minutes: baseline {baseline.homes_dark_minutes:,.0f}; "
                f"Vidyut {vidyut.homes_dark_minutes:,.0f}."
            ),
            f"Audit report: {operator_report_url}",
            "",
            "RESIDENT MESSAGE PREVIEW — NOT SENT TO A RESIDENT",
            preview_message,
            "",
            "This is a simulation. No live utility system or resident was contacted.",
        ]
    )
    html = f"""<!doctype html>
<html><body style="font-family:Arial,sans-serif;color:#102019;line-height:1.5">
  <div style="max-width:680px;margin:auto;border:1px solid #d7e1da;padding:28px">
    <p style="font-size:12px;letter-spacing:.12em;color:#5d7065">SIMULATED OPERATOR DIGEST</p>
    <h1 style="font-size:28px;margin:0 0 20px">Vidyut · {escape(scenario_label)}</h1>
    <p><strong>Seed:</strong> {record.seed}</p>
    <p><strong>{len(notifications)}</strong> simulated broadcasts across
      <strong>{len(transformers)}</strong> transformers.</p>
    <p>{escape(peak_line)}</p>
    <p><strong>Critical-load uptime:</strong> {vidyut.critical_uptime_pct:.3f}%<br>
      <strong>Dark-home minutes:</strong> {baseline.homes_dark_minutes:,.0f} baseline →
      {vidyut.homes_dark_minutes:,.0f} with Vidyut</p>
    <p><a href="{escape(operator_report_url, quote=True)}">Open the auditable simulation report</a></p>
    <div style="margin-top:24px;padding:16px;background:#f2f7f3;border-left:4px solid #a4d63c">
      <strong>Resident message preview — not sent to a resident</strong><br>
      {escape(preview_message)}
    </div>
    <p style="margin-top:24px;font-size:12px;color:#5d7065">
      This is a simulation. No live utility system or resident was contacted.
    </p>
  </div>
</body></html>"""

    return {
        "schema_version": 1,
        "kind": "operator_digest",
        "run_id": record.run_id,
        "email": {"subject": subject, "text": text, "html": html},
        "digest": {
            "scenario": record.scenario,
            "seed": record.seed,
            "broadcast_count": len(notifications),
            "transformer_count": len(transformers),
            "household_notification_opportunities": household_opportunities,
            "peak_outage_avoided": peak,
            "baseline_homes_dark_minutes": round(baseline.homes_dark_minutes, 2),
            "vidyut_homes_dark_minutes": round(vidyut.homes_dark_minutes, 2),
            "critical_load_uptime_pct": round(vidyut.critical_uptime_pct, 5),
            "resident_message_preview": preview,
        },
        "notification_ids": notification_ids,
        "report_url": report_url,
        "public_report_url": operator_report_url,
        "callback_url": callback_url,
        "simulation_notice": (
            "This is a simulation. No live utility system or resident was contacted."
        ),
    }
