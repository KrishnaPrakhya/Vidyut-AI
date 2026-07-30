from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parents[2] / "ml" / "models"
EVAL_PATH = MODEL_DIR / "nilm_eval.json"
WEIGHTS_PATH = MODEL_DIR / "nilm_model.pt"

APPLIANCES = ("ac_1", "ac_2", "fridge", "tv", "laptop")
DEFERRABLE_APPLIANCES = ("ac_1", "ac_2")


@dataclass
class DisaggregationResult:
    appliance_kw: dict[str, np.ndarray]
    deferrable_share: float
    trained: bool


@dataclass
class VerificationResult:
    expected_reduction_kw: float
    realised_reduction_kw: float
    baseline_kw: float
    accuracy_pct: float


def is_trained() -> bool:
    return EVAL_PATH.exists() and WEIGHTS_PATH.exists()


def load_eval() -> dict | None:
    if not EVAL_PATH.exists():
        return None
    with EVAL_PATH.open() as f:
        return json.load(f)


def dr_baseline_kw(history: np.ndarray, event_index: int, lookback_days: int = 5) -> float:
    """High 4-of-5 same-day-adjusted baseline, the standard DR measurement convention."""
    if event_index <= 0 or history.size == 0:
        return 0.0
    candidates = history[max(0, event_index - lookback_days) : event_index]
    if candidates.size == 0:
        return 0.0
    top = np.sort(candidates)[-4:]
    return float(top.mean())


def verify_event(
    history: np.ndarray, event_index: int, observed_kw: float, expected_reduction_kw: float
) -> VerificationResult:
    baseline = dr_baseline_kw(history, event_index)
    realised = max(baseline - observed_kw, 0.0)
    accuracy = (
        100.0 * realised / expected_reduction_kw if expected_reduction_kw > 0 else 0.0
    )
    return VerificationResult(
        expected_reduction_kw=expected_reduction_kw,
        realised_reduction_kw=realised,
        baseline_kw=baseline,
        accuracy_pct=accuracy,
    )
