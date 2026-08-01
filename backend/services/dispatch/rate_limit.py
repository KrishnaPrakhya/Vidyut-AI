from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0


class DigestRateLimiter:
    """Small, privacy-safe limiter for a single-instance hackathon deployment."""

    def __init__(self, window_seconds: int = 3600) -> None:
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _key(namespace: str, value: str) -> str:
        digest = hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()
        return f"{namespace}:{digest}"

    def check(
        self,
        client_ip: str,
        recipient_email: str,
        now: float | None = None,
    ) -> RateLimitResult:
        current = time.monotonic() if now is None else now
        rules = (
            (self._key("ip", client_ip or "unknown"), 10),
            (self._key("email", recipient_email), 3),
        )
        with self._lock:
            for key, _ in rules:
                queue = self._events[key]
                while queue and current - queue[0] >= self.window_seconds:
                    queue.popleft()
            blocked = [
                (key, limit)
                for key, limit in rules
                if len(self._events[key]) >= limit
            ]
            if blocked:
                retry_after = max(
                    1,
                    int(
                        max(
                            self.window_seconds
                            - (current - self._events[key][0])
                            for key, _ in blocked
                        )
                    ),
                )
                return RateLimitResult(False, retry_after)
            for key, _ in rules:
                self._events[key].append(current)
        return RateLimitResult(True)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


operator_digest_limiter = DigestRateLimiter()
