from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

DEBT_WEIGHT = {"device": 1.0, "load_limit": 2.0, "disconnect": 4.0}


@dataclass
class CurtailmentRecord:
    tick: int
    household_id: str
    dt_id: str
    level: str
    kw: float
    minutes: float
    reason_code: str


@dataclass
class FairnessLedger:
    debt_min: dict[str, float] = field(default_factory=dict)
    records: list[CurtailmentRecord] = field(default_factory=list)

    def charge(
        self,
        tick: int,
        household_id: str,
        dt_id: str,
        level: str,
        kw: float,
        minutes: float,
        reason_code: str,
    ) -> float:
        weighted = minutes * DEBT_WEIGHT[level]
        self.debt_min[household_id] = self.debt_min.get(household_id, 0.0) + weighted
        self.records.append(
            CurtailmentRecord(tick, household_id, dt_id, level, kw, minutes, reason_code)
        )
        return weighted

    def debt_of(self, household_id: str) -> float:
        return self.debt_min.get(household_id, 0.0)

    def normalised_debt(self, household_id: str) -> float:
        if not self.debt_min:
            return 0.0
        peak = max(self.debt_min.values())
        if peak <= 0.0:
            return 0.0
        return self.debt_of(household_id) / peak


def gini(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    v = np.sort(np.clip(values.astype(float), 0.0, None))
    total = v.sum()
    if total <= 0.0:
        return 0.0
    n = v.size
    index = np.arange(1, n + 1)
    return float((2.0 * (index * v).sum()) / (n * total) - (n + 1.0) / n)
