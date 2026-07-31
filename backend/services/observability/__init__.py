from services.observability.flexibility import (
    estimate_weather_opportunity,
    registered_availability_profile,
    registered_envelope,
)
from services.observability.verification import verify_event

__all__ = [
    "estimate_weather_opportunity",
    "registered_availability_profile",
    "registered_envelope",
    "verify_event",
]


def engine_status() -> dict:
    return {
        "ready": True,
        "component": "flexibility_assurance",
        "runtime": "numpy",
        "methods": {
            "registered": "controllable_device_nameplate",
            "estimated": "interval_baseline_temperature_association_v1",
            "verified": ["high_4_of_5", "ten_in_ten"],
        },
        "boundaries": [
            "does not identify individual appliances from aggregate meter data",
            "estimated opportunity is capped by registered capacity when provided",
            "issues no control commands",
        ],
    }
