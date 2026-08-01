# ⚡ Vidyut-AI

> **AI-powered distribution network intelligence that prevents neighborhood blackouts before they happen.**

Vidyut-AI is a full-stack platform that simulates realistic Indian electrical distribution networks under stress scenarios (heatwaves, EV surges), applies a tiered autonomous response controller, and lets grid operators explore, compare, and audit every decision through an interactive 3D digital twin, an evidence-grounded AI Copilot, and automated operator email digests — all backed by a production-grade deployment pipeline on **Azure + Vercel**.

---

## 📑 Table of Contents

- [Problem Statement](#-problem-statement)
- [How Vidyut Solves It](#-how-vidyut-solves-it)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Frontend — Features & Components](#-frontend--features--components)
- [Backend — Services & Modules](#-backend--services--modules)
- [API Reference](#-api-reference)
- [ML / Forecast Pipeline](#-ml--forecast-pipeline)
- [N8N Workflow Automation](#-n8n-workflow-automation)
- [Deployment](#-deployment)
- [Getting Started (Local)](#-getting-started-local)
- [All Commands](#-all-commands)
- [Testing](#-testing)
- [Environment Variables](#-environment-variables)
- [Project Structure](#-project-structure)

---

## 🔥 Problem Statement

During extreme heat events, residential cooling demand can surge simultaneously across hundreds of homes served by the same distribution transformer. When the transformer exceeds its rated capacity, conventional protection trips the entire locality — **70+ homes go dark at once**, including critical medical loads. There is no visibility, no warning, and no fairness in who gets affected.

## 💡 How Vidyut Solves It

Vidyut operates a **5-step autonomous control loop** running every 15 minutes:

| Step | Action | Detail |
|:--:|:--|:--|
| **01** | **Sense** | Read demand and equipment state from AMI-enabled households every 15-minute interval |
| **02** | **Forecast** | Look 1 hour ahead at **each transformer**, not just the whole feeder |
| **03** | **Decide** | Use the smallest fair intervention that can remove the risk (fairness ledger, debt-weighted priority) |
| **04** | **Respond** | Shift flexible demand first, then curtail locally only when necessary |
| **05** | **Verify** | Measure the actual result and carry the household burden ledger forward |

The result: in a recorded heatwave scenario, Vidyut prevents **96%+ of homes-dark-minutes** compared to conventional protection, while maintaining **100% critical-load uptime**.

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────┐
│                   FRONTEND (Vercel)                  │
│  Next.js 16 · React 19 · Three.js · Framer Motion   │
│  ┌──────────┬──────────┬──────────┬────────────────┐ │
│  │ Landing  │ Command  │  Replay  │  Simulation    │ │
│  │  Page    │  Center  │ Dashboard│    Lab         │ │
│  ├──────────┴──────────┴──────────┴────────────────┤ │
│  │ Assurance Lab │ Story Mode │ AI Copilot (Groq)  │ │
│  └─────────────────────┬──────────────────────────── │
│                        │ /api/ai/explain (LangGraph) │
└────────────────────────┼─────────────────────────────┘
                         │ REST + WebSocket
┌────────────────────────┼─────────────────────────────┐
│                   BACKEND (Azure VM)                 │
│  FastAPI · Pandapower · SQLAlchemy · Alembic         │
│  ┌─────────┬───────────┬────────────┬──────────────┐ │
│  │   API   │Simulation │ Dispatch   │Observability │ │
│  │ Service │  Engine   │ (n8n/email)│  & M&V       │ │
│  ├─────────┴───────────┴────────────┴──────────────┤ │
│  │ Persistence (PostgreSQL) │ Forecast │ Actuation  │ │
│  └─────────────────────────┴──────────┴────────────┤ │
│                                                      │
│  ┌─────────┐  ┌─────────┐  ┌──────────────────────┐ │
│  │PostgreSQL│  │  n8n    │  │  Caddy (TLS/Proxy)   │ │
│  │  16      │  │  2.28   │  │  Auto HTTPS          │ │
│  └─────────┘  └─────────┘  └──────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Frontend

| Technology | Purpose |
|:--|:--|
| **Next.js 16** | React framework with server-side rendering and API routes |
| **React 19** | UI library |
| **Tailwind CSS v4** | Utility-first styling |
| **Framer Motion** | Animations, page transitions, scroll-driven effects |
| **Three.js** (`@react-three/fiber` + `@react-three/drei`) | Interactive 3D digital twin of the distribution network |
| **Recharts** | Data visualization — loading curves, demand charts |
| **Zustand** | Client-side state management |
| **LangChain / LangGraph** | Multi-agent AI Copilot orchestration |
| **Groq SDK** | LLM inference (via server-side route handler) |
| **Zod v4** | Runtime schema validation for Copilot requests |

### Backend

| Technology | Purpose |
|:--|:--|
| **Python 3.11** | Runtime |
| **FastAPI** | REST API + WebSocket endpoints |
| **Pandapower** | IEEE-standard power flow solver for grid simulation |
| **SQLAlchemy 2.0** + **Alembic** | ORM and database migrations |
| **PostgreSQL 16** | Persistent storage (runs, households, fairness, notifications) |
| **NumPy / Pandas / SciPy** | Numerical simulation, demand modeling |
| **NetworkX** | Network topology graph |
| **ReportLab** | Automated PDF audit report generation |
| **WebSockets** | Real-time tick-by-tick simulation streaming |
| **uv** | Fast Python package manager |

### Infrastructure & Automation

| Technology | Purpose |
|:--|:--|
| **Docker** + **Docker Compose** | Container orchestration (local + production) |
| **Caddy** | Automatic HTTPS reverse proxy (TLS via Let's Encrypt) |
| **n8n** | Workflow automation — operator email digests via Gmail |
| **Azure VM** (Standard_B2s) | Production backend hosting |
| **Vercel** | Production frontend hosting |
| **Cloudflare DNS** | DNS management |

---

## 🖥️ Frontend — Features & Components

### 1. Landing Page (`landing-page.tsx`)
- **Scroll-driven narrative** that tells the blackout story in 3 beats: demand surge → blackout → Vidyut protection
- **Interactive 3D hero twin** that cycles through scenarios automatically
- **Animated neighborhood comparison** showing baseline vs. Vidyut side-by-side with house-by-house visualization
- Parallax scroll progress indicator, responsive navigation

### 2. Command Center (`command-center.tsx`)
- **Unified operator dashboard** showing real-time network state
- **Interactive 3D digital twin** with selectable distribution transformers (color-coded by loading: green/yellow/red)
- **Network loading curve chart** (Recharts `AreaChart`) comparing baseline vs. Vidyut across all 96 intervals
- **Controller decision feed** showing Tier 1/2/3 events with kW reductions, affected households, and reason codes
- **Vidyut Copilot AI panel** — ask natural language questions about the grid state

### 3. Replay Dashboard (`replay-dashboard.tsx`)
- **Full 96-interval playback** with play/pause, speed control (1×–8×), and timeline scrubbing
- **Event markers** on the timeline showing overloads, controller actions, and outages
- **Side-by-side transformer comparison** (Baseline vs. Vidyut) with loading %, homes dark, energized status
- **Fairness leaderboard** — queries the backend for household burden distribution (cumulative debt in minutes)
- **Dual network view** — toggle between grid overview and 3D spatial twin

### 4. Story Mode (`story-mode.tsx`)
- **Cinematic auto-playing narrative** using pre-built story beats extracted from the recording
- Each beat highlights a specific transformer at a specific tick with custom text (heat build-up, overload, forecast action, protection, outcome)
- Transformer grid visualization with active intervention markers

### 5. Simulation Lab (`simulation-lab.tsx`)
- **Create and run fresh simulations** against the live backend API
- Configurable scenario parameters: AMI penetration, connected device penetration, EV penetration, critical share, peak multiplier
- **Real-time WebSocket streaming** — watch the simulation tick-by-tick as it computes
- **Results panels**: summary comparison, flexibility registration, events list, operator notifications
- **Operator digest dispatch** — enter an email (with consent checkbox) to send a real Gmail digest via n8n
- **PDF audit report** download
- **Fault injection** — inject heatwave surges, EV surges, cloud cover, or DT faults mid-run

### 6. Assurance Lab (`assurance-lab.tsx`)
- **Weather-driven opportunity estimation** — enter aggregate demand + ambient temperature to estimate flexible capacity
- **Measurement & Verification (M&V)** using industry-standard methods: `high_4_of_5` and `ten_in_ten`
- **ML forecast model registry** — shows Chronos fine-tuned vs. Seasonal Naive vs. LightGBM accuracy (MASE, MAPE, MAE) across horizons
- Cold-start evaluation for new meters with limited history

### 7. 3D Network Digital Twin (`network-3d.tsx`)
- Built with **Three.js** (`@react-three/fiber`)
- 60 distribution transformers across 3 feeders, rendered as 3D blocks with neighborhood houses
- **Color-coded** by state: green (stable), yellow (strained ≥90%), red (overloaded ≥100%), dark (offline)
- Active intervention ring animation on transformers under Vidyut control
- Interactive orbit controls, hover tooltips, click-to-select

### 8. AI Copilot (`ai-explainer.tsx` + `vidyut-agent.ts`)
- **LangGraph multi-agent workflow** running server-side via Next.js route handler (`/api/ai/explain`)
- **5 specialist agents**: Risk, Compare, Resident, Incident, General
- Evidence grounding: every answer cites specific data points from the simulation frame
- **Claim verification**: unsupported numeric claims are automatically detected and repaired
- **Safety guardrails**: the Copilot never implies actuation authority, never uses Markdown, always identifies readings as simulated
- Full audit trace returned to the UI showing each graph node traversed

---

## ⚙️ Backend — Services & Modules

### `services/sim/` — Simulation Engine
| Module | Responsibility |
|:--|:--|
| `world.py` | Core world model — households, transformers, pandapower network, power flow solver |
| `run.py` | Orchestrates a full simulation run (baseline + vidyut arms, 96 ticks each) |
| `demand.py` | Demand modeling with temperature-driven peaks, EV profiles, design-day sizing |
| `network.py` | Builds the pandapower network (feeders, transformers, buses, lines) |
| `population.py` | Generates the household population with AMI, devices, tiers |
| `controllers/baseline.py` | Conventional protection: overload → disconnect transformer |
| `controllers/vidyut.py` | **580-line Vidyut controller**: Tier 1 (demand shifting + topology reconfiguration), Tier 2 (preemptive curtailment via price signals + device control), Tier 3 (emergency load limiting + last-resort disconnection) |
| `ledger.py` | Fairness ledger — tracks cumulative burden (minutes of curtailment) per household |
| `metrics.py` | Collects per-tick and per-run metrics (loading, homes dark, unserved kWh, Gini coefficient) |
| `reconfiguration.py` | Tie-switch reconfiguration to rebalance feeder loading |
| `injection.py` | Runtime fault injection (heatwave, EV surge, cloud cover, DT fault) |
| `record.py` | Records deterministic simulation runs to JSON for the Replay engine |
| `scenario.py` | Loads YAML scenario configs (`heatwave`, `ev_surge`, `normal`) |
| `topology.py` | Network topology generation with tie switches |

### `services/api/` — REST API
| Module | Responsibility |
|:--|:--|
| `main.py` | FastAPI application — 25+ endpoints, CORS, WebSocket, lifespan management |
| `schemas.py` | Pydantic request/response models with validation |
| `store.py` | In-memory run store with background simulation execution |
| `report.py` | PDF audit report generation using ReportLab (A4 format, tables, event logs) |
| `models_registry.py` | Serves ML model evaluation artifacts |

### `services/dispatch/` — Notification & Email Automation
| Module | Responsibility |
|:--|:--|
| `digest.py` | Builds the operator digest payload (HTML email body, subject, PDF link) |
| `n8n.py` | Dispatches operator digests to n8n webhook with retry + HMAC auth |
| `outbox.py` | Notification outbox model (pending/acknowledged state) |
| `rate_limit.py` | Per-IP and per-email rate limiting (3/email/hour, 10/IP/hour) |

### `services/observability/` — Flexibility Assurance & M&V
| Module | Responsibility |
|:--|:--|
| `flexibility.py` | Weather-driven opportunity estimation, registered capacity envelope, availability profiling |
| `verification.py` | Post-event M&V using `high_4_of_5` and `ten_in_ten` baseline methods |

### `services/persistence/` — Database Layer
| Module | Responsibility |
|:--|:--|
| `models.py` | SQLAlchemy ORM models: Feeder, DistributionTransformer, Household, Device, Run, Notification, HouseholdAction, TickMetric |
| `repository.py` | CRUD operations for runs, notifications, delivery tracking |
| `queries.py` | Fairness leaderboard, household history, profile lookups |
| `engine.py` | Database connection management, schema creation |

### `services/forecast/` — Demand Forecasting
| Module | Responsibility |
|:--|:--|
| `naive.py` | Seasonal naive baseline forecaster |
| `base.py` | Forecaster interface |

### `services/actuation/` — Load Control
| Module | Responsibility |
|:--|:--|
| `commands.py` | Actuation command model — tracks device curtailment, load limiting, and disconnect commands with durations |

---

## 🌐 API Reference

### Health & Metadata

| Method | Endpoint | Description |
|:--|:--|:--|
| `GET` | `/api/health` | Health check — returns API status, available scenarios, database connectivity, n8n configuration |
| `GET` | `/api/scenarios` | List available simulation scenarios (`normal`, `heatwave`, `ev_surge`) |
| `GET` | `/api/models` | ML model registry — forecast evaluation metrics (MASE, MAPE, cold-start) |

### Recordings (Pre-computed Replays)

| Method | Endpoint | Description |
|:--|:--|:--|
| `GET` | `/api/recordings` | List all recorded simulation files with metadata |
| `GET` | `/api/recordings/{scenario}?seed=42` | Download a specific recorded replay JSON (cached 5 min) |

### Simulation Runs

| Method | Endpoint | Description |
|:--|:--|:--|
| `POST` | `/api/runs` | Create a new simulation run (scenario, seed, ticks, params, carry_debt) |
| `GET` | `/api/runs` | List all runs |
| `GET` | `/api/runs/{run_id}` | Get run status (pending/running/ready/failed) |
| `GET` | `/api/runs/{run_id}/summary` | Get completed run summary — baseline vs. vidyut totals + deltas |
| `GET` | `/api/runs/{run_id}/flexibility` | Registered, available, and realised flexibility data |
| `GET` | `/api/runs/{run_id}/events?arm=vidyut&tier=1` | Paginated controller events with filtering |
| `GET` | `/api/runs/{run_id}/report` | Download PDF audit report |
| `POST` | `/api/runs/{run_id}/inject` | Inject a fault/surge into a completed run and re-simulate |
| `WebSocket` | `/ws/runs/{run_id}?speed=4` | Real-time tick-by-tick simulation stream |

### Notifications & Operator Digests

| Method | Endpoint | Description |
|:--|:--|:--|
| `GET` | `/api/runs/{run_id}/notifications` | Get pending notifications for a run |
| `POST` | `/api/runs/{run_id}/notifications/dispatch` | Send operator digest email via n8n (rate-limited, requires consent) |
| `GET` | `/api/runs/{run_id}/notifications/delivery` | Poll delivery status (accepted → delivered) |
| `POST` | `/api/runs/{run_id}/notifications/delivery` | n8n callback — update delivery status (HMAC authenticated) |
| `POST` | `/api/notifications/{id}/delivery` | Per-notification delivery callback |

### Observability & M&V

| Method | Endpoint | Description |
|:--|:--|:--|
| `GET` | `/api/observability/status` | Flexibility assurance engine status and supported methods |
| `POST` | `/api/observability/flexibility/estimate` | Estimate weather-driven flexibility opportunity from AMI + temperature data |
| `POST` | `/api/observability/events/verify` | Post-event M&V verification using `high_4_of_5` or `ten_in_ten` |

### Households & Fairness

| Method | Endpoint | Description |
|:--|:--|:--|
| `GET` | `/api/households/{household_id}` | Household profile + action history |
| `GET` | `/api/fairness/leaderboard?dt_id=F1-DT17` | Fairness leaderboard — cumulative burden ranking |

### Frontend Server Route

| Method | Endpoint | Description |
|:--|:--|:--|
| `POST` | `/api/ai/explain` | Vidyut Copilot — LangGraph multi-agent AI pipeline (runs on Next.js server, calls Groq) |

---

## 🧠 ML / Forecast Pipeline

Located in `backend/ml/`:

| Item | Description |
|:--|:--|
| `kaggle_training/train_forecast.py` | Training script for demand forecasting models using real Kaggle smart meter data |
| `kaggle_training/train_forecast.ipynb` | Jupyter notebook version for interactive development |
| `models/forecast_eval.json` | Pre-computed model evaluation results (Chronos fine-tuned, LightGBM, Seasonal Naive) |
| `models/forecasts.parquet` | Forecast output data |
| `export_forecast_data.py` | Export simulation demand data for training |

**Models evaluated**:
- **Chronos (fine-tuned)** — Amazon's foundation model for time series, fine-tuned on Indian household data
- **LightGBM** — gradient boosted tree baseline
- **Seasonal Naive** — persistence baseline

Metrics tracked: **MASE**, **MAPE**, **MAE (kW)** across next-hour and full-day horizons, including cold-start performance with limited history.

---

## 🔄 N8N Workflow Automation

Located in `automation/n8n/`:

The **Vidyut Operator Digest** workflow sends a real email (via Gmail OAuth) to the evaluator acting as the grid operator. The flow:

1. **Receive webhook** — authenticated with `X-Vidyut-Webhook-Token`
2. **Download audit PDF** — fetches the run's PDF report from the API
3. **Send Gmail** — HTML digest email with the PDF attached
4. **Delivery callback** — calls back to the API with delivery status (authenticated with `X-Vidyut-Callback-Token`)

Security:
- Two independent HMAC tokens (webhook + callback)
- Rate limited: 3 sends/email/hour, 10 sends/IP/hour
- Email address is never persisted to the database or run record
- n8n execution data saving is disabled to prevent retention

---

## 🚀 Deployment

### Frontend → Vercel

The Next.js frontend is deployed to **Vercel** with the configuration in `frontend/vercel.json`:

```bash
# Vercel auto-detects Next.js, uses:
npm ci          # install
npm run build   # build
```

Set these environment variables in Vercel:
- `NEXT_PUBLIC_API_URL` — points to the Azure API domain
- `GROQ_API_KEY` — server-side only, enables the AI Copilot

### Backend → Azure VM

Located in `deploy/azure/`. The backend runs on a single **Azure Ubuntu VM** (Standard_B2s, 2 vCPU, 4 GB RAM) with:

| Service | Port | Access |
|:--|:--|:--|
| **Caddy** | 80, 443 | Public (automatic HTTPS) |
| **FastAPI** | 8000 | Internal only (behind Caddy) |
| **n8n** | 5678 | Internal only (behind Caddy) |
| **PostgreSQL** | 5432 | Internal only (no public access) |

**Deployment commands:**

```bash
# 1. Bootstrap the VM (install Docker, configure firewall)
sudo bash deploy/azure/bootstrap.sh

# 2. Configure production env
cp deploy/azure/env.production.example deploy/azure/env.production
nano deploy/azure/env.production

# 3. Deploy all services
bash deploy/azure/deploy.sh
```

The `deploy.sh` script validates env vars (rejects placeholders), pulls images, builds the API container, and starts everything with `docker compose up -d`.

**DNS Setup** (Cloudflare):
- `api.yourdomain.com` → Azure VM IP (A record)
- `ops.yourdomain.com` → Azure VM IP (A record, for n8n)
- Frontend domain → configured in Vercel

Full deployment runbook: `docs/deployment-vercel-azure.md`

---

## 🏁 Getting Started (Local)

### Prerequisites

- **Docker** & **Docker Compose** (for database + optional full stack)
- **Node.js 20+** (for frontend)
- **Python 3.11** with [uv](https://github.com/astral-sh/uv) (for backend)

### Quick Start (Docker — recommended for evaluators)

```bash
# 1. Clone the repository
git clone https://github.com/KrishnaPrakhya/Vidyut-AI.git
cd Vidyut-AI

# 2. Set up environment variables
cp .env.example .env

# 3. Start the backend + database
docker compose up --build

# 4. In a new terminal, start the frontend
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** in your browser.

### Manual Setup (Development)

```bash
# 1. Start the database
docker compose up postgres -d

# 2. Set up and start the backend
cd backend
uv sync                                              # install dependencies
uv run uvicorn services.api.main:app --reload --port 8000  # start API

# 3. In a new terminal, start the frontend
cd frontend
npm install
npm run dev
```

### Enable the AI Copilot

Add `GROQ_API_KEY=your_key_here` to `frontend/.env`. The key is used server-side only (never exposed to the browser via `NEXT_PUBLIC_`).

---

## 📋 All Commands

### Makefile (from project root)

| Command | What it does |
|:--|:--|
| `make setup` | Install Python dependencies via `uv sync` |
| `make api` | Start the FastAPI backend with hot-reload on port 8000 |
| `make demo` | Build and start the full Docker Compose stack |
| `make demo-check` | Run pre-demo readiness checks (API health, DB, n8n, recordings, simulation, PDF report) |
| `make run SCENARIO=heatwave SEED=42` | Run a specific simulation scenario locally |
| `make record` | Record all scenarios to JSON files for the Replay engine |
| `make test` | Run fast unit tests (`pytest -q -m "not slow"`) |
| `make test-all` | Run the complete test suite including slow property sweeps |
| `make models` | Print the ML model evaluation registry |
| `make clean` | Remove `__pycache__` and `.pytest_cache` |

### Frontend (from `frontend/`)

| Command | What it does |
|:--|:--|
| `npm run dev` | Start Next.js dev server on port 3000 |
| `npm run build` | Production build |
| `npm run start` | Start production server |
| `npm run lint` | Run ESLint |

### Docker

| Command | What it does |
|:--|:--|
| `docker compose up --build` | Start the full local stack (PostgreSQL + API) |
| `docker compose up postgres -d` | Start just the database |
| `docker compose down` | Stop all services |
| `docker compose logs -f api` | Tail API logs |

---

## 🧪 Testing

The backend has **12 dedicated test files** covering:

| Test File | Coverage |
|:--|:--|
| `test_api.py` | All REST endpoints, WebSocket streaming, error handling |
| `test_determinism.py` | Verifies identical seeds produce identical simulation results |
| `test_dispatch.py` | n8n webhook dispatch, rate limiting, HMAC authentication |
| `test_observability.py` | Weather opportunity estimation, M&V verification methods |
| `test_opening_debt.py` | Fairness ledger initialization and carry-forward |
| `test_operator_digest.py` | Operator digest payload construction and delivery |
| `test_persistence.py` | Database CRUD operations, schema creation |
| `test_persistence_integration.py` | End-to-end database persistence with full run lifecycle |
| `test_reconfiguration.py` | Tie-switch topology reconfiguration logic |
| `test_record.py` | Deterministic recording to JSON |
| `test_runtime_hardening.py` | Edge cases, malformed input, concurrent access |
| `test_safety_invariants.py` | Critical safety properties (no actuation leaks, energy balance) |

```bash
# Fast tests only
cd backend && uv run pytest -q -m "not slow"

# Full suite
cd backend && uv run pytest -q
```

---

## 🔐 Environment Variables

### Root `.env`

| Variable | Description |
|:--|:--|
| `CORS_ORIGINS` | Allowed frontend origins (default: `http://localhost:3000`) |
| `VIDYUT_PUBLIC_API_URL` | Public-facing API URL (written into emails) |
| `DATABASE_URL` | PostgreSQL connection string |
| `N8N_WEBHOOK_URL` | n8n production webhook endpoint |
| `N8N_WEBHOOK_TOKEN` | HMAC token for authenticating webhook calls to n8n |
| `N8N_CALLBACK_TOKEN` | HMAC token for authenticating n8n callbacks to the API |
| `N8N_DOCKER_WEBHOOK_URL` | Container-safe n8n URL (for Docker Compose) |
| `VIDYUT_N8N_API_URL` | Internal API URL used by n8n for PDF download and callbacks |

### Frontend `.env`

| Variable | Description |
|:--|:--|
| `NEXT_PUBLIC_API_URL` | Backend API URL (default: `http://localhost:8000`) |
| `GROQ_API_KEY` | Server-side Groq API key for the AI Copilot |

---

## 📁 Project Structure

```
Vidyut-AI/
├── frontend/                      # Next.js 16 frontend
│   ├── app/
│   │   ├── components/            # 11 React components
│   │   │   ├── landing-page.tsx        # Scroll-driven narrative landing
│   │   │   ├── command-center.tsx      # Operator dashboard + 3D twin
│   │   │   ├── replay-dashboard.tsx    # 96-interval playback explorer
│   │   │   ├── simulation-lab.tsx      # Live simulation runner
│   │   │   ├── assurance-lab.tsx       # M&V and flexibility estimation
│   │   │   ├── story-mode.tsx          # Cinematic auto-playing narrative
│   │   │   ├── network-3d.tsx          # Three.js 3D digital twin
│   │   │   ├── ai-explainer.tsx        # Copilot UI panel
│   │   │   ├── app-header.tsx          # Navigation header
│   │   │   ├── transformer-grid.tsx    # Grid overview component
│   │   │   └── account-console.tsx     # User account management
│   │   ├── api/ai/explain/route.ts  # Copilot server-side API route
│   │   ├── lib/
│   │   │   ├── vidyut-agent.ts         # LangGraph multi-agent AI pipeline
│   │   │   ├── replay.ts              # Replay data utilities
│   │   │   └── glossary.tsx           # Technical term glossary
│   │   ├── page.tsx                 # Main app entry point
│   │   ├── layout.tsx               # Root layout
│   │   ├── types.ts                 # TypeScript type definitions
│   │   └── globals.css              # 120KB+ design system
│   ├── vercel.json                  # Vercel deployment config
│   └── package.json
│
├── backend/                       # Python 3.11 backend
│   ├── services/
│   │   ├── api/                    # FastAPI REST API (25+ endpoints)
│   │   ├── sim/                    # Simulation engine (pandapower)
│   │   │   └── controllers/        # Baseline + Vidyut controllers
│   │   ├── dispatch/               # n8n integration + email automation
│   │   ├── observability/          # Flexibility estimation + M&V
│   │   ├── persistence/            # PostgreSQL ORM + queries
│   │   ├── forecast/               # Demand forecasting
│   │   └── actuation/              # Load control commands
│   ├── ml/
│   │   ├── kaggle_training/        # ML training scripts + notebooks
│   │   └── models/                 # Pre-computed forecast evaluations
│   ├── data/
│   │   ├── scenarios/              # YAML scenario configs
│   │   └── recorded/               # Pre-recorded simulation replays
│   ├── tests/                      # 12 test files
│   ├── migrations/                 # Alembic database migrations
│   ├── Dockerfile                  # Backend container image
│   └── pyproject.toml              # Python project config
│
├── automation/
│   └── n8n/                        # n8n workflow + configuration
│       ├── vidyut-operator-digest.json  # Importable workflow
│       └── README.md
│
├── deploy/
│   └── azure/                      # Production deployment
│       ├── bootstrap.sh            # VM setup (Docker, firewall)
│       ├── deploy.sh               # Deploy all services
│       ├── docker-compose.prod.yml # Production compose (4 services)
│       ├── Caddyfile                # Reverse proxy config
│       └── env.production.example
│
├── docs/                          # Documentation
│   ├── deployment-vercel-azure.md  # Full deployment runbook
│   ├── frontend-contract.md        # Frontend-backend API contract
│   ├── persistence-scope.md        # Database schema documentation
│   └── demo-readiness.md           # Pre-demo checklist
│
├── scripts/
│   └── demo_check.py              # Automated readiness verification
│
├── docker-compose.yml             # Local development compose
├── Makefile                       # Project-wide commands
└── .env.example                   # Environment variable template
```

---

## 📜 Simulation Scenarios

| Scenario | Description | Peak Multiplier |
|:--|:--|:--|
| `heatwave` | Extreme heat drives simultaneous cooling demand across the network | 1.42× |
| `ev_surge` | High EV charging penetration creates evening demand spikes | Configurable |
| `normal` | Baseline day with typical residential load patterns | 1.0× |

Each scenario is defined in a YAML config file (`backend/data/scenarios/`) and supports runtime parameter overrides via the API (AMI penetration, EV penetration, critical share, etc.).

---

> **Built for the Hackathon** — Vidyut-AI demonstrates that AI-driven distribution intelligence can prevent blackouts, protect critical loads, and maintain fairness — all with full auditability.
