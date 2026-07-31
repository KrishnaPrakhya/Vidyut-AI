from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from services.dispatch.outbox import Notification, Outbox

WEBHOOK_ENV_VAR = "N8N_WEBHOOK_URL"
TIMEOUT_SECONDS = 4.0


@dataclass
class DispatchReport:
    configured: bool
    attempted: int
    delivered: int
    error: str | None = None

    @property
    def status(self) -> str:
        if not self.configured:
            return "not_configured"
        if self.error:
            return "unreachable"
        return "delivered"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "configured": self.configured,
            "attempted": self.attempted,
            "delivered": self.delivered,
            "error": self.error,
        }


def webhook_url() -> str | None:
    url = os.environ.get(WEBHOOK_ENV_VAR, "").strip()
    return url or None


def _post(url: str, payload: dict) -> None:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        response.read()


def dispatch(run_id: str, outbox: Outbox, batch_size: int = 50) -> DispatchReport:
    notifications = outbox.pending()
    url = webhook_url()
    if url is None:
        return DispatchReport(configured=False, attempted=len(notifications), delivered=0)

    delivered = 0
    for start in range(0, len(notifications), batch_size):
        batch: list[Notification] = notifications[start : start + batch_size]
        payload = {
            "run_id": run_id,
            "batch_index": start // batch_size,
            "notifications": [n.to_dict() for n in batch],
        }
        try:
            _post(url, payload)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return DispatchReport(
                configured=True,
                attempted=len(notifications),
                delivered=delivered,
                error=str(exc),
            )
        delivered += len(batch)
        outbox.acknowledge(len(batch))

    return DispatchReport(configured=True, attempted=len(notifications), delivered=delivered)
