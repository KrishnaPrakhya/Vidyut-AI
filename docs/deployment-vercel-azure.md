# Vidyut deployment: Vercel + Azure

This runbook deploys the Next.js frontend to Vercel and the stateful runtime to a single Azure Ubuntu VM. Cloudflare is used only as the DNS provider for the existing domain.

## 0. Publish the deployment files

Vercel and the Azure VM can only see committed code. From the repository root on your development machine, review and publish the prepared files:

```bash
git add .gitattributes .gitignore deploy/azure docs/deployment-vercel-azure.md frontend/env.production.example frontend/vercel.json
git commit -m "add Azure and Vercel deployment configuration"
git push origin test-backend
```

Do not add `deploy/azure/env.production`, `frontend/env.production`, the root `.env`, or n8n credential exports. Those contain production secrets and are ignored intentionally.

## 1. Final architecture

| Public name | Runtime | Purpose |
| --- | --- | --- |
| `app.example.com` | Vercel | Next.js user interface and Groq-backed server route |
| `api.example.com` | Azure VM / Caddy / FastAPI | REST API, WebSocket replay, reports and callbacks |
| `ops.example.com` | Azure VM / Caddy / n8n | Private operator workflow editor and Gmail OAuth callback |

Inside the VM, FastAPI calls `http://n8n:5678`, n8n calls `http://api:8000`, and PostgreSQL has no public port. Only Caddy publishes TCP 80 and TCP/UDP 443.

## 2. Values to decide first

Replace these examples everywhere:

```text
Frontend: app.example.com
API:      api.example.com
n8n:      ops.example.com
Region:   Central India
VM user:  azureuser
```

Use `Standard_B2s` (2 vCPU, 4 GiB RAM) for the judging period. The smaller 1 GiB machines are not suitable for FastAPI/pandapower, n8n and PostgreSQL together.

## 3. Create the Azure VM

In Azure Portal:

1. Create a resource group named `vidyut-rg` in **Central India**.
2. Create an **Ubuntu Server 24.04 LTS Gen2** VM in that group.
3. Select size **Standard_B2s**.
4. Use SSH public-key authentication. Download and protect the private key.
5. Use a 32 GiB Standard SSD OS disk; Premium SSD is unnecessary for this demo.
6. Keep a Standard static public IPv4 address.
7. In the Network Security Group allow:
   - SSH/TCP 22 from **My IP**, not from the entire Internet.
   - HTTP/TCP 80 from the Internet.
   - HTTPS/TCP 443 from the Internet.
8. Do not open ports 5432, 5678 or 8000.
9. Under VM **Auto-shutdown**, set a safe time outside demo hours.
10. Add a subscription budget and alerts at 50%, 80% and 100% of the intended student-credit spend.

Record the VM's static public IP as `AZURE_VM_IP`.

## 4. Configure DNS

In Cloudflare DNS create these records with **Proxy status: DNS only** initially:

| Type | Name | Target |
| --- | --- | --- |
| A | `api` | `AZURE_VM_IP` |
| A | `ops` | `AZURE_VM_IP` |

DNS-only mode lets Caddy complete its initial TLS certificate challenge directly. Do not create public records for PostgreSQL or port 8000.

For the frontend, add the custom domain inside Vercel first. Vercel will display the exact A or CNAME record it requires. Add that exact record in Cloudflare DNS rather than copying a generic value from an old tutorial.

Check propagation:

```bash
nslookup api.example.com
nslookup ops.example.com
```

Both must resolve to `AZURE_VM_IP` before starting Caddy.

## 5. Install the Azure runtime

Connect from your computer:

```bash
ssh -i /path/to/azure-key.pem azureuser@AZURE_VM_IP
```

Clone the deployed branch and install Docker:

```bash
git clone --branch test-backend https://github.com/KrishnaPrakhya/Vidyut-AI.git
cd Vidyut-AI
sudo bash deploy/azure/bootstrap.sh
```

Log out and reconnect so Docker group membership takes effect:

```bash
exit
ssh -i /path/to/azure-key.pem azureuser@AZURE_VM_IP
cd Vidyut-AI
```

Create the ignored production environment file:

```bash
cp deploy/azure/env.production.example deploy/azure/env.production
```

Generate four independent secrets. Run the command separately for the PostgreSQL password, n8n encryption key, webhook token and callback token:

```bash
openssl rand -hex 32
```

Edit the file:

```bash
nano deploy/azure/env.production
```

Example shape, with real domains and generated values replacing every placeholder:

```dotenv
API_DOMAIN=api.example.com
N8N_DOMAIN=ops.example.com
FRONTEND_ORIGIN=https://app.example.com
TLS_EMAIL=your-address@example.com
POSTGRES_DB=vidyut
POSTGRES_USER=vidyut
POSTGRES_PASSWORD=<generated-value-1>
N8N_ENCRYPTION_KEY=<generated-value-2>
N8N_WEBHOOK_TOKEN=<generated-value-3>
N8N_CALLBACK_TOKEN=<generated-value-4>
VIDYUT_SIM_VERSION=production
```

