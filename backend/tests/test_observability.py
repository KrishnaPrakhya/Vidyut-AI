from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from services.observability.flexibility import (
    estimate_weather_opportunity,
    registered_envelope,
)
from services.observability.verification import verify_event


def test_registered_envelope_uses_only_noncritical_controllable_devices() -> None:
    device = lambda kind, rated_kw, controllable: SimpleNamespace(
        kind=kind, rated_kw=rated_kw, controllable=controllable
    )
    households = [
        SimpleNamespace(
            tier="standard",
            devices=[device("ac", 1.5, True), device("pump", 0.8, False)],
        ),
        SimpleNamespace(
            tier="critical",
            devices=[device("water_heater", 2.0, True)],
        ),
        SimpleNamespace(
            tier="essential",
            devices=[device("pump", 0.75, True)],
        ),
    ]

    result = registered_envelope(households)

    assert result.capacity_kw == pytest.approx(2.25)
    assert result.households == 2
    assert result.devices == 2
    assert result.capacity_by_kind_kw == {"ac": 1.5, "pump": 0.75}
    assert result.source == "registered"


def test_weather_opportunity_requires_and_finds_a_real_association() -> None:
    intervals = np.array([21, 22, 24, 27, 30, 32, 28, 24], dtype=float)
    ambient = np.stack([intervals + offset for offset in range(7)])
    base = np.array([8, 8, 9, 10, 11, 12, 11, 9], dtype=float)
    aggregate = base[None, :] + 1.2 * np.maximum(ambient - 24.0, 0.0)

    result = estimate_weather_opportunity(
        aggregate,
        ambient,
        registered_capacity_kw=5.0,
    )

    assert result.ready is True
    assert result.confidence in {"medium", "high"}
    assert result.estimated_peak_kw > 0
    assert result.actionable_peak_kw is not None
    assert result.actionable_peak_kw <= 5.0
    assert max(result.actionable_profile_kw or []) <= 5.0
    assert result.source == "estimated"


def test_weather_opportunity_fails_closed_without_temperature_variation() -> None:
    aggregate = np.full((5, 8), 10.0)
    ambient = np.full((5, 8), 28.0)

    result = estimate_weather_opportunity(aggregate, ambient)

    assert result.ready is False
    assert result.confidence == "unavailable"
    assert any("temperature span" in reason for reason in result.reasons)


def test_high_four_of_five_verification_reports_energy_and_power() -> None:
    history = np.stack([np.full(8, value) for value in (100, 110, 120, 130, 140)])
    observed = np.full(8, 125.0)
    observed[4:6] = 105.0

    result = verify_event(history, observed, 4, 6, 20.0)

    assert result.selected_days == [1, 2, 3, 4]
    assert result.baseline_average_kw == pytest.approx(125.0)
    assert result.realised_reduction_kw == pytest.approx(20.0)
    assert result.realised_reduction_kwh == pytest.approx(10.0)
    assert result.performance_pct == pytest.approx(100.0)
    assert result.source == "verified"


def test_verification_rejects_insufficient_history() -> None:
    with pytest.raises(ValueError, match="at least 4"):
        verify_event(np.ones((3, 8)), np.ones(8), 4, 6, 1.0)
