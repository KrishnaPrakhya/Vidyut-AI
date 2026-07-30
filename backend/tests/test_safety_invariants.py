from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.sim.run import simulate_arm

NILM_DIR = Path(__file__).resolve().parents[1] / "services" / "nilm"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_nilm_does_not_import_actuation() -> None:
    for path in NILM_DIR.rglob("*.py"):
        for module in _imported_modules(path):
            assert not module.startswith("services.actuation"), (
                f"{path.name} imports {module}; NILM is observability and must never actuate"
            )


@pytest.mark.parametrize("seed", [1, 7, 13, 42, 99])
@pytest.mark.parametrize("scenario", ["heatwave", "ev_surge"])
def test_critical_tier_is_never_disconnected(scenario: str, seed: int) -> None:
    result = simulate_arm("vidyut", scenario, seed)
    world = result.world

    for command in world.actuation.commands:
        if command.level in ("disconnect", "load_limit"):
            assert world.households[command.household_id].tier != "critical"

    for record in world.ledger.records:
        if record.level in ("disconnect", "load_limit"):
            assert world.households[record.household_id].tier != "critical"

    assert world.critical_household_dark_minutes == 0.0
    assert result.totals.critical_uptime_pct == pytest.approx(100.0)


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(100))
def test_critical_tier_property_sweep(seed: int) -> None:
    world = simulate_arm("vidyut", "heatwave", seed).world
    assert world.critical_household_dark_minutes == 0.0
    for command in world.actuation.commands:
        if command.level == "disconnect":
            assert world.households[command.household_id].tier != "critical"


def test_load_limit_requires_capable_meter() -> None:
    world = simulate_arm("vidyut", "heatwave", 42).world
    for command in world.actuation.commands:
        if command.level == "load_limit":
            household = world.households[command.household_id]
            assert household.ami and household.meter_load_limit_supported


def test_device_curtailment_requires_connected_device() -> None:
    world = simulate_arm("vidyut", "heatwave", 42).world
    for command in world.actuation.commands:
        if command.level == "device":
            assert world.households[command.household_id].has_connected_device


def test_price_signal_only_targets_non_addressable() -> None:
    world = simulate_arm("vidyut", "heatwave", 42).world
    for command in world.actuation.commands:
        if command.level == "price_signal":
            assert not world.households[command.household_id].addressable
