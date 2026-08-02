# Vidyut operator-digest automation

This directory contains an importable n8n workflow that turns a completed Vidyut simulation into a real, auditable operator email.

The evaluator is the legitimate recipient: they are acting as the distribution-system operator. Simulated residents are never contacted. A resident-facing tariff message is included only as a clearly labelled preview.

## What the workflow proves

- a backend decision can leave the application as an operational digest;
- the PDF audit artifact is attached rather than merely linked;
- delivery state returns to Vidyut and becomes visible in the UI;
- transient recipient data does not become simulation master data; and
- automation failure does not affect the simulation core.

## Flow

```mermaid
flowchart LR
    UI["Operator enters email + consent"] --> API["Vidyut API"]
    API -->|"authenticated webhook + idempotency key"| Hook["n8n webhook"]
    Hook --> PDF["Download audit PDF"]
    PDF --> Gmail["Send simulated operator digest"]
    Gmail -->|"authenticated callback"| Delivered["Vidyut delivery state"]
    PDF -->|"error path"| Failed["Vidyut failure state"]
```

The webhook responds immediately. Gmail delivery continues asynchronously, avoiding duplicate backend retries while the email provider is working.

## Import and configure

1. Import [`vidyut-operator-digest.json`](vidyut-operator-digest.json) into n8n.
2. Create a **Header Auth** credential named `Vidyut webhook token`:
   - Header: `X-Vidyut-Webhook-Token`
   - Value: the same long random value used for `N8N_WEBHOOK_TOKEN` in the API.
3. Create another **Header Auth** credential named `Vidyut callback token`:
   - Header: `X-Vidyut-Callback-Token`
   - Value: the separate value used for `N8N_CALLBACK_TOKEN` in the API.
4. Select the webhook credential on **Receive Vidyut digest**.
5. Select the callback credential on **Confirm delivery to Vidyut** and **Report failure to Vidyut**.
6. Create or select a Gmail OAuth credential on **Send operator digest**.
7. In workflow settings, disable saving successful, failed, and manual execution data. This prevents n8n history from retaining the one-time recipient address.
8. Save, activate the workflow, and copy its **production** webhook URL.

Credentials are intentionally absent from the exported JSON. If an imported node is marked incomplete, reselect the appropriate named credential.

## Configure Vidyut

Copy the repository [`.env.example`](../../.env.example) to `.env` and set:

```dotenv
N8N_WEBHOOK_URL=https://YOUR_N8N_HOST/webhook/vidyut-operator-digest
N8N_WEBHOOK_TOKEN=use-a-long-random-value
N8N_CALLBACK_TOKEN=use-a-different-long-random-value
VIDYUT_PUBLIC_API_URL=http://localhost:8000
VIDYUT_N8N_API_URL=http://host.docker.internal:8000
DATABASE_URL=postgresql+psycopg://vidyut:vidyut@localhost:5433/vidyut
```

- `VIDYUT_PUBLIC_API_URL` is written into the email and must open in the recipient's browser.
- `VIDYUT_N8N_API_URL` is used by n8n for PDF download and delivery callbacks.
- When n8n runs in Docker but FastAPI runs on the host, `host.docker.internal` is normally the correct internal hostname.

When the Vidyut API also runs through Docker Compose, the included defaults use:

```dotenv
N8N_DOCKER_WEBHOOK_URL=http://host.docker.internal:5678/webhook/vidyut-operator-digest
VIDYUT_N8N_API_URL=http://host.docker.internal:8000
VIDYUT_PUBLIC_API_URL=http://localhost:8000
```

Restart the API after changing environment variables. The repository-root `.env` is canonical; `backend/.env` and `frontend/.env` are compatibility fallbacks for local development.

## Security and privacy

- Independent shared-secret headers protect the inbound webhook and delivery callback directions.
- Backend requests carry a stable `Idempotency-Key` derived from run ID and a truncated hash of the recipient address.
- Transient HTTP and network failures receive up to three attempts with exponential backoff.
- Client errors are not retried.
- Dispatch is limited to **3 sends per email hash per hour** and **10 sends per client IP per hour**.
- The raw email address is not written to the run record or Vidyut database.
- The subject and body explicitly say **simulated**.
- The workflow never contacts a simulated resident.

## Test end to end

1. Ensure the workflow is active; do not use “Listen for test event” with the production URL.
2. Run a fresh scenario in Simulation Lab.
3. Enter an operator email and accept the one-time-use consent statement.
4. Select **Send simulated operator digest**.
5. Confirm the UI changes to `accepted`.
6. Confirm the Gmail message arrives with the PDF attachment.
7. Open the report link and verify it uses the public API domain.
8. Confirm the UI changes to `delivered` after the callback.

If the frontend reports `403`, check that the n8n Header Auth value exactly matches `N8N_WEBHOOK_TOKEN`. If it reports `connection refused`, check container-versus-host URLs. If Gmail OAuth opens a blank window, verify the exact n8n origin and `/rest/oauth2-credential/callback` URI in the Google Cloud OAuth client.

Production setup is covered in the [Vercel + Azure deployment runbook](../../docs/deployment-vercel-azure.md).
