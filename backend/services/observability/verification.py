from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np

from services.timebase import TICK_HOURS

BaselineMethod = Literal["high_4_of_5", "ten_in_ten"]


@dataclass(frozen=True)
class VerificationResult:
    ready: bool
    method: str
    selected_days: list[int]
    baseline_profile_kw: list[float]
    observed_profile_kw: list[float]
    baseline_average_kw: float
    observed_average_kw: float
    gross_difference_kw: float
    realised_reduction_kw: float
    realised_reduction_kwh: float
    committed_reduction_kw: float
    performance_pct: float | None
    same_day_adjustment_kw: float
    coverage_pct: float
    confidence: str
    source: str = "verified"

    def to_dict(self) -> dict:
        return asdict(self)


def _matrix(values: object) -> np.ndarray:
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError("history_kw must be a non-empty days-by-intervals matrix")
    finite = np.isfinite(matrix)
    if np.any(matrix[finite] < 0):
        raise ValueError("history_kw cannot contain negative values")
    return matrix


def _profile(values: object, intervals: int) -> np.ndarray:
    profile = np.asarray(values, dtype=float)
    if profile.ndim != 1 or profile.size != intervals:
        raise ValueError("observed_kw must match the history interval count")
    finite = np.isfinite(profile)
    if np.any(profile[finite] < 0):
        raise ValueError("observed_kw cannot contain negative values")
    return profile


def verify_event(
    history_kw: object,
    observed_kw: object,
    event_start_index: int,
    event_end_index: int,
    committed_reduction_kw: float,
    method: BaselineMethod = "high_4_of_5",
    adjustment_intervals: int = 4,
) -> VerificationResult:
    history = _matrix(history_kw)
    observed = _profile(observed_kw, history.shape[1])
    if not 0 <= event_start_index < event_end_index <= history.shape[1]:
        raise ValueError("event interval is outside the daily profile")
    if committed_reduction_kw < 0:
        raise ValueError("committed_reduction_kw cannot be negative")

    event_slice = slice(event_start_index, event_end_index)
    eligible = np.flatnonzero(np.all(np.isfinite(history[:, event_slice]), axis=1))
    required = 4 if method == "high_4_of_5" else 10
    if eligible.size < required:
        raise ValueError(f"{method} requires at least {required} complete eligible days")

    if method == "high_4_of_5":
        candidates = eligible[-5:]
        scores = np.mean(history[candidates, event_slice], axis=1)
        selected = candidates[np.argsort(scores)[-4:]]
    elif method == "ten_in_ten":
        selected = eligible[-10:]
    else:
        raise ValueError(f"unsupported baseline method {method!r}")

    baseline = np.nanmean(history[selected], axis=0)
    adjustment = 0.0
    pre_start = max(0, event_start_index - max(adjustment_intervals, 0))
    if pre_start < event_start_index:
        pre = slice(pre_start, event_start_index)
        pre_valid = np.isfinite(observed[pre]) & np.isfinite(baseline[pre])
        if int(pre_valid.sum()) >= 2:
            raw_adjustment = float(
                np.mean(observed[pre][pre_valid] - baseline[pre][pre_valid])
            )
            cap = 0.2 * float(np.mean(baseline[event_slice]))
            adjustment = float(np.clip(raw_adjustment, -cap, cap))
            baseline[event_slice] += adjustment

    baseline_event = baseline[event_slice]
    observed_event = observed[event_slice]
    valid = np.isfinite(baseline_event) & np.isfinite(observed_event)
    coverage = float(valid.mean()) if valid.size else 0.0
    if not valid.any():
        raise ValueError("event interval has no joint baseline and observed coverage")

    baseline_average = float(np.mean(baseline_event[valid]))
    observed_average = float(np.mean(observed_event[valid]))
    gross_difference = baseline_average - observed_average
    realised = max(gross_difference, 0.0)
    realised_kwh = max(
        float(np.sum(baseline_event[valid] - observed_event[valid])) * TICK_HOURS,
        0.0,
    )
    performance = (
        100.0 * realised / committed_reduction_kw
        if committed_reduction_kw > 0
        else None
    )
    confidence = "high" if coverage == 1.0 and eligible.size >= required else "medium"

    return VerificationResult(
        ready=True,
        method=method,
        selected_days=selected.astype(int).tolist(),
        baseline_profile_kw=np.round(baseline_event, 3).tolist(),
        observed_profile_kw=np.round(observed_event, 3).tolist(),
        baseline_average_kw=round(baseline_average, 3),
        observed_average_kw=round(observed_average, 3),
        gross_difference_kw=round(gross_difference, 3),
        realised_reduction_kw=round(realised, 3),
        realised_reduction_kwh=round(realised_kwh, 3),
        committed_reduction_kw=round(committed_reduction_kw, 3),
        performance_pct=round(performance, 2) if performance is not None else None,
        same_day_adjustment_kw=round(adjustment, 3),
        coverage_pct=round(coverage * 100.0, 2),
        confidence=confidence,
    )
