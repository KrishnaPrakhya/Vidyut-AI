from __future__ import annotations

import ast
from pathlib import Path

from services.persistence.engine import check, database_url, session_scope
from services.persistence.models import Base
from services.persistence.repository import load_fairness_balances

SIM_DIR = Path(__file__).resolve().parents[1] / "services" / "sim"
ACTUATION_DIR = Path(__file__).resolve().parents[1] / "services" / "actuation"


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_simulation_does_not_import_persistence() -> None:
    for directory in (SIM_DIR, ACTUATION_DIR):
        for path in directory.rglob("*.py"):
            for module in _imports(path):
                assert not module.startswith("services.persistence"), (
                    f"{path.name} imports {module}; the simulation must stay pure and "
                    f"runnable with no database"
                )


def test_simulation_imports_no_database_driver() -> None:
    forbidden = ("sqlalchemy", "psycopg", "asyncpg", "alembic")
    for path in SIM_DIR.rglob("*.py"):
        for module in _imports(path):
            assert not any(module.startswith(name) for name in forbidden), (
                f"{path.name} imports {module}"
            )


def test_check_reports_not_configured_without_a_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    status = check()
    assert status.status == "not_configured"
    assert status.configured is False


def test_check_reports_unreachable_for_a_dead_host(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://vidyut:vidyut@127.0.0.1:1/vidyut"
    )
    status = check()
    assert status.status == "unreachable"
    assert status.error


def test_session_scope_yields_none_without_a_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with session_scope() as session:
        assert session is None


def test_fairness_balances_are_empty_without_a_session() -> None:
    assert load_fairness_balances(None) == {}


def test_every_table_has_a_primary_key() -> None:
    for table in Base.metadata.tables.values():
        assert table.primary_key.columns, f"{table.name} has no primary key"


def test_audit_spine_tables_exist() -> None:
    required = {
        "run",
        "run_arm_total",
        "tick_metric",
        "dt_tick_reading",
        "feeder_tick_reading",
        "control_action",
        "household_impact",
        "fairness_ledger",
        "fairness_ledger_history",
        "notification",
        "notification_delivery",
        "household",
        "device",
    }
    assert required <= set(Base.metadata.tables)


def test_fairness_ledger_is_keyed_by_household_not_run() -> None:
    ledger = Base.metadata.tables["fairness_ledger"]
    primary_key = {column.name for column in ledger.primary_key.columns}
    assert primary_key == {"household_id"}
    assert "run_id" not in ledger.columns


def test_household_impact_records_standing_relative_to_neighbours() -> None:
    impact = Base.metadata.tables["household_impact"]
    assert "standing_percentile" in impact.columns
    assert "reason_code" in impact.columns
