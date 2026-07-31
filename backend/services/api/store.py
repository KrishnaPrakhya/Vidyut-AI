from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from services.persistence.engine import session_scope
from services.persistence.repository import load_fairness_balances, save_run
from services.sim.injection import Injection
from services.sim.run import RunResult, simulate
from services.sim.scenario import N_TICKS


@dataclass
class RunRecord:
    run_id: str
    scenario: str
    seed: int
    ticks: int
    params: dict[str, float]
    status: str = "pending"
    error: str | None = None
    carry_debt: bool = True
    opening_debt_households: int = 0
    persisted: bool = False
    persistence_error: str | None = None
    generation: int = 0
    result: RunResult | None = None
    injections: list[Injection] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def summary_stub(self) -> dict:
        return {
            "run_id": self.run_id,
            "scenario": self.scenario,
            "seed": self.seed,
            "ticks": self.ticks,
            "params": self.params,
            "status": self.status,
            "error": self.error,
            "carry_debt": self.carry_debt,
            "opening_debt_households": self.opening_debt_households,
            "persisted": self.persisted,
            "persistence_error": self.persistence_error,
            "generation": self.generation,
            "injections": [i.to_dict() for i in self.injections],
            "created_at": self.created_at,
        }


class RunStore:
    def __init__(self, max_workers: int = 2, max_runs: int = 20) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._ready: dict[tuple[str, int], threading.Event] = {}
        self._max_runs = max_runs

    def create(
        self,
        scenario: str,
        seed: int,
        ticks: int,
        params: dict[str, float],
        carry_debt: bool = True,
    ) -> RunRecord:
        run_id = uuid.uuid4().hex[:12]
        record = RunRecord(
            run_id=run_id,
            scenario=scenario,
            seed=seed,
            ticks=ticks,
            params=params,
            carry_debt=carry_debt,
        )
        with self._lock:
            self._evict()
            self._runs[run_id] = record
            event = threading.Event()
            self._ready[(run_id, record.generation)] = event
        self._executor.submit(self._compute, run_id, record.generation, event)
        return record

    def _compute(
        self, run_id: str, generation: int, event: threading.Event
    ) -> None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None or record.generation != generation:
                event.set()
                return
            record.status = "running"
            injections = list(record.injections)
        try:
            opening_debt = self._opening_debt(record)
            result = simulate(
                record.scenario,
                record.seed,
                record.ticks,
                record.params or None,
                injections or None,
                opening_debt,
            )
            with self._lock:
                current = self._runs.get(run_id)
                if current is None or current.generation != generation:
                    return
                current.result = result
                current.opening_debt_households = len(opening_debt)
            self._persist(record, result)
            with self._lock:
                if record.generation == generation:
                    record.status = "ready"
        except Exception as exc:
            with self._lock:
                if record.generation == generation:
                    record.status = "failed"
                    record.error = str(exc)
        finally:
            event.set()

    def _opening_debt(self, record: RunRecord) -> dict[str, float]:
        if not record.carry_debt:
            return {}
        try:
            with session_scope() as session:
                return load_fairness_balances(
                    session, exclude_run_id=record.run_id
                )
        except Exception as exc:
            record.persistence_error = f"could not load opening balances: {exc}"
            return {}

    def _persist(self, record: RunRecord, result: RunResult) -> None:
        try:
            with session_scope() as session:
                if session is None:
                    return
                save_run(session, record, result)
            record.persisted = True
        except Exception as exc:
            record.persistence_error = str(exc)

    def get(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    def wait_ready(self, run_id: str, timeout: float = 120.0) -> bool:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return False
            event = self._ready.get((run_id, record.generation))
            if event is None:
                return False
        return event.wait(timeout=timeout)

    def inject(self, run_id: str, injection: Injection) -> RunRecord | None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None or record.status != "ready":
                return None
            record.generation += 1
            record.injections.append(injection)
            record.status = "pending"
            record.result = None
            record.error = None
            record.persisted = False
            event = threading.Event()
            self._ready[(run_id, record.generation)] = event
        self._executor.submit(self._compute, run_id, record.generation, event)
        return record

    def list_runs(self) -> list[dict]:
        return [record.summary_stub() for record in self._runs.values()]

    def _evict(self) -> None:
        if len(self._runs) < self._max_runs:
            return
        for run_id, record in list(self._runs.items()):
            if record.status in {"ready", "failed"}:
                del self._runs[run_id]
                for key in [key for key in self._ready if key[0] == run_id]:
                    del self._ready[key]
                return


store = RunStore()
