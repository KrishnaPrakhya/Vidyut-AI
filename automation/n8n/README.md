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
VIDYUT_PUBLIC_API_URL=https://YOUR_PUBLIC_API_HOST
```

`VIDYUT_PUBLIC_API_URL` must be reachable from n8n because it is used for the PDF download and delivery callback. For a local n8n instance running on the same machine, `http://host.docker.internal:8000` is usually appropriate.

The API rate-limits each hashed email to 3 sends/hour and each client IP to 10 sends/hour. It never writes the email address to the run record or database.

The workflow uses n8n's documented Gmail attachment field and generic Header Auth support. If an imported node is marked incomplete, reselect its named credential; credentials are intentionally not exported with the workflow.
