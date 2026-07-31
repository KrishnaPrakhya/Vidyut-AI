# Persistence scope — why Vidyut needs a database

## The argument

A simulation does not need a database. Vidyut does, and the reason is not storage — it is that two
of the four novelty claims are **statements about history**, and history cannot live in a process
that exits.

> **Claim 2 — obligation, not incentive.** Where flexibility must be taken rather than bought, the
> hard problem becomes equity.
>
> **Claim 4 — per-household auditability.** Every action carries a reason and a
> standing-relative-to-neighbours figure.

Curtailment debt that resets when the run ends is not debt. "Why me and not my neighbour" is
unanswerable without a record of what happened to the neighbour last Tuesday. The fairness ledger is
the product, and a ledger is by definition durable.

Everything else below is real but secondary. This one is structural.

## Ranked needs

### 1. The fairness ledger must outlive the episode

Rotational curtailment orders households by accumulated debt. Over a single 24-hour run that
ordering barely matters — few households are hit twice. Over a heatwave week it is the entire
mechanism: the households curtailed on Monday must be at the back of the queue on Tuesday.

Without persistence the rotation resets daily and Vidyut curtails the same low-comfort-cost
households every single day — precisely the inequity the claim says it solves. The ledger is keyed
by **household**, not by run.

This also unlocks the strongest demo we can build: run three consecutive heatwave days and show the
Tier-3 rotation selecting *different* households each day because debt carried over.

### 2. Regulatory audit trail

An Indian DISCOM curtailing a consumer under obligation is a regulated act. SERCs, the draft 2026
consumer-rights amendments, and any future DR framework will expect a defensible record: who was
curtailed, when, at what level, under what reason code, what the measured constraint was, and what
their standing was relative to comparable consumers.

That is an append-only table with a retention policy, not an in-memory list. It is also the
artifact behind the incident-report PDF.

### 3. Measurement and verification needs history by construction

The standard DR baseline is **high 4-of-5 same-day-adjusted** — it requires the household's load on
the five preceding comparable days. NILM's M&V role cannot be computed at all without stored
per-household history. This is a hard dependency, not a nicety.

### 4. Forecast accuracy over time

Claiming the fine-tuned Chronos model beats seasonal naive requires storing issued forecasts against
realised load and computing error after the fact. A single run's MASE is a point estimate; the
credible version is error tracked across runs, scenarios and horizons.

### 5. Consent and delivery receipts for price signals

Price signalling sends messages to real people. That carries obligations most DR demos ignore:
recorded consent, opt-out state, and delivery status per message. n8n dispatches; the delivery
outcome has to come back and be recorded against the notification. Consent is master data with an
audit trail of its own.

### 6. Run comparison and reproducibility

Parameter sweeps, seed comparisons, and "what changed between these two runs" need runs to be
durable objects with their inputs and code version recorded.

## Explicit non-goals

Scope creep here is the risk, so these are out:

- **Not a time-series store for production telemetry.** At real scale (52.53 lakh DTs) this would be
  TimescaleDB or a historian. We store simulation output at demo scale and say so.
- **No authentication, multi-tenancy, or row-level security.** B11 rules these out.
- **No write path from the tick loop.** See the architectural constraint below.
- **Postgres is never required for the demo to run.** See below.

## The architectural constraint that makes this safe

This is the part that matters most.

```
services/sim  MUST NOT import  services/persistence
```

Same discipline as `services/nilm` not importing `services/actuation`, enforced the same way — a
test. The simulation stays pure, importable, and headless. `python -m services.sim.run` continues to
work with no database, no container, and no network. The Day-2 fallback demo and the offline
requirement are both protected.

Postgres is an **adapter at the API boundary**:

```
POST /api/runs
  └─ services.sim.simulate(...)        pure, in memory, no IO
  └─ services.persistence.save_run(...)  after the fact
```

If `DATABASE_URL` is unset the API behaves exactly as it does today, holding runs in memory. The
same graceful-degradation posture as the n8n dispatcher: absent infrastructure is a reported status,
never a crash.

### How prior debt enters a pure simulation

