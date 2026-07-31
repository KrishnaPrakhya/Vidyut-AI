# Vidyut API endpoint guide

This guide explains the backend from a frontend developer's point of view. The exact field definitions and limits are in `frontend-context.json`, while copy-paste payloads are in `api-examples.json`.

## The normal frontend sequence

1. Check the backend with `GET /api/health`.
2. Load the scenario options with `GET /api/scenarios`.
3. Create a simulation with `POST /api/runs`.
4. Poll `GET /api/runs/{run_id}` until its status becomes `ready` or `failed`.
5. Load the summary, flexibility and event endpoints for that run.
6. Use the WebSocket only when animated tick-by-tick playback is needed.

## Service and capability endpoints

### `GET /api/health`

Asks: “Is the backend working?”

Call this when the application opens and occasionally during a long session. It reports whether the API is alive, which scenarios are installed, and whether PostgreSQL can be reached.

Frontend use:

- Show an online/offline backend indicator.
- Show database-dependent features as unavailable when `database.reachable` is false.
- Do not disable simulation merely because the database is unavailable; simulation can continue in memory.

### `GET /api/scenarios`

Asks: “Which simulation situations can the user choose?”

It currently returns `normal`, `heatwave`, and `ev_surge`.

Frontend use:

- Populate the scenario selector from this response.
- Display friendly labels such as “Normal day”, while sending the original value such as `normal` to the API.

### `GET /api/observability/status`

Asks: “Is the flexibility-assurance calculation engine available, and what are its limits?”

This is not a model-training status. The engine is deterministic NumPy code and normally reports `ready: true`. Its `boundaries` explain what it does not claim.

Frontend use:

- Show whether registered flexibility, estimation and event verification are available.
- Preserve the boundary that aggregate AMI data does not identify individual appliances.

### `GET /api/models`

Asks: “Which evaluated ML artifacts exist?”

The forecast artifact appears under `models`. The flexibility-assurance engine appears separately under `observability` because it is not an ML model.

Frontend use:

- Build a model/evaluation information panel.
- Keep `trained`, `evaluation_only`, and `runtime_ready` visually distinct.
- Do not claim the evaluated forecast artifact is serving live predictions when `runtime_ready` is false.

## Simulation run endpoints

### `POST /api/runs`

Asks: “Start a new baseline-versus-Vidyut simulation.”

The request selects the scenario, deterministic seed, duration and optional scenario overrides. The response immediately returns a short `run_id`; computation continues in the background.

Frontend use:

- Send the run form here.
- Store the returned `run_id` as the active run.
- Move the UI into a pending/running state.
- Do not treat the initial response as a completed simulation.

Important parameters:

- `ticks`: number of 15-minute intervals. `12` means three hours and `96` means a full day.
- `seed`: reproduces the same generated network and population.
- `carry_debt`: uses stored fairness history when the database is available.
- `params`: optional AMI, connected-device, EV, household-tier, peak and tariff overrides.

### `GET /api/runs`

Asks: “Which recent runs still exist in this API process?”

It returns the same status records used by the individual status endpoint.

Frontend use:

- Build a recent-runs picker or debugging page.
- Do not treat it as permanent run history. The in-memory list is bounded and is cleared when the API process restarts.

### `GET /api/runs/{run_id}`

Asks: “What is happening with this run right now?”

Possible statuses are `pending`, `running`, `ready`, and `failed`. It also reports persistence status, injection generation, and any failure message.

Frontend use:

- Poll approximately every 500 milliseconds after creating or injecting a run.
- Stop polling on `ready` or `failed`.
- On `failed`, display the `error` value.
- A `persisted: false` result can still be a valid in-memory simulation; inspect `persistence_error` before deciding how to label it.

### `GET /api/runs/{run_id}/summary`

Asks: “What were the final results, and how did Vidyut compare with the baseline?”

It returns totals for both arms and a `deltas` object. Every delta is calculated as Vidyut minus baseline.

Frontend use:

- Populate comparison tables and headline metrics.
- Use lower-is-better coloring for unserved energy, homes-dark time, losses and overload measures.
- Use higher-is-better coloring for critical uptime and served energy.
- Do not assume every positive delta is good.

### `GET /api/runs/{run_id}/flexibility`

Asks: “How much controllable capacity was registered and available in this simulated run?”

It separates three concepts:

- `registered`: controllable device nameplate capacity.
- `available`: the portion scheduled or expected to be active during each interval.
- `realised`: reduction measured inside the simulator.

Frontend use:

- Show registered capacity by device kind.
- Plot `available.profile_kw` as one value per run tick.
- Label realised values as simulated results, not field telemetry.
- This endpoint does not use aggregate-load appliance detection.

### `POST /api/runs/{run_id}/inject`

Asks: “Change this completed run by adding a disturbance and simulate it again.”

Supported disturbances are `heatwave`, `ev_surge`, `cloud_cover`, and `dt_fault`. The same run ID is retained, but its generation increases and its previous result is temporarily removed.

Frontend use:

- Only enable injection when the run is ready.
- After a successful injection, clear or mark old result panels as stale.
- Return to status polling and reload summary, flexibility and events after the new generation becomes ready.
- For `dt_fault`, require the user to select a valid transformer ID.
- `from_tick` must be inside that run's duration.

### `GET /api/runs/{run_id}/events`

Asks: “Which decisions did the selected controller make?”

Each event includes its tick, action, target, affected power, household count, reason code, human-readable detail and optional forecast-versus-safe-limit values.

Frontend use:

