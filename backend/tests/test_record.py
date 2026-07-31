from __future__ import annotations

import json

from services.sim.record import build_recording
from services.sim.run import simulate

TICKS = 6


def test_recording_matches_the_websocket_tick_shape() -> None:
    recording = build_recording(simulate("heatwave", 42, TICKS))

    assert recording["meta"]["simulated"] is True
    assert recording["meta"]["ticks"] == TICKS
    assert len(recording["ticks"]) == TICKS

    for tick, payload in enumerate(recording["ticks"]):
        assert payload["t"] == tick
        assert set(payload["arms"]) == {"baseline", "vidyut"}
        arm = payload["arms"]["vidyut"]
        assert set(arm) == {"feeders", "dts", "topology", "metrics", "events"}
        assert len(arm["dts"]) == 60
        assert len(arm["feeders"]) == 3
        assert isinstance(arm["metrics"]["converged"], bool)


def test_recording_is_json_serialisable_and_carries_the_summary() -> None:
    recording = build_recording(simulate("heatwave", 42, TICKS))
    round_tripped = json.loads(json.dumps(recording))

    assert "unserved_kwh" in round_tripped["summary"]["deltas"]
    assert round_tripped["summary"]["arms"]["vidyut"]["critical_uptime_pct"] == 100.0
    assert isinstance(round_tripped["notifications"], list)


def test_energy_accounting_closes() -> None:
    result = simulate("heatwave", 42, TICKS)
    for arm in result.arms.values():
        assert arm.totals.energy_balance_error_kwh < 1e-6
