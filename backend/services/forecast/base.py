from __future__ import annotations

from typing import Protocol

import numpy as np


class Forecaster(Protocol):
    name: str

    def observe(self, tick: int, dt_kw: np.ndarray) -> None: ...

    def predict(self, tick: int, horizon: int) -> np.ndarray: ...
