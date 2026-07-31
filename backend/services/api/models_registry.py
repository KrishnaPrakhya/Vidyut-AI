from __future__ import annotations

import json
from pathlib import Path

from services.observability import engine_status

MODEL_DIR = Path(__file__).resolve().parents[2] / "ml" / "models"

EXPECTED = {
    "forecast": "forecast_eval.json",
}


def read_artifacts() -> dict:
    artifacts: dict[str, dict] = {}
    for key, filename in EXPECTED.items():
        path = MODEL_DIR / filename
        if not path.exists():
            artifacts[key] = {
                "trained": False,
                "artifact": filename,
                "message": f"{filename} not found; train the model to populate this panel",
            }
            continue
        try:
            with path.open() as f:
                payload = json.load(f)
        except json.JSONDecodeError as exc:
            artifacts[key] = {
                "trained": False,
                "artifact": filename,
                "message": f"{filename} is not valid JSON: {exc}",
            }
            continue
        artifacts[key] = {
            "trained": True,
            "runtime_ready": False,
            "evaluation_only": True,
            "runtime_message": (
                "evaluation is available; the live controller uses damped_trend until "
                "a deployable predictor is exported"
            ),
            "artifact": filename,
            **payload,
        }

    return {
        "model_dir": str(MODEL_DIR),
        "any_trained": any(a.get("trained") for a in artifacts.values()),
        "models": artifacts,
        "observability": engine_status(),
    }
