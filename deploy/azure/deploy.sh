#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.prod.yml"
ENV_FILE="${1:-${SCRIPT_DIR}/env.production}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy env.production.example and fill every value." >&2
  exit 1
fi

if grep -Eq '(^|=)(CHANGE_ME|.*\.example\.com)' "${ENV_FILE}"; then
  echo "Deployment stopped: ${ENV_FILE} still contains placeholder values." >&2
  exit 1
fi

cd "${REPO_ROOT}"
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" config --quiet
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" pull postgres n8n caddy
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" build --pull api
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --remove-orphans
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps

echo
echo "Deployment started. After DNS and TLS settle, verify:"
echo "  https://$(grep '^API_DOMAIN=' "${ENV_FILE}" | cut -d= -f2)/api/health"
