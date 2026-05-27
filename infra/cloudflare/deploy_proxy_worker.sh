#!/usr/bin/env bash
# Deploy / update the api.eniak.org -> Railway proxy Worker.
#
# Why a Worker rather than Railway's own TLS cert?
#   Railway issues Let's Encrypt certs via HTTP-01 challenge against the origin,
#   which gets blocked when Cloudflare proxies the hostname. Running the entire
#   TLS chain through Cloudflare's Universal SSL (which covers *.eniak.org) plus
#   a tiny edge proxy lets us proxy api.eniak.org without waiting on Railway and
#   without round-trips through certbot's challenge dance.
#
# Required env (from /data/eniak/.env in dev):
#   CF_API_TOKEN
#   CF_ACCOUNT_ID
#   CF_ZONE_ID_ENIAK_ORG

set -euo pipefail

: "${CF_API_TOKEN:?}"; : "${CF_ACCOUNT_ID:?}"; : "${CF_ZONE_ID_ENIAK_ORG:?}"

WORKER_NAME="${WORKER_NAME:-eniak-api-proxy}"
SCRIPT_FILE="$(dirname "$0")/eniak-api-proxy.js"
ROUTE_PATTERN="${ROUTE_PATTERN:-api.eniak.org/*}"

echo "→ uploading Worker $WORKER_NAME"
curl -sS -X PUT \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/workers/scripts/$WORKER_NAME" \
  -F 'metadata={"main_module":"eniak-api-proxy.js","compatibility_date":"2026-01-01"};type=application/json' \
  -F "eniak-api-proxy.js=@$SCRIPT_FILE;type=application/javascript+module" \
  | python3 -c "import sys, json; r=json.load(sys.stdin); print('  ok' if r.get('success') else '  ERR: '+str(r.get('errors')))"

echo "→ ensuring route $ROUTE_PATTERN -> $WORKER_NAME"
EXISTING=$(curl -sS -H "Authorization: Bearer $CF_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID_ENIAK_ORG/workers/routes" \
  | python3 -c "
import sys, json
r = json.load(sys.stdin).get('result', [])
for x in r:
    if x.get('pattern') == '$ROUTE_PATTERN':
        print(x['id']); break")

if [[ -z "$EXISTING" ]]; then
  curl -sS -X POST \
    -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" \
    "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID_ENIAK_ORG/workers/routes" \
    --data "{\"pattern\":\"$ROUTE_PATTERN\",\"script\":\"$WORKER_NAME\"}" \
    | python3 -c "import sys, json; r=json.load(sys.stdin); print('  + route created' if r.get('success') else '  ERR: '+str(r.get('errors')))"
else
  echo "  ↻ route already exists ($EXISTING) — nothing to do"
fi
