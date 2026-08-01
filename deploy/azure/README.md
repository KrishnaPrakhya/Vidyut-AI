# Azure runtime

This directory deploys the Vidyut API, PostgreSQL, n8n and Caddy on one Ubuntu VM.

```bash
sudo bash deploy/azure/bootstrap.sh
# Log out and back in after Docker installation.
cp deploy/azure/env.production.example deploy/azure/env.production
nano deploy/azure/env.production
bash deploy/azure/deploy.sh
```

Only Caddy publishes ports. PostgreSQL, FastAPI and n8n communicate over private Docker networks. Caddy obtains and renews TLS certificates after the API and n8n DNS records point to the VM.

The complete portal, DNS, Vercel, n8n, OAuth, verification and rollback procedure is in [`docs/deployment-vercel-azure.md`](../../docs/deployment-vercel-azure.md).
