from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, Field

from services.sim.metrics import ArmSnapshot, RunTotals
from services.sim.scenario import N_TICKS


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


def clock_of(tick: int) -> str:
    minutes = tick * 15
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


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
