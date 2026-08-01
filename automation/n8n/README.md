# Vidyut operator digest automation

This workflow sends one real email to the evaluator acting as the distribution-system operator. It never pretends to contact simulated residents. The resident notification appears only as a labelled preview.

## Configure n8n

1. Import `vidyut-operator-digest.json` into n8n.
2. Create a **Header Auth** credential named `Vidyut webhook token`:
   - Header: `X-Vidyut-Webhook-Token`
   - Value: the same random value used for `N8N_WEBHOOK_TOKEN` in the API.
3. Create a second **Header Auth** credential named `Vidyut callback token`:
   - Header: `X-Vidyut-Callback-Token`
   - Value: the same random value used for `N8N_CALLBACK_TOKEN` in the API.
4. Select those credentials on the webhook and both callback nodes. Select the Gmail OAuth credential on **Send operator digest**.
5. Check workflow settings and keep successful, failed, and manual execution data saving disabled. This prevents the transient recipient address from being retained in n8n execution history.
6. Activate the workflow and copy its production webhook URL.

The webhook replies immediately, so Vidyut does not retry while Gmail is still sending. n8n then downloads the run PDF, attaches it, sends the HTML digest, and calls the authenticated Vidyut delivery endpoint. The UI polls that state and changes from **accepted** to **delivered**.

## Configure Vidyut

Copy `.env.example` to `.env` and set:

```dotenv
N8N_WEBHOOK_URL=https://YOUR_N8N_HOST/webhook/vidyut-operator-digest
N8N_WEBHOOK_TOKEN=use-a-long-random-value
N8N_CALLBACK_TOKEN=use-a-different-long-random-value
VIDYUT_PUBLIC_API_URL=http://localhost:8000
VIDYUT_N8N_API_URL=http://host.docker.internal:8000
DATABASE_URL=postgresql+psycopg://vidyut:vidyut@localhost:5433/vidyut
```

`VIDYUT_PUBLIC_API_URL` is written into the operator email and must be reachable from the operator's browser. `VIDYUT_N8N_API_URL` is used only for PDF download and delivery callbacks from n8n. When n8n runs in Docker, `host.docker.internal` is usually appropriate for that internal URL.

Put backend values in the repository-root `.env` (or `backend/.env`) and restart the API. Local development also reads `frontend/.env` as a compatibility fallback, but keeping n8n secrets beside frontend configuration is discouraged.

When the Vidyut API also runs through Docker Compose, use the Docker-specific overrides below. The included defaults already match a local n8n container and the supplied workflow path:

```dotenv
N8N_DOCKER_WEBHOOK_URL=http://host.docker.internal:5678/webhook/vidyut-operator-digest
VIDYUT_N8N_API_URL=http://host.docker.internal:8000
VIDYUT_PUBLIC_API_URL=http://localhost:8000
```

The API rate-limits each hashed email to 3 sends/hour and each client IP to 10 sends/hour. It never writes the email address to the run record or database.

The workflow uses n8n's documented Gmail attachment field and generic Header Auth support. If an imported node is marked incomplete, reselect its named credential; credentials are intentionally not exported with the workflow.
