# Vidyut — frontend contract

Everything the UI needs from the backend. Every shape here was captured from a running server,
not written from memory. Live samples sit in `docs/api-samples/`, and the full machine-readable
spec is `docs/api-samples/openapi.json`.

Base URL in development is `http://localhost:8000`. CORS is open to all origins.

---

## 1. Ground rules

**Every number on screen must come from a simulation output or an artifact file.** Nothing is
hardcoded in the UI. If a value is missing, render an explicit empty state rather than a
placeholder number.

**The words "first", "world's first", "only" and "nobody does this" must not appear** anywhere in
UI copy.

**Label it a simulation.** The About page must state that this is a simulated network, not
connected to any live utility system.

**Two arms, always side by side.** `baseline` is current utility practice; `vidyut` is the system
under test. They run on identical demand under an identical seed. Never show one without the other.

---

## 2. Lifecycle

Runs are **simulated up front, then replayed**. A `POST` computes all 96 ticks for both arms
(roughly 20 seconds), and the WebSocket then streams the stored result at playback speed. Playback
never blocks on computation.

```
POST /api/runs                    -> { run_id, status: "pending" }
GET  /api/runs/{id}               -> poll until status === "ready"
WS   /ws/runs/{id}?speed=4        -> one message per tick
GET  /api/runs/{id}/summary       -> final metrics for both arms + deltas
```

`status` is one of `pending`, `running`, `ready`, `failed`. Poll at ~500 ms. On `failed`, read
`error`.

The WebSocket can be opened before the run is ready; it sends `{"type":"status"}` immediately and
waits, then sends `ready` followed by ticks.

---

## 3. REST endpoints

### `GET /api/health`

```json
{ "status": "ok", "scenarios": ["ev_surge", "heatwave", "normal"], "database": { "status": "not_configured" } }
```

`database.status` is `not_configured`, `connected` or `unreachable`. **The app must work when it is
not connected** — history and household endpoints simply return 503, everything else is unaffected.

### `POST /api/runs`

```json
{
  "scenario": "heatwave",
  "seed": 42,
  "ticks": 96,
  "carry_debt": true,
  "params": {
    "ami_penetration": 0.55,
    "connected_device_penetration": 0.25,
    "ev_penetration": 0.08,
    "critical_share": 0.02,
    "essential_share": 0.18,
    "peak_multiplier": 1.42,
    "tariff_rs_per_kwh": 7.5
  }
}
```

All of `params` is optional; omitted keys use the scenario default. These are the header sliders.
Out-of-range values return **422** — surface the message, do not clamp silently.

`carry_debt` controls whether the fairness ledger from previous runs carries into this one. Leave
`true` for the multi-day story.

Returns `{ "run_id": "28b6aab49a6a", "status": "pending" }`.

### `GET /api/runs/{id}`

Run status without the heavy payload. Fields worth surfacing: `status`, `error`, `generation`
(increments on each re-simulation — use it to discard stale WebSocket frames), `injections`,
`opening_debt_households`, `persisted`.

### `GET /api/runs/{id}/summary`

`{ ready, arms: { baseline, vidyut }, deltas }`. Each arm carries the run totals. **Deltas are
`vidyut - baseline`**, so negative is an improvement for cost-like metrics.

Key fields per arm:

| field | meaning |
|---|---|
| `served_kwh`, `demanded_kwh`, `unserved_kwh` | energy accounting; `demanded = served + unserved` |
| `unserved_cost_rs` | unserved energy at the scenario tariff |
| `homes_dark_minutes`, `peak_homes_dark` | de-energised households |
| `critical_uptime_pct` | must read 100.000 for vidyut |
| `max_trafo_loading_pct`, `peak_kva` | worst transformer, peak served |
| `mean_spread_pct`, `max_spread_pct`, `spread_series` | feeder utilisation spread |
| `total_losses_kwh`, `losses_pct_of_delivered` | **show the percentage, not the absolute** |
| `gini`, `gini_affected`, `max_household_burden_min`, `households_curtailed` | fairness |
| `minutes_by_level` | `{device, load_limit, disconnect}` household-minutes |
| `addressable_share_of_load` | fraction of load that is controllable |
| `nonconverged_ticks` | power flow failures; non-zero is a real outcome, show it |

**Two traps.** Vidyut serves *more* energy than baseline, so its `peak_kva` and `total_losses_kwh`
are **higher**. That is serving more load, not performing worse — always pair losses with
`losses_pct_of_delivered`. And baseline scores *better* on `gini_affected` because de-energising a
whole transformer harms everyone on it equally; show `minutes_by_level` alongside it so the reader
sees severity, not just spread.

