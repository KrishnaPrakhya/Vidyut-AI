from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from services.dispatch.outbox import Notification, Outbox

WEBHOOK_ENV_VAR = "N8N_WEBHOOK_URL"
TIMEOUT_SECONDS = 4.0
MAX_ATTEMPTS = 3
RETRY_BASE_SECONDS = 0.25


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
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": payload["idempotency_key"],
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        response.read()


def dispatch(
    run_id: str,
    outbox: Outbox,
    batch_size: int = 50,
    notification_ids: list[int] | None = None,
) -> DispatchReport:
    notifications = outbox.pending()
    url = webhook_url()
    if url is None:
        return DispatchReport(configured=False, attempted=len(notifications), delivered=0)

    delivered = 0
    for start in range(0, len(notifications), batch_size):
        batch: list[Notification] = notifications[start : start + batch_size]
        rows = []
        for offset, notification in enumerate(batch):
            row = notification.to_dict()
            index = start + offset
            if notification_ids is not None and index < len(notification_ids):
                row["notification_id"] = notification_ids[index]
            rows.append(row)
        payload = {
            "run_id": run_id,
            "batch_index": start // batch_size,
            "notifications": rows,
            "idempotency_key": (
                f"{run_id}:" + ",".join(
                    str(row.get("notification_id", start + offset))
                    for offset, row in enumerate(rows)
                )
            ),
        }
        error: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                _post(url, payload)
                error = None
                break
            except urllib.error.HTTPError as exc:
                error = exc
                if 400 <= exc.code < 500:
                    break
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                error = exc
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(RETRY_BASE_SECONDS * (2**attempt))
        if error is not None:
            return DispatchReport(
                configured=True,
                attempted=len(notifications),
                delivered=delivered,
                error=str(error),
            )
        delivered += len(batch)
        outbox.acknowledge(len(batch))

    return DispatchReport(configured=True, attempted=len(notifications), delivered=delivered)
