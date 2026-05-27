#!/usr/bin/env bash
# Create / upsert the DNS records ENIAK needs on eniak.org.
#
# Required env (loaded from /data/eniak/.env in dev):
#   CF_API_TOKEN
#   CF_ZONE_ID_ENIAK_ORG
#   ENIAK_FRONTEND_TARGET   (e.g. eniak-web.pages.dev)
#   ENIAK_API_TARGET        (e.g. eniak-api-production.up.railway.app)
#
# Usage: bash infra/scripts/cf_dns_setup.sh

set -euo pipefail

: "${CF_API_TOKEN:?CF_API_TOKEN is required}"
: "${CF_ZONE_ID_ENIAK_ORG:?CF_ZONE_ID_ENIAK_ORG is required}"
: "${ENIAK_FRONTEND_TARGET:?ENIAK_FRONTEND_TARGET is required (eniak-web.pages.dev)}"
: "${ENIAK_API_TARGET:?ENIAK_API_TARGET is required (xxx.up.railway.app)}"

api() {
  curl -sS -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" "$@"
}

upsert_record() {
  local name="$1" type="$2" content="$3" proxied="$4"
  local existing
  existing=$(
    api "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID_ENIAK_ORG/dns_records?name=$name&type=$type" \
      | python3 -c "import sys, json; r=json.load(sys.stdin)['result']; print(r[0]['id'] if r else '')"
  )
  local body
  body=$(printf '{"type":"%s","name":"%s","content":"%s","ttl":1,"proxied":%s}' \
    "$type" "$name" "$content" "$proxied")
  if [[ -n "$existing" ]]; then
    echo "↻ updating $type $name -> $content"
    api -X PUT "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID_ENIAK_ORG/dns_records/$existing" \
      --data "$body" >/dev/null
  else
    echo "+ creating $type $name -> $content"
    api -X POST "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID_ENIAK_ORG/dns_records" \
      --data "$body" >/dev/null
  fi
}

upsert_record "www.eniak.org" CNAME "$ENIAK_FRONTEND_TARGET" true
upsert_record "eniak.org"     CNAME "$ENIAK_FRONTEND_TARGET" true
upsert_record "api.eniak.org" CNAME "$ENIAK_API_TARGET"      true

echo "✓ DNS records upserted on eniak.org"
