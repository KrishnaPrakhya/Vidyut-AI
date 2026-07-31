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
    device_kind: str | None = None


@dataclass
class FairnessLedger:
    debt_min: dict[str, float] = field(default_factory=dict)
    opening_debt: dict[str, float] = field(default_factory=dict)
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
        device_kind: str | None = None,
    ) -> float:
        weighted = minutes * DEBT_WEIGHT[level]
        self.debt_min[household_id] = self.debt_min.get(household_id, 0.0) + weighted
        self.records.append(
            CurtailmentRecord(
                tick,
                household_id,
                dt_id,
                level,
                kw,
                minutes,
                reason_code,
                device_kind,
            )
        )
        return weighted

    def accrued_of(self, household_id: str) -> float:
        return self.debt_min.get(household_id, 0.0)

    def debt_of(self, household_id: str) -> float:
        return self.opening_debt.get(household_id, 0.0) + self.debt_min.get(household_id, 0.0)

    def normalised_debt(self, household_id: str) -> float:
        standing = self.debt_of(household_id)
        if standing <= 0.0:
            return 0.0
        peak = max(
            self.debt_of(hh_id)
            for hh_id in set(self.opening_debt) | set(self.debt_min)
        )
        if peak <= 0.0:
            return 0.0
        return standing / peak


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
