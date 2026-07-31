from __future__ import annotations

TICK_MINUTES = 15
TICK_HOURS = TICK_MINUTES / 60.0


def clock_of(tick: int) -> str:
    minutes = tick * TICK_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
