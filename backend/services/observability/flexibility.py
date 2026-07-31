from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class RegisteredEnvelope:
    capacity_kw: float
    households: int
    devices: int
    capacity_by_kind_kw: dict[str, float]
    source: str = "registered"
    method: str = "controllable_device_nameplate"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class OpportunityEstimate:
    ready: bool
    reasons: list[str]
    estimated_profile_kw: list[float]
    actionable_profile_kw: list[float] | None
    estimated_average_kw: float
    estimated_peak_kw: float
    estimated_aggregate_share: float
    actionable_average_kw: float | None
    actionable_peak_kw: float | None
    registered_capacity_kw: float | None
    confidence: str
    coverage_pct: float
    temperature_span_c: float
    fit_score: float
    source: str = "estimated"
    method: str = "interval_baseline_temperature_association_v1"

    def to_dict(self) -> dict:
        return asdict(self)


def registered_envelope(households: Iterable[object]) -> RegisteredEnvelope:
    capacity_by_kind: dict[str, float] = {}
    enrolled_households = 0
    devices = 0
    for household in households:
        if getattr(household, "tier", None) == "critical":
            continue
        household_devices = [
            device
            for device in getattr(household, "devices", [])
            if bool(getattr(device, "controllable", False))
        ]
        if not household_devices:
            continue
        enrolled_households += 1
        for device in household_devices:
            kind = str(getattr(device, "kind"))
            capacity_by_kind[kind] = capacity_by_kind.get(kind, 0.0) + float(
                getattr(device, "rated_kw")
            )
            devices += 1
    rounded = {kind: round(value, 3) for kind, value in sorted(capacity_by_kind.items())}
    return RegisteredEnvelope(
        capacity_kw=round(sum(rounded.values()), 3),
        households=enrolled_households,
        devices=devices,
        capacity_by_kind_kw=rounded,
    )


def registered_availability_profile(world: object, ticks: int) -> list[float]:
    demand = getattr(world, "demand")
    households = getattr(world, "households")
    profile = np.zeros(ticks, dtype=float)
    for load in demand.thermostatic:
        household = households[load.hh_id]
        if load.controllable and household.tier != "critical":
            profile += load.rated_kw * demand.thermal_stress[:ticks]
    for run in demand.deferrable:
        household = households[run.hh_id]
        if not run.controllable or household.tier == "critical":
            continue
        start = max(int(run.start), 0)
        end = min(start + int(run.duration_ticks), ticks)
        if start < end:
            profile[start:end] += float(run.rated_kw)
    return np.round(profile, 3).tolist()


def _matrix(values: object, name: str, nonnegative: bool = True) -> np.ndarray:
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError(f"{name} must be a non-empty days-by-intervals matrix")
    finite = np.isfinite(matrix)
    if nonnegative and np.any(matrix[finite] < 0):
        raise ValueError(f"{name} cannot contain negative values")
    return matrix


def estimate_weather_opportunity(
    aggregate_kw: object,
    ambient_c: object,
    registered_capacity_kw: float | None = None,
    setpoint_c: float = 24.0,
) -> OpportunityEstimate:
    load = _matrix(aggregate_kw, "aggregate_kw")
    temperature = _matrix(ambient_c, "ambient_c", nonnegative=False)
    if load.shape != temperature.shape:
        raise ValueError("aggregate_kw and ambient_c must have the same shape")
    if registered_capacity_kw is not None and registered_capacity_kw < 0:
        raise ValueError("registered_capacity_kw cannot be negative")

    valid = np.isfinite(load) & np.isfinite(temperature)
    total = int(load.size)
    valid_count = int(valid.sum())
    coverage = valid_count / total
    reasons: list[str] = []
    if load.shape[0] < 3:
        reasons.append("at least three comparable days are required")
    if coverage < 0.8:
        reasons.append("joint meter and weather coverage is below 80%")

    finite_temperatures = temperature[valid]
    temperature_span = (
        float(np.ptp(finite_temperatures)) if finite_temperatures.size else 0.0
    )
    if temperature_span < 4.0:
        reasons.append("ambient temperature span is below 4 C")

    with np.errstate(all="ignore"):
        interval_baseline = np.nanquantile(np.where(valid, load, np.nan), 0.2, axis=0)
    residual = np.maximum(load - interval_baseline[None, :], 0.0)
    degree = np.maximum(temperature - setpoint_c, 0.0)
    fit_valid = valid & np.isfinite(residual) & (degree > 0)
    x = degree[fit_valid]
    y = residual[fit_valid]
    denominator = float(np.dot(x, x))
    slope = float(np.dot(x, y) / denominator) if denominator > 0 else 0.0
    slope = max(slope, 0.0)
    predicted = np.minimum(residual, slope * degree)
    predicted[~valid] = np.nan

    if y.size and float(np.dot(y, y)) > 0:
        errors = y - slope * x
        fit_score = max(0.0, 1.0 - float(np.dot(errors, errors) / np.dot(y, y)))
    else:
        fit_score = 0.0
    if fit_score < 0.1:
        reasons.append("load has no reliable positive temperature association")

    latest = predicted[-1]
    estimated_profile = np.nan_to_num(latest, nan=0.0, posinf=0.0, neginf=0.0)
    actionable = None
    if registered_capacity_kw is not None and not reasons:
        actionable = np.minimum(estimated_profile, registered_capacity_kw)

    latest_load = load[-1]
    latest_valid = np.isfinite(latest_load)
    aggregate_energy = float(latest_load[latest_valid].sum())
    estimated_energy = float(estimated_profile[latest_valid].sum())
    share = estimated_energy / aggregate_energy if aggregate_energy > 0 else 0.0

    if reasons:
        confidence = "unavailable"
    elif coverage >= 0.95 and load.shape[0] >= 7 and fit_score >= 0.5:
        confidence = "high"
    elif coverage >= 0.9 and fit_score >= 0.25:
        confidence = "medium"
    else:
        confidence = "low"

    return OpportunityEstimate(
        ready=not reasons,
        reasons=reasons,
        estimated_profile_kw=np.round(estimated_profile, 3).tolist(),
        actionable_profile_kw=(
            np.round(actionable, 3).tolist() if actionable is not None else None
        ),
        estimated_average_kw=round(float(estimated_profile.mean()), 3),
        estimated_peak_kw=round(float(estimated_profile.max()), 3),
        estimated_aggregate_share=round(float(np.clip(share, 0.0, 1.0)), 4),
        actionable_average_kw=(
            round(float(actionable.mean()), 3) if actionable is not None else None
        ),
        actionable_peak_kw=(
            round(float(actionable.max()), 3) if actionable is not None else None
        ),
        registered_capacity_kw=registered_capacity_kw,
        confidence=confidence,
        coverage_pct=round(coverage * 100.0, 2),
        temperature_span_c=round(temperature_span, 3),
        fit_score=round(fit_score, 4),
    )