The sim needs to *read* accumulated debt to order rotation, but it cannot query a database. The
dependency is inverted: the API loads opening balances and passes them in as a plain dict.

```
opening_debt = persistence.load_fairness_balances(household_ids)   # API layer
world = build_world(arm, scenario, seed, params, opening_debt)     # plain dict[str, float]
```

`services/sim` gains an optional dict parameter and no imports. The ledger becomes continuous across
runs without the simulation knowing a database exists.

## Schema

### Asset and customer master

Stable across runs. In production this is fed from the DISCOM's GIS, CIS and MDM rather than the
population generator.

| table | purpose |
|---|---|
| `substation`, `feeder`, `distribution_transformer`, `tie_switch` | network asset register |
| `household` | id, dt_id, tier, ami, meter_load_limit_supported, consent_dr, consent_updated_at |
| `device` | household_id, kind, rated_kw, controllable, deferrable_window_min, comfort_cost_per_min |

Household IDs are deterministic under a given seed and parameter set, which is what allows a
household to be the *same* household across runs.

### Episodes and results

| table | purpose |
|---|---|
| `run` | scenario, seed, ticks, params, status, timings, sim version |
| `run_injection` | judge triggers applied, with tick and magnitude |
| `run_arm_total` | final metrics per arm |
| `tick_metric` | per-tick headline metrics per arm |
| `dt_tick_reading` | per-DT loading, energised, households dark |
| `feeder_tick_reading` | per-feeder loading and losses |
| `topology_change` | reconfiguration decisions with objective before/after |

`dt_tick_reading` is the volume table: 60 DTs × 96 ticks × 2 arms = 11,520 rows per run. Trivial at
demo scale; partitioned by run in anything larger.

### The audit spine

| table | purpose |
|---|---|
| `control_action` | one row per controller decision — tier, action, level, dt_id, kw, households, reason_code, detail, **and the forecast_kw / safe_limit_kw that justified it** |
| `household_impact` | one row per household per action — level, kw, minutes, debt weight, debt charged, and `standing_percentile`, the household's debt relative to its DT neighbours at decision time |
| `fairness_ledger` | **keyed by household_id**, cumulative debt, minutes by level, first/last curtailed |
| `fairness_ledger_history` | append-only record of every change to the ledger itself |

`household_impact.standing_percentile` is claim 4 made concrete: it is the number that lets a
household be told, in one sentence, where they stood relative to their neighbours when the decision
was made.

### Notifications and ML

| table | purpose |
|---|---|
| `notification` | the outbox row, as dispatched to n8n |
| `notification_delivery` | provider, status, message id, delivered_at, error — written by an n8n callback |
| `forecast_issue` | issued horizon per DT per tick, with model name and version |
| `forecast_error` | predicted vs realised, enabling MASE/MAPE across runs |
| `mv_verification` | expected vs realised reduction per action, with baseline method recorded |
| `model_artifact` | trained model registry — name, version, trained_at, metrics |

## What this unlocks

- **Multi-day fairness demo.** Three consecutive heatwave days, rotation visibly rotating.
- **Household 360.** `GET /api/households/{id}` — full curtailment history, every reason, standing
  over time. This is the single most convincing screen for claim 4.
- **Regulatory export.** All actions in a period, per household, as CSV or PDF.
- **Honest M&V.** Realised against expected, with the baseline method named.
- **Forecast scoreboard** that improves as more runs accumulate.

## Implementation phases

**Phase 1 — foundation.** Postgres in docker-compose, SQLAlchemy 2.0 models, Alembic migrations,
repository layer, `save_run` after simulation. Import-isolation test. Graceful degradation when
`DATABASE_URL` is unset.

**Phase 2 — the ledger becomes real.** Persistent `fairness_ledger`, opening balances passed into
`build_world`, multi-day continuity, `standing_percentile` computed at decision time,
`GET /api/households/{id}`.

**Phase 3 — notifications close the loop.** Delivery callbacks from n8n, consent and opt-out state
respected by the price-signal tier.

**Phase 4 — ML records.** Forecast error accumulation, M&V verification rows, model registry.

Phases 1 and 2 carry the argument. Phases 3 and 4 are additive and cuttable.