Never put these secrets in Git, Vercel public variables, screenshots or chat messages.

Deploy:

```bash
bash deploy/azure/deploy.sh
```

Inspect startup if necessary:

```bash
docker compose --env-file deploy/azure/env.production -f deploy/azure/docker-compose.prod.yml ps
docker compose --env-file deploy/azure/env.production -f deploy/azure/docker-compose.prod.yml logs --tail=100 api
docker compose --env-file deploy/azure/env.production -f deploy/azure/docker-compose.prod.yml logs --tail=100 caddy
```

Verify HTTPS:

```bash
curl https://api.example.com/api/health
```

The response must report the database as connected and all automation configuration booleans as true.

## 6. Configure production n8n

1. Open `https://ops.example.com` and create the production owner account.
2. Import `automation/n8n/vidyut-operator-digest.json`.
3. Create **Vidyut webhook token** using Header Auth:
   - Header: `X-Vidyut-Webhook-Token`
   - Value: the production `N8N_WEBHOOK_TOKEN`.
4. Create **Vidyut callback token** using Header Auth:
   - Header: `X-Vidyut-Callback-Token`
   - Value: the production `N8N_CALLBACK_TOKEN`.
5. Assign the webhook credential only to **Receive Vidyut digest**.
6. Assign the callback credential to **Confirm delivery to Vidyut** and **Report failure to Vidyut**.
7. Create or reconnect the Gmail OAuth credential and assign it to **Send operator digest**.
8. In workflow settings, disable saving successful, failed and manual execution data so the one-time recipient address is not retained.
9. Save and activate the workflow.

For Google OAuth, create a Web application client with:

```text
Authorized JavaScript origin:
https://ops.example.com

Authorized redirect URI:
https://ops.example.com/rest/oauth2-credential/callback
```

Enable the Gmail API and add the sender Gmail account as a test user while the OAuth consent screen remains in Testing mode.

## 7. Deploy the frontend to Vercel

1. In Vercel select **Add New → Project** and import `KrishnaPrakhya/Vidyut-AI`.
2. Set **Root Directory** to `frontend`.
3. Keep framework preset **Next.js**.
4. Set the production branch to `test-backend` until the deployment changes are merged to `main`.
5. Add these environment variables for Production:

```dotenv
NEXT_PUBLIC_API_URL=https://api.example.com
NEXT_PUBLIC_SITE_URL=https://app.example.com
GROQ_API_KEY=<your-existing-groq-key>
```

`NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_SITE_URL` are intentionally browser-visible. `GROQ_API_KEY` is server-only and must never use the `NEXT_PUBLIC_` prefix.

6. Deploy and wait for the production build to pass.
7. Add `app.example.com` under **Settings → Domains**.
8. Add the exact DNS record Vercel displays in Cloudflare.
9. Redeploy if either `NEXT_PUBLIC_` value changes; Next.js embeds those values during the build.

If using the generated `*.vercel.app` hostname instead of a custom frontend domain, set `FRONTEND_ORIGIN` on Azure to that exact HTTPS origin and rerun `deploy.sh`.

## 8. Production verification

From a local Python 3 installation:

```bash
python scripts/demo_check.py \
  --api https://api.example.com \
  --frontend https://app.example.com
```

Then perform the email path once:

1. Open Simulation Lab.
2. Run a fresh heatwave simulation.
3. Enter the operator email and consent.
4. Send the simulated operator digest.
5. Confirm the email arrives with a PDF.
6. Confirm **Open the auditable simulation report** uses `https://api.example.com`.
7. Confirm the UI reaches `delivered` and the notification outbox becomes empty.

Also verify the browser developer console contains no mixed-content or CORS errors and that replay WebSockets use `wss://api.example.com`.

## 9. Updating the deployment

On the Azure VM:

```bash
cd ~/Vidyut-AI
git pull --ff-only origin test-backend
bash deploy/azure/deploy.sh
```

Vercel redeploys automatically after a push to its production branch. Do not regenerate `N8N_ENCRYPTION_KEY`; changing it makes stored n8n credentials unreadable.

## 10. Backup and recovery

Create a PostgreSQL backup before major changes:

```bash
docker compose --env-file deploy/azure/env.production \
  -f deploy/azure/docker-compose.prod.yml \
  exec -T postgres pg_dump -U vidyut -d vidyut > vidyut-backup.sql
```

Back up the n8n volume and production environment file to an encrypted location. Never commit either one.

If a new code revision fails, switch the VM working tree to a previously known commit and rerun `deploy.sh`. Database volumes are not removed by normal `docker compose up` operations. Never use `docker compose down --volumes` on the production VM.

## 11. Cost control

Use Azure's **Stop (deallocate)** action when the demo is not needed. A shutdown inside Ubuntu alone may continue allocating compute. The site and n8n automation will be unavailable while the VM is deallocated; Vercel's frontend can remain online but will show its recorded/offline state.
