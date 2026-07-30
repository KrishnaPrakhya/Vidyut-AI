from __future__ import annotations

from dataclasses import asdict, dataclass, field


def clock_of(tick: int) -> str:
    minutes = tick * 15
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass
class Notification:
    tick: int
    clock: str
    channel: str
    event_type: str
    dt_id: str
    feeder_id: str
    households: int
    reason_code: str
    message: str
    tariff_multiplier: float | None = None
    expected_reduction_kw: float | None = None
    window_minutes: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Outbox:
    notifications: list[Notification] = field(default_factory=list)

    def add(self, notification: Notification) -> None:
        self.notifications.append(notification)

    def pending(self) -> list[Notification]:
        return list(self.notifications)

    def clear(self) -> None:
        self.notifications = []
