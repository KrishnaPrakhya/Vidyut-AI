from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

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
            "injections": [i.to_dict() for i in self.injections],
            "created_at": self.created_at,
        }


class RunStore:
    def __init__(self, max_workers: int = 2) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._ready: dict[str, threading.Event] = {}

    def create(
        self, scenario: str, seed: int, ticks: int, params: dict[str, float]
    ) -> RunRecord:
        run_id = uuid.uuid4().hex[:12]
        record = RunRecord(
            run_id=run_id, scenario=scenario, seed=seed, ticks=ticks, params=params
        )
        with self._lock:
            self._runs[run_id] = record
            self._ready[run_id] = threading.Event()
        self._executor.submit(self._compute, run_id)
        return record

    def _compute(self, run_id: str) -> None:
        record = self._runs[run_id]
        record.status = "running"
        try:
            record.result = simulate(
                record.scenario,
                record.seed,
                record.ticks,
                record.params or None,
                record.injections or None,
            )
            record.status = "ready"
        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)
        finally:
            self._ready[run_id].set()

    def get(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    def wait_ready(self, run_id: str, timeout: float = 120.0) -> bool:
        event = self._ready.get(run_id)
        if event is None:
            return False
        return event.wait(timeout=timeout)

    def inject(self, run_id: str, injection: Injection) -> RunRecord | None:
        record = self._runs.get(run_id)
        if record is None:
            return None
        record.injections.append(injection)
        record.status = "pending"
        record.result = None
        with self._lock:
            self._ready[run_id] = threading.Event()
        self._executor.submit(self._compute, run_id)
        return record

    def list_runs(self) -> list[dict]:
        return [record.summary_stub() for record in self._runs.values()]


store = RunStore()
