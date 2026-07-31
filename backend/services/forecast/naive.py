from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TREND_WINDOW = 4
DAMPING = 0.75


@dataclass
class DampedTrendForecaster:
    n_dt: int
    name: str = "damped_trend"
    history: list[np.ndarray] = field(default_factory=list)

    def observe(self, tick: int, dt_kw: np.ndarray) -> None:
        self.history.append(np.asarray(dt_kw, dtype=float).copy())

    def predict(self, tick: int, horizon: int) -> np.ndarray:
        if not self.history:
            return np.zeros((self.n_dt, horizon))

        last = self.history[-1]
        window = self.history[-TREND_WINDOW:]
        if len(window) < 2:
            return np.repeat(last[:, None], horizon, axis=1)

        recent = np.stack(window, axis=1)
        steps = np.arange(recent.shape[1], dtype=float)
        slope = np.polyfit(steps, recent.T, deg=1)[0]

        offsets = np.cumsum(DAMPING ** np.arange(1, horizon + 1))
        forecast = last[:, None] + slope[:, None] * offsets[None, :]
        return np.clip(forecast, 0.0, None)