- Build an audit timeline.
- Filter by arm, control tier or transformer.
- Use `offset` and `limit` for pagination.
- Show `detail` to users; `reason_code` is mainly useful for filtering and consistent icons.
- An empty list is valid and means no controller action occurred in the selected window.

### `GET /api/runs/{run_id}/notifications`

Asks: “Which customer or operator notifications are waiting to be sent?”

These are notification messages generated by the controller and still present in its outbox.

Frontend use:

- Preview recipient group, channel, reason, message, tariff multiplier and expected response.
- Treat the returned count as pending messages, not all notifications ever generated.

### `POST /api/runs/{run_id}/notifications/dispatch`

Asks: “Send the pending notification batches to the configured n8n webhook.”

If no webhook is configured, it returns `not_configured` without sending. If sending fails after retries, it returns `unreachable` and an error. Successful delivery to the webhook returns `delivered`.

Frontend use:

- Treat this as an operator action, not an automatic page-load request.
- Require confirmation before dispatch in a production UI.
- Distinguish “accepted by webhook” from final provider delivery.

### `GET /api/runs/{run_id}/report`

Asks: “Generate the PDF audit report for this completed run.”

The response is PDF bytes rather than JSON.

Frontend use:

- Open the URL in a new browser tab for a simple implementation.
- Use a Blob download when the product needs a named download action.
- Only enable the action when the run is ready.

## Flexibility-assurance endpoints

### `POST /api/observability/flexibility/estimate`

Asks: “How much of recent aggregate demand appears weather-sensitive, and how much can be considered actionable after applying the registered-capacity limit?”

The input contains matching days-by-intervals matrices for aggregate kW and ambient temperature. Null values represent missing data. The engine builds an interval baseline and checks whether excess load has a reliable positive temperature association.

Frontend use:

- Use this for imported or live AMI and weather histories, not the simulator's device registry.
- Always show source, method, confidence and coverage.
- Present `estimated_profile_kw` separately from `actionable_profile_kw`.
- When `ready` is false, display `reasons` and do not present actionable capacity.
- Do not rename the result “AC detected” or “appliance load”.

Why an estimate may be unavailable:

- Fewer than three comparable days.
- Less than 80% joint meter-and-weather coverage.
- Less than 4 °C temperature variation.
- No reliable positive temperature association.

### `POST /api/observability/events/verify`

Asks: “During a demand-response event, how much did observed load fall below its calculated baseline?”

The frontend supplies historical daily load profiles, the observed event-day profile, the event interval and the committed reduction.

Frontend use:

- Show baseline and observed values together.
- Show both kW reduction and kWh reduction because they answer different questions.
- Show the selected method and same-day adjustment.
- `performance_pct` may be over 100% when response exceeds the commitment.
- The high-4-of-5 method needs at least four complete eligible days; 10-in-10 needs ten.

## Household and fairness endpoints

### `GET /api/households/{household_id}`

Asks: “What devices, addressability, fairness balance and curtailment history belong to this household?”

The response combines the household profile, registered devices, fairness ledger and a paginated history of control impacts. Each history row includes a human-readable explanation.

Frontend use:

- Build a household transparency or customer-support page.
- Use the supplied `explanation` instead of recreating fairness wording in the browser.
- Paginate history with `offset` and `limit`.
- This endpoint requires PostgreSQL and returns 503 when the database is unavailable.

### `GET /api/fairness/leaderboard`

Asks: “Which households have accumulated the most curtailment burden?”

It can return the overall list or only households on one transformer.

Frontend use:

- Build an operator fairness panel.
- Use `dt_id` to inspect fairness within a transformer rather than comparing unrelated areas.
- Explain that a higher debt balance means the household has already borne more burden and should usually move back in the selection queue.
- This endpoint requires PostgreSQL.

## Provider integration endpoint

### `POST /api/notifications/{notification_id}/delivery`

Asks: “What happened to a message after the external notification provider handled it?”

This records provider delivery states such as dispatched, delivered or failed.

Frontend use:

- Normal browser code should not call this endpoint.
- It is intended for n8n or a messaging-provider callback.
- An internal operations page may read delivery state in the future, but it should not manufacture callbacks.

## WebSocket playback

### `WS /ws/runs/{run_id}`

Asks: “Stream this run one 15-minute tick at a time for an animated network view.”

The server sends messages in this order:

1. `status`
2. `ready`
3. One `tick` message per interval
4. `complete`

It may send `error` instead when the run is missing, parameters are invalid, or simulation does not complete.

Frontend use:

- Use `speed` to control playback from 0.1 to 200 ticks per second.
- Use `from_tick` to resume the visual stream.
- Each tick contains both baseline and Vidyut feeder, transformer, topology, metric and event snapshots.
- The WebSocket replays an already computed run; it is not live field telemetry.
- Reconnect after an injection because the run generation and result changed.

## Features that should not appear as normal buttons

- The notification delivery callback is provider-facing.
- Notification dispatch needs explicit operator confirmation.
- Injection changes a completed simulation and should be clearly labeled as a simulation action.
- Database failures should not be presented as simulation failures.
- Estimated weather-sensitive opportunity must not be presented as registered capacity or appliance detection.

## Where to find exact formats

- `frontend/docs/frontend-context.json`: every parameter, type, limit and response contract.
- `frontend/docs/api-examples.json`: copy-paste request and response examples.
- `http://localhost:8000/openapi.json`: machine-generated HTTP specification from the running backend.
- The WebSocket contract is documented in the JSON handoff because OpenAPI does not describe WebSockets.
