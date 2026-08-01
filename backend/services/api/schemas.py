from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from services.sim.metrics import ArmSnapshot, RunTotals
from services.sim.scenario import N_TICKS
from services.timebase import clock_of


class ScenarioParams(BaseModel):
    ami_penetration: float | None = Field(default=None, ge=0.0, le=1.0)
    connected_device_penetration: float | None = Field(default=None, ge=0.0, le=1.0)
    ev_penetration: float | None = Field(default=None, ge=0.0, le=1.0)
    critical_share: float | None = Field(default=None, ge=0.0, le=0.2)
    essential_share: float | None = Field(default=None, ge=0.0, le=0.6)
    peak_multiplier: float | None = Field(default=None, ge=1.0, le=2.5)
    tariff_rs_per_kwh: float | None = Field(default=None, gt=0.0, le=50.0)

    def overrides(self) -> dict[str, float]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class CreateRunRequest(BaseModel):
    scenario: str = "heatwave"
    seed: int = 42
    ticks: int = Field(default=N_TICKS, ge=1, le=N_TICKS)
    params: ScenarioParams = Field(default_factory=ScenarioParams)
    carry_debt: bool = True


class CreateRunResponse(BaseModel):
    run_id: str
    status: str


class InjectRequest(BaseModel):
    type: Literal["heatwave", "ev_surge", "cloud_cover", "dt_fault"]
    magnitude: float = Field(default=0.5, ge=0.0, le=3.0)
    from_tick: int | None = Field(default=None, ge=0, le=N_TICKS - 1)
    dt_id: str | None = None


class DeliveryReceiptRequest(BaseModel):
    status: Literal["queued", "dispatched", "delivered", "failed"]
    provider_message_id: str | None = Field(default=None, max_length=128)
    error: str | None = Field(default=None, max_length=2000)


class OperatorDigestRequest(BaseModel):
    recipient_email: str = Field(min_length=3, max_length=254)
    consent: Literal[True]

    @field_validator("recipient_email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        local, separator, domain = normalized.rpartition("@")
        if (
            separator != "@"
            or not local
            or "." not in domain
            or domain.startswith(".")
            or domain.endswith(".")
            or any(character.isspace() for character in normalized)
        ):
            raise ValueError("enter a valid operator email address")
        return normalized


class DigestDeliveryReceiptRequest(BaseModel):
    notification_ids: list[int] = Field(min_length=1, max_length=500)
    status: Literal["delivered", "failed"]
    provider_message_id: str | None = Field(default=None, max_length=128)
    error: str | None = Field(default=None, max_length=2000)


class FlexibilityEstimateRequest(BaseModel):
    aggregate_kw: list[list[float | None]]
    ambient_c: list[list[float | None]]
    registered_capacity_kw: float | None = Field(default=None, ge=0.0)
    setpoint_c: float = Field(default=24.0, ge=15.0, le=35.0)


class EventVerificationRequest(BaseModel):
    history_kw: list[list[float | None]]
    observed_kw: list[float | None]
    event_start_index: int = Field(ge=0)
    event_end_index: int = Field(gt=0)
    committed_reduction_kw: float = Field(default=0.0, ge=0.0)
    method: Literal["high_4_of_5", "ten_in_ten"] = "high_4_of_5"
    adjustment_intervals: int = Field(default=4, ge=0, le=16)


def arm_payload(snapshot: ArmSnapshot) -> dict:
    return {
        "feeders": [asdict(f) for f in snapshot.feeders],
        "dts": [asdict(d) for d in snapshot.dts],
        "topology": {"tie_switches": snapshot.tie_switches},
        "metrics": asdict(snapshot.metrics),
        "events": [asdict(e) for e in snapshot.events],
    }


def tick_payload(arms: dict[str, ArmSnapshot], tick: int) -> dict:
    return {
        "t": tick,
        "clock": clock_of(tick),
        "arms": {name: arm_payload(snapshot) for name, snapshot in arms.items()},
        "forecast": arms["vidyut"].forecast if "vidyut" in arms else None,
    }


def totals_payload(totals: RunTotals) -> dict:
    return asdict(totals)


def delta_payload(baseline: RunTotals, vidyut: RunTotals) -> dict:
    numeric_fields = [
        "peak_kva",
        "max_trafo_loading_pct",
        "total_losses_kwh",
        "losses_pct_of_delivered",
        "mean_spread_pct",
        "max_spread_pct",
        "homes_dark_minutes",
        "peak_homes_dark",
        "critical_uptime_pct",
        "unserved_kwh",
        "demanded_kwh",
        "flexibility_kwh",
        "energy_balance_error_kwh",
        "unserved_cost_rs",
        "served_kwh",
        "gini",
        "gini_affected",
        "max_household_burden_min",
        "households_curtailed",
    ]
    base = asdict(baseline)
    vid = asdict(vidyut)
    return {field: vid[field] - base[field] for field in numeric_fields}
