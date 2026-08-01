# Vidyut frontend

The frontend has four connected workspaces:

- **Command center** combines the recorded network loading curve, spatial twin, controller events and an evidence-grounded Vidyut Copilot.
- **Replay** loads a deterministic 96-interval recording and presents a short heatwave story plus a fully synchronized timeline, transformer map, locality state, controller trace and fairness ledger.
- **Simulation lab** creates a fresh baseline-versus-Vidyut run, polls it to completion and exposes the comparison, registered flexibility, events, notifications and audit PDF.
- **Assurance** demonstrates the aggregate AMI + weather opportunity estimate and post-event measurement and verification flow with explicit evidence labels.

Start the backend on `http://localhost:8000`, then run:

```bash
npm run dev
```

Open `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL` before starting the frontend when the API runs elsewhere.

Set `GROQ_API_KEY` in the frontend server environment to enable Vidyut Copilot. The key is read only by the Next.js route handler and is never exposed through a `NEXT_PUBLIC_` variable. LangGraph grounds the request, selects a risk, comparison, resident, incident or general specialist, verifies numeric claims against cited evidence, repairs an unsafe draft when necessary and returns the visible audit path. The copilot has no actuation tool or backend command import.

Useful checks:

```bash
npm run lint
npm run build
```

The frontend-team API handoff is in [`docs/frontend-context.json`](docs/frontend-context.json), with request examples in [`docs/api-examples.json`](docs/api-examples.json) and plain-language endpoint explanations in [`docs/endpoint-guide.md`](docs/endpoint-guide.md).