### `POST /api/runs/{id}/inject`

Judge triggers. Re-simulates from `from_tick` onward and increments `generation`.

```json
{ "type": "heatwave", "magnitude": 0.6, "from_tick": 40, "dt_id": null }
```

`type` is `heatwave`, `ev_surge`, `cloud_cover` or `dt_fault`. `magnitude` 0–3. `dt_id` only
applies to `dt_fault`; null picks the most loaded transformer.

Keyboard shortcuts required by the brief: **H** heatwave, **E** EV surge, **C** cloud cover,
**F** fault, **R** reset.

After injecting, the run returns to `pending`. Reconnect the WebSocket once it is `ready` again.

### `GET /api/runs/{id}/events`

Paginated decision log. Query: `arm` (default `vidyut`), `tier`, `dt_id`, `offset`, `limit`.

```json
{
  "t": 71, "tier": 3, "action": "rotational_disconnect", "target": "F1-DT07",
  "kw": 2.11, "households": 2, "reason_code": "LAST_RESORT_ROTATION",
  "detail": "F1-DT07 measured 101% after flexibility exhausted; 2 standard-tier households rotated off for 30 minutes, lowest accumulated debt first"
}
```

**`detail` is always populated and is written for a human.** Render it verbatim in the event feed;
do not paraphrase or re-template it.

Tiers: `0` price signal or baseline trip, `1` steady state (shifting, reconfiguration),
`2` pre-emptive (device curtailment, load limit), `3` last resort (rotational disconnect).

### `GET /api/runs/{id}/report`

Returns `application/pdf`. Link to it; do not parse it.

### `GET /api/models`

Model artifacts. `models.forecast` carries the trained metrics.

```json
{
  "any_trained": true,
  "models": {
    "forecast": {
      "trained": true,
      "evaluation_only": true,
      "runtime_ready": false,
      "models": {
        "seasonal_naive":    { "MASE": 1.0635, "MAPE": 60.5636 },
        "chronos_zeroshot":  { "MASE": 0.8748, "MAPE": 45.7893 },
        "chronos_finetuned": { "MASE": 0.8579, "MAPE": 43.2293 }
      },
      "cold_start": { "history_days": 14, "lgbm_from_scratch": { "MASE": 0.9322 }, "chronos_finetuned": { "MASE": 0.8238 } },
      "by_scale": { "chronos_finetuned": { "transformer_scale": { "MASE": 0.9136, "series": 5 } } },
      "data": { "country": "India", "real_measurements": true, "synthetic_training_data": false }
    }
  }
}
```

Three rules for the models page:

1. **If `trained` is false, render an explicit "not yet trained" state.** Never fabricate numbers.
2. **`trained` and `runtime_ready` are different.** `evaluation_only: true` means the model was
   evaluated but is not wired for live inference. Say so rather than implying it is running.
3. **Always print `series` next to a per-scale MASE.** `transformer_scale` rests on 5 series and
   that must be visible.

Lower MASE is better; below 1.0 beats the seasonal-naive baseline.

### `GET /api/observability/status`

The flexibility assurance engine. It replaces appliance disaggregation and **does not claim
appliance detection** — its own `boundaries` array says so. Render those boundaries on the page.

Five quantities that must never be conflated in the UI:

| quantity | meaning |
|---|---|
| `registered` | nameplate capacity of controllable devices; critical tier excluded |
| `estimated` | weather-association estimate, with `confidence` and `coverage_pct` |
| `actionable` | estimated **capped by** registered. **`null` when no registry is supplied** |
| `verified` | measured after an event (high-4-of-5, 10-in-10) |
| `simulated` | what the simulation itself did |

When `actionable_*` is `null`, show "not actionable without a device registry". Do not fall back to
the estimate.

### Database-backed endpoints

`GET /api/households/{id}`, `GET /api/fairness/leaderboard`, `GET /api/runs/{id}/flexibility`.

These return **503** when `DATABASE_URL` is not configured. Treat that as a normal state and hide
the panel rather than showing an error.

`GET /api/households/{id}` is the strongest screen for the per-household auditability claim. Each
history entry carries `standing_percentile_at_decision` and a pre-written `explanation`:

> At 20:30, a connected appliance was briefly curtailed for 30 minutes. Transformer F1-DT17 was
> forecast to reach 153 kW against a safe limit of 137 kW. You had already borne more than most
> homes on your transformer, so you were near the back of the queue.

Render it verbatim.

---

## 4. WebSocket

`ws://localhost:8000/ws/runs/{run_id}?speed=4&from_tick=0`

