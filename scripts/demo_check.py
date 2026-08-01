from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def request_json(url: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())


def request_bytes(url: str) -> tuple[str, bytes]:
    with urllib.request.urlopen(url, timeout=15) as response:
        return response.headers.get_content_type(), response.read()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fast pre-demo Vidyut readiness check")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--frontend", default="http://localhost:3000")
    parser.add_argument(
        "--core-only",
        action="store_true",
        help="Skip n8n readiness checks while developing locally",
    )
    args = parser.parse_args()
    api = args.api.rstrip("/")

    health = request_json(f"{api}/api/health")
    require(health.get("status") == "ok", "API health check failed")
    print("✓ API is healthy")

    database = health.get("database", {})
    require(database.get("configured") and database.get("reachable"), "database is not ready")
    print("✓ database is configured and reachable")

    if not args.core_only:
        automation = health.get("automation", {})
        require(
            all(
                automation.get(key)
                for key in (
                    "n8n_webhook_configured",
                    "callback_auth_configured",
                    "public_api_url_configured",
                )
            ),
            "n8n webhook, callback token, or public API URL is not configured",
        )
        print("✓ n8n webhook and both authenticated directions are configured")

    recordings = request_json(f"{api}/api/recordings").get("recordings", [])
    require(any(row.get("scenario") == "heatwave" for row in recordings), "heatwave recording is missing")
    print("✓ recorded heatwave is available")

    models = request_json(f"{api}/api/models")
    forecast = models.get("models", {}).get("forecast", {})
    require(forecast.get("trained"), "forecast evaluation artifact is missing")
    require(forecast.get("data", {}).get("real_measurements"), "forecast provenance is not real measurements")
    print("✓ forecast evaluation and real-data provenance are available")

    content_type, frontend = request_bytes(args.frontend.rstrip("/"))
    require("html" in content_type and b"VIDYUT" in frontend.upper(), "frontend landing page is not ready")
    print("✓ frontend landing page is serving")

    created = request_json(
        f"{api}/api/runs",
        {"scenario": "normal", "seed": 42, "ticks": 4, "carry_debt": False},
    )
    run_id = created["run_id"]
    for _ in range(120):
        state = request_json(f"{api}/api/runs/{run_id}")
        if state.get("status") == "ready":
            break
        if state.get("status") == "failed":
            raise RuntimeError(state.get("error") or "smoke simulation failed")
        time.sleep(0.5)
    else:
        raise RuntimeError("smoke simulation did not finish in 60 seconds")
    require(state.get("persisted"), "smoke run completed but was not persisted")
    summary = request_json(f"{api}/api/runs/{run_id}/summary")
    require(summary.get("ready") and set(summary.get("arms", {})) == {"baseline", "vidyut"}, "run summary is incomplete")
    report_type, report = request_bytes(f"{api}/api/runs/{run_id}/report")
    require(report_type == "application/pdf" and report.startswith(b"%PDF"), "audit PDF failed")
    print(f"✓ four-interval simulation, persistence, summary, and PDF passed ({run_id})")
    print("\nVidyut is demo-ready.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, urllib.error.URLError, TimeoutError) as exc:
        print(f"\n✗ demo check failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
