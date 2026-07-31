from __future__ import annotations

import io
from dataclasses import asdict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.api.schemas import clock_of
from services.sim.run import RunResult

INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")
RULE = colors.HexColor("#D1D5DB")
BAND = colors.HexColor("#F3F4F6")

MAX_EVENT_ROWS = 45


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=19, leading=23, textColor=INK, spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontSize=9.5, leading=13,
            textColor=MUTED, spaceAfter=14,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11.5, leading=14, textColor=INK, spaceBefore=16, spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontSize=9, leading=13, textColor=INK,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontSize=7.8, leading=10.5, textColor=MUTED,
        ),
        "cell": ParagraphStyle(
            "cell", parent=base["Normal"], fontSize=7.6, leading=10, textColor=INK,
        ),
    }


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def _table(rows: list[list], widths: list[float], align_right_from: int = 1) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.8),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                ("BACKGROUND", (0, 0), (-1, 0), BAND),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
                ("ALIGN", (align_right_from, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _headline_rows(baseline, vidyut) -> list[list]:
    spec = [
        ("Energy delivered", "served_kwh", "kWh", 0),
        ("Demand flexibility", "flexibility_kwh", "kWh", 1),
        ("Unserved energy", "unserved_kwh", "kWh", 1),
        ("Energy balance error", "energy_balance_error_kwh", "kWh", 6),
        ("Unserved energy cost", "unserved_cost_rs", "Rs", 0),
        ("Homes dark, peak count", "peak_homes_dark", "homes", 0),
        ("Homes dark", "homes_dark_minutes", "household-min", 0),
        ("Critical-load uptime", "critical_uptime_pct", "%", 3),
        ("Max transformer loading", "max_trafo_loading_pct", "%", 1),
        ("Feeder utilisation spread, max", "max_spread_pct", "%", 1),
        ("Network losses", "total_losses_kwh", "kWh", 1),
        ("Losses as share of delivered", "losses_pct_of_delivered", "%", 2),
        ("Households affected", "households_curtailed", "homes", 0),
        ("Curtailment Gini, affected", "gini_affected", "", 4),
        ("Curtailment Gini, all households", "gini", "", 4),
    ]
    base_map, vid_map = asdict(baseline), asdict(vidyut)

    rows = [["Metric", "Unit", "Baseline", "Vidyut", "Delta"]]
    for label, key, unit, digits in spec:
        base_value, vid_value = base_map[key], vid_map[key]
        rows.append(
            [
                label,
                unit,
                _fmt(base_value, digits),
                _fmt(vid_value, digits),
                _fmt(vid_value - base_value, digits),
            ]
        )
    return rows


def _severity_rows(baseline, vidyut) -> list[list]:
    labels = {
        "device": "Connected device curtailment",
        "load_limit": "Meter load limit",
        "disconnect": "Full service disconnection",
    }
    rows = [["Intervention", "Baseline", "Vidyut"]]
    for key, label in labels.items():
        rows.append(
            [
                label,
                _fmt(baseline.minutes_by_level.get(key, 0.0), 0),
                _fmt(vidyut.minutes_by_level.get(key, 0.0), 0),
            ]
        )
    return rows


def _event_rows(result: RunResult, styles: dict) -> tuple[list[list], int]:
    rows = [["Time", "Tier", "Action", "Target", "Homes", "Reason"]]
    collected = []
    for tick, snapshot in enumerate(result.arms["vidyut"].snapshots):
        for event in snapshot.events:
            collected.append((tick, event))

    for tick, event in collected[:MAX_EVENT_ROWS]:
        rows.append(
            [
                clock_of(tick),
                str(event.tier),
                event.action.replace("_", " "),
                event.target,
                str(event.households),
                Paragraph(event.detail or event.reason_code, styles["cell"]),
            ]
        )
    return rows, len(collected)


def build_report_pdf(run_id: str, record, result: RunResult) -> bytes:
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Vidyut incident report {run_id}",
    )

    baseline = result.arms["baseline"].totals
    vidyut = result.arms["vidyut"].totals
    injections = ", ".join(
        f"{i.type} x{i.magnitude:g} from {clock_of(i.from_tick)}" for i in record.injections
    )

    story = [
        Paragraph("Vidyut incident report", styles["title"]),
        Paragraph(
            f"Simulated distribution network &mdash; not connected to any live utility system. "
            f"Run {run_id} &middot; scenario <b>{record.scenario}</b> &middot; seed {record.seed} "
            f"&middot; {record.ticks} intervals of 15 minutes &middot; generated {record.created_at}",
            styles["subtitle"],
        ),
        Paragraph("Outcome against current practice", styles["h2"]),
        Paragraph(
            "Both arms run on identical demand under an identical seed. The baseline arm reproduces "
            "current utility practice: when a distribution transformer exceeds its rating for two "
            "consecutive intervals, the whole transformer is de-energised for 45 minutes.",
            styles["body"],
        ),
        Spacer(1, 8),
        _table(_headline_rows(baseline, vidyut), [58 * mm, 20 * mm, 26 * mm, 26 * mm, 26 * mm]),
        Paragraph(
            "Vidyut serves more energy than the baseline, so its peak served kVA and absolute losses "
            "are higher. Losses are therefore also reported as a share of energy delivered.",
            styles["small"],
        ),
        Paragraph("Household-minutes of intervention, by severity", styles["h2"]),
        Paragraph(
            "The baseline has a single instrument, full disconnection. Vidyut substitutes milder and "
            "more targeted interventions for most of it.",
            styles["body"],
        ),
        Spacer(1, 8),
        _table(_severity_rows(baseline, vidyut), [78 * mm, 39 * mm, 39 * mm]),
        Paragraph("Fairness", styles["h2"]),
        Paragraph(
            f"Every curtailment is recorded against the household that bore it, weighted by severity "
            f"(device 1x, load limit 2x, disconnect 4x). Vidyut affected "
            f"{vidyut.households_curtailed:,} households against the baseline's "
            f"{baseline.households_curtailed:,}, with a worst individual burden of "
            f"{vidyut.max_household_burden_min:,.0f} weighted minutes against "
            f"{baseline.max_household_burden_min:,.0f}. The baseline records a lower Gini among "
            f"affected households because de-energising a transformer harms everyone downstream "
            f"equally; that is equality of outcome achieved by indiscriminate means, not selectivity.",
            styles["body"],
        ),
    ]

    if injections:
        story += [
            Paragraph("Injected events", styles["h2"]),
            Paragraph(injections, styles["body"]),
        ]

    event_rows, total_events = _event_rows(result, styles)
    story += [
        PageBreak(),
        Paragraph("Decision log", styles["h2"]),
        Paragraph(
            f"{total_events:,} decisions were recorded for the Vidyut arm. Every action carries a "
            f"machine-generated reason. Up to {min(MAX_EVENT_ROWS, total_events)} are shown; the "
            f"complete log is available from the events endpoint.",
            styles["body"],
        ),
        Spacer(1, 8),
        KeepTogether(
            _table(
                event_rows,
                [15 * mm, 10 * mm, 27 * mm, 22 * mm, 14 * mm, 68 * mm],
                align_right_from=4,
            )
        ),
    ]

    doc.build(story)
    return buffer.getvalue()