`speed` is ticks per second (default 4, so a 96-tick day plays in ~24 s). Message types arrive in
order: `status` → `ready` → `tick` × N → `complete`, or `error`.

**One message per tick carrying both arms.** Roughly 11 KB per tick. Do not expect per-entity
messages.

```json
{
  "type": "tick",
  "t": 0,
  "clock": "00:00",
  "arms": {
    "baseline": {
      "feeders": [{ "id": "F1", "loading_pct": 18.3, "losses_kw": 2.3 }],
      "dts": [{ "id": "F1-DT01", "loading_pct": 19.0, "energized": true, "households_dark": 0 }],
      "topology": { "tie_switches": [{ "id": "TS-F1-F2", "closed": false }] },
      "metrics": {
        "converged": true, "peak_kva": 2145.9, "spread_pct": 4.0, "losses_kw": 5.27,
        "homes_dark": 0, "critical_uptime_pct": 100.0, "unserved_kwh": 0.0,
        "gini": 0.0, "max_trafo_loading_pct": 29.3
      },
      "events": []
    },
    "vidyut": { "...same shape..." }
  },
  "forecast": {
    "model": "damped_trend", "runtime_ready": true, "dt_id": "F1-DT17",
    "horizon_kw": [44.6, 44.6, 44.7, 44.8], "safe_limit_kw": 136.8, "rating_kw": 152.0
  }
}
```

Fixed cardinality: **3 feeders, 60 DTs, 3 tie switches**, per arm, every tick. DT ids are
`F{1..3}-DT{01..20}`.

`forecast` is top-level (Vidyut's view, not per-arm) and may be `null`. Chart `horizon_kw` with
`safe_limit_kw` as a reference line — the breach of that line is what triggers Tier 2.

`metrics.converged: false` means the power flow did not solve. That is a **valid outcome meaning
the network collapsed**, expected in the baseline arm under stress. Render it as a distinct state,
not an error, and treat that tick's loading values as unreliable.

`clock` is `HH:MM` over a 24-hour day; tick `t` covers 15 minutes, 96 ticks total.

**Use `generation` to discard stale frames.** After an injection the run re-simulates; frames from
the previous generation must be dropped.

---

## 5. Offline replay

`data/recorded/{scenario}-{seed}.json` for `normal`, `heatwave`, `ev_surge` at seed 42 (~1 MB each).

```json
{
  "meta": { "scenario": "heatwave", "seed": 42, "ticks": 96, "arms": ["baseline","vidyut"], "simulated": true },
  "ticks": [ /* exactly the WebSocket tick payload, minus "type" */ ],
  "summary": { "arms": { "baseline": {}, "vidyut": {} }, "deltas": {} },
  "notifications": []
}
```

`?replay=recorded` **must render a full demo with the API down** — this is a hard requirement and
the venue-wifi safety net. Because `ticks[]` is byte-identical to the WebSocket payload, the same
render path serves both: swap the transport, keep the components.

Build against this first.

---

## 6. Screens

**`/` Console.** Header: scenario selector, seed, penetration sliders, play/pause/speed, reset.
Body: split A/B, baseline left, Vidyut right. Right rail: metrics table with live deltas, event
feed, forecast chart with the safe-limit line. Footer: timeline scrubber. Judge triggers as large
buttons *and* keyboard shortcuts.

**Hero visual: three feeder utilisation bars, before and after.** Build this first — it is the
thesis in one image and belongs on the submission thumbnail. Feeders run roughly 85/81/71% at peak;
the >100% numbers live at DT level.

**`/models`.** Three-bar eval chart, cold-start comparison, and the observability panel with its
boundaries. All from `/api/models` and `/api/observability/status`, with an honest empty state.

**`/runs/[id]/report`** printable. **`/about`** scope, prior art, limitations.

Copy required on the About page and in the addressability tooltip: *"smart meters provide
visibility, connected devices provide control."*

---

## 7. Colour and state

Loading: green under 90%, amber 90–100%, red over 100%. De-energised DTs greyed, not red — being
switched off is a different state from being overloaded. Non-converged ticks need their own
treatment again.

Animate the 3D twin via refs in `useFrame`, never per-frame React state. Build the **2D SVG
schematic first** (`?twin=2d`) — it is the safety net and reads better on a projector.

---

## 8. Getting a backend up

```bash
cd backend
uv sync
.venv/Scripts/python.exe -m uvicorn services.api.main:app --reload --port 8000
```

Interactive docs at `http://localhost:8000/docs`. Postgres is optional; without it the three
database endpoints return 503 and nothing else changes.

To regenerate the recorded fixtures:

```bash
.venv/Scripts/python.exe -m services.sim.record --all --seed 42
```
