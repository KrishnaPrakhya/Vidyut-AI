# Vidyut frontend

The frontend has three connected workspaces:

- **Replay** loads a deterministic 96-interval recording and presents a short heatwave story plus a fully synchronized timeline, transformer map, locality state, controller trace and fairness ledger.
- **Simulation lab** creates a fresh baseline-versus-Vidyut run, polls it to completion and exposes the comparison, registered flexibility, events, notifications and audit PDF.
- **Assurance** demonstrates the aggregate AMI + weather opportunity estimate and post-event measurement and verification flow with explicit evidence labels.

Start the backend on `http://localhost:8000`, then run:

```bash
npm run dev
```

Open `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL` before starting the frontend when the API runs elsewhere.

Useful checks:

```bash
npm run lint
npm run build
```

The frontend-team API handoff is in [`docs/frontend-context.json`](docs/frontend-context.json), with request examples in [`docs/api-examples.json`](docs/api-examples.json) and plain-language endpoint explanations in [`docs/endpoint-guide.md`](docs/endpoint-guide.md).
