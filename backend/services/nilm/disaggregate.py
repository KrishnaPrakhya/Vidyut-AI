from __future__ import annotations

import hashlib
import importlib.util
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
class NilmStatus:
    ready: bool
    reasons: list[str]
    appliances: list[str]
    required_appliances: list[str]
    runtime: str

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "reasons": self.reasons,
            "appliances": self.appliances,
            "required_appliances": self.required_appliances,
            "runtime": self.runtime,
        }


@dataclass
class DisaggregationResult:
    appliance_w: dict[str, np.ndarray]
    deferrable_share: float
    trained: bool


@dataclass
class VerificationResult:
    expected_reduction_kw: float
    realised_reduction_kw: float
    baseline_kw: float
    accuracy_pct: float


def load_eval() -> dict | None:
    if not EVAL_PATH.exists():
        return None
    try:
        with EVAL_PATH.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def model_status() -> NilmStatus:
    payload = load_eval()
    reasons: list[str] = []
    models = payload.get("appliances", {}) if payload else {}
    available = sorted(models)

    if payload is None:
        reasons.append("evaluation artifact is missing or invalid")
    if not WEIGHTS_PATH.exists():
        reasons.append("model weights are missing")
    elif payload and payload.get("deployment_ready"):
        expected_hash = payload.get("weights_sha256")
        if not expected_hash:
            reasons.append("model weights have no integrity hash")
        else:
            with WEIGHTS_PATH.open("rb") as handle:
                actual_hash = hashlib.file_digest(handle, "sha256").hexdigest()
            if actual_hash != expected_hash:
                reasons.append("model weights do not match the evaluation artifact")

    missing = sorted(set(DEFERRABLE_APPLIANCES) - set(available))
    if missing:
        reasons.append("deferrable appliance models are missing: " + ", ".join(missing))

    for appliance, metrics in models.items():
        mae = metrics.get("MAE")
        constant_mae = metrics.get("MAE_predicting_the_mean")
        f1 = metrics.get("F1")
        trivial_f1 = metrics.get("F1_always_on_baseline")
        if mae is None or constant_mae is None:
            reasons.append(f"{appliance} has no constant-power baseline evaluation")
        elif float(mae) >= float(constant_mae):
            reasons.append(f"{appliance} does not beat the constant-power baseline")
        if f1 is None or trivial_f1 is None:
            reasons.append(f"{appliance} has no trivial state-baseline evaluation")
        elif float(f1) <= float(trivial_f1):
            reasons.append(f"{appliance} does not beat the trivial state baseline")

    if payload and payload.get("deployment_ready") is False:
        reasons.extend(str(reason) for reason in payload.get("rejection_reasons", []))

    torch_available = importlib.util.find_spec("torch") is not None
    if not torch_available:
        reasons.append("PyTorch runtime is not installed")

    return NilmStatus(
        ready=not reasons,
        reasons=list(dict.fromkeys(reasons)),
        appliances=available,
        required_appliances=list(DEFERRABLE_APPLIANCES),
        runtime="pytorch" if torch_available else "unavailable",
    )


def is_trained() -> bool:
    return model_status().ready


def _network(torch, window: int):
    nn = torch.nn

    class Seq2Point(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv1d(1, 30, 10, padding="same"),
                nn.ReLU(),
                nn.Conv1d(30, 30, 8, padding="same"),
                nn.ReLU(),
                nn.Conv1d(30, 40, 6, padding="same"),
                nn.ReLU(),
                nn.Conv1d(40, 50, 5, padding="same"),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Conv1d(50, 50, 5, padding="same"),
                nn.ReLU(),
                nn.Dropout(0.2),
            )
            self.head = nn.Sequential(
                nn.Flatten(),
                nn.Linear(50 * window, 1024),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(1024, 1),
            )

        def forward(self, values):
            return self.head(self.features(values)).squeeze(-1)

    return Seq2Point()


def disaggregate(mains_w: np.ndarray, batch_size: int = 512) -> DisaggregationResult:
    status = model_status()
    if not status.ready:
        raise RuntimeError("NILM is unavailable: " + "; ".join(status.reasons))

    import torch

    values = np.asarray(mains_w, dtype=np.float32)
    if values.ndim != 1 or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("mains_w must be a finite, non-negative one-dimensional array")

    bundle = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=False)
    outputs: dict[str, np.ndarray] = {}
    for appliance, artifact in bundle.items():
        window = int(artifact["window"])
        if values.size < window:
            raise ValueError(f"mains_w needs at least {window} samples")
        windows = np.lib.stride_tricks.sliding_window_view(values, window)
        normalised = (
            windows - float(artifact["mains_mean"])
        ) / max(float(artifact["mains_std"]), 1e-6)
        model = _network(torch, window)
        model.load_state_dict(artifact["state_dict"])
        model.eval()
        predicted: list[np.ndarray] = []
        with torch.no_grad():
            for start in range(0, len(normalised), batch_size):
                batch = torch.from_numpy(normalised[start : start + batch_size]).unsqueeze(1)
                predicted.append(model(batch).numpy())
        watts = np.concatenate(predicted) * float(
            artifact["appliance_std"]
        ) + float(artifact["appliance_mean"])
        aligned = np.full(values.size, np.nan, dtype=float)
        half = window // 2
        aligned[half : half + len(watts)] = np.clip(watts, 0.0, None)
        outputs[appliance] = aligned

    deferrable = [outputs[name] for name in DEFERRABLE_APPLIANCES if name in outputs]
    if not deferrable:
        share = 0.0
    else:
        stacked = np.stack(deferrable)
        valid = np.all(np.isfinite(stacked), axis=0) & (values > 0)
        predicted_w = np.sum(stacked[:, valid], axis=0)
        aggregate_w = float(values[valid].sum())
        share = (
            float(np.clip(predicted_w.sum() / aggregate_w, 0.0, 1.0))
            if aggregate_w > 0
            else 0.0
        )
    return DisaggregationResult(outputs, share, True)


def dr_baseline_kw(history: np.ndarray, event_index: int, lookback_days: int = 5) -> float:
    values = np.asarray(history, dtype=float)
    if values.size == 0 or event_index < 0:
        return 0.0
    if values.ndim == 2:
        if event_index >= values.shape[1]:
            raise ValueError("event_index is outside the daily profile")
        candidates = values[-lookback_days:, event_index]
    elif values.ndim == 1:
        candidates = values[max(0, event_index - lookback_days) : event_index]
    else:
        raise ValueError("history must contain comparable daily values or daily profiles")
    candidates = candidates[np.isfinite(candidates)]
    if candidates.size == 0:
        return 0.0
    return float(np.sort(candidates)[-min(4, candidates.size) :].mean())


def verify_event(
    history: np.ndarray,
    event_index: int,
    observed_kw: float,
    expected_reduction_kw: float,
) -> VerificationResult:
    baseline = dr_baseline_kw(history, event_index)
    realised = max(baseline - observed_kw, 0.0)
    accuracy = (
        100.0 * realised / expected_reduction_kw
        if expected_reduction_kw > 0
        else 0.0
    )
    return VerificationResult(
        expected_reduction_kw=expected_reduction_kw,
        realised_reduction_kw=realised,
        baseline_kw=baseline,
        accuracy_pct=accuracy,
    )
