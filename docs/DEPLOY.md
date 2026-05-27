# Deploying ENIAK

Live as of 2026-05-27:

| Surface | URL | Host |
|---|---|---|
| Frontend | https://www.eniak.org · https://eniak.org | Cloudflare Pages (`eniak-web.pages.dev`) |
| Backend | https://api.eniak.org | Railway (`eniak-api-production.up.railway.app`) |
| Database | SQLite (`/tmp/eniak.sqlite3` on Railway, ephemeral) | local-only for Phase 2; Supabase Postgres planned |
| LLM | Aliyun DashScope coding plan (Qwen 3.5-plus) | `https://coding.dashscope.aliyuncs.com/v1` |

## What the bootstrap script did

```text
Cloudflare Pages:
  ✓ created project          eniak-web
  ✓ attached custom domains  www.eniak.org, eniak.org
  ✓ set env var              NEXT_PUBLIC_API_BASE=https://api.eniak.org
  ✓ deployed                 .vercel/output/static built via @cloudflare/next-on-pages

Cloudflare DNS (zone eniak.org):
  ✓ CNAME  www.eniak.org -> eniak-web.pages.dev   (proxied)
  ✓ CNAME  eniak.org     -> eniak-web.pages.dev   (proxied)
  ✓ CNAME  api.eniak.org -> d8184t7d.up.railway.app  (unproxied — Railway needs origin SNI)

Railway (workspace: Paris Y.'s Projects):
  ✓ project    eniak (80368c35-863b-4bbd-a02f-f3c32d4be400)
  ✓ service    eniak-api (942e79ae-a730-4a7a-a4b6-b40bf2449f27)
  ✓ env vars   LLM_API_KEY, LLM_BASE_URL, ENIAK_DEFAULT_MODEL, ENIAK_ENV=production,
               ENIAK_CORS_ORIGINS, PORT=8000, DATABASE_URL=sqlite+aiosqlite:////tmp/...
  ✓ domain     api.eniak.org (custom) + eniak-api-production.up.railway.app (default)
  ✓ deployed   via `railway up --service eniak-api --ci`
```

## Re-deploying

### Frontend (Cloudflare Pages)

```bash
cd apps/web
npx @cloudflare/next-on-pages
CLOUDFLARE_API_TOKEN=$CF_API_TOKEN CLOUDFLARE_ACCOUNT_ID=$CF_ACCOUNT_ID \
  npx wrangler pages deploy .vercel/output/static \
    --project-name=eniak-web --branch=main --commit-dirty=true
```

### Backend (Railway)

Two options.

**A. From local dir (autonomous, no GitHub link):**

```bash
# Get a fresh project token (or reuse an existing one from the Railway dashboard)
TOKEN=$(curl -sS -X POST \
  -H "Authorization: Bearer $RAILWAY_ACCOUNT_TOKEN" \
  -H "Content-Type: application/json" \
  https://backboard.railway.app/graphql/v2 \
  --data '{"query":"mutation { projectTokenCreate(input: { projectId: \"80368c35-863b-4bbd-a02f-f3c32d4be400\", environmentId: \"a3f56513-b0be-4ce5-86c7-a2ae053755b6\", name: \"deploy\" }) }"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['projectTokenCreate'])")

RAILWAY_TOKEN="$TOKEN" railway up --service eniak-api --ci
```

**B. GitHub-triggered:** in the Railway dashboard, connect the `eniak-api` service to `yupoet/eniak` on branch `main`. Subsequent pushes auto-deploy.

## DNS recovery (if records get nuked)

```bash
# Loads .env then upserts CNAMEs
bash infra/scripts/cf_dns_setup.sh
```

with `CF_API_TOKEN`, `CF_ZONE_ID_ENIAK_ORG`, `ENIAK_FRONTEND_TARGET=eniak-web.pages.dev`,
`ENIAK_API_TARGET=d8184t7d.up.railway.app` set in env.

## Promoting the database to Supabase Postgres

When ready (Phase 3):

1. Create a Supabase project (any region close to ap-southeast-1 for latency to DashScope).
2. Enable the `pgvector` extension in the Supabase SQL editor: `create extension if not exists vector;`.
3. Run migrations:
   ```bash
   DATABASE_URL=postgresql+asyncpg://postgres.xxxx:PASS@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres \
   DATABASE_URL_DIRECT=postgresql://postgres:PASS@db.xxxx.supabase.co:5432/postgres \
   uv run --package eniak-api alembic upgrade head
   ```
4. In Railway, update `DATABASE_URL` to the Supabase pooler URL and redeploy.
5. Remove the SQLite-on-/tmp fallback by also setting `DATABASE_URL_DIRECT` (Alembic uses this).

## Logs

- Frontend: Cloudflare Pages dashboard → eniak-web → Functions → Real-time logs
- Backend: `railway logs --service eniak-api` (with the project token), or the Railway dashboard

## Why api.eniak.org goes through a Cloudflare Worker

Railway's custom-domain TLS issuance uses HTTP-01 ACME challenges hitting the
origin. With Cloudflare proxying api.eniak.org, those challenges never reach
Railway and the certificate sits in `VALIDATING_OWNERSHIP` indefinitely.

Solution: skip Railway's cert entirely.

- `infra/cloudflare/eniak-api-proxy.js` — tiny Worker that rewrites the `Host`
  header from `api.eniak.org` → `eniak-api-production.up.railway.app` so
  Railway's router recognises the request.
- `infra/cloudflare/deploy_proxy_worker.sh` — idempotent deploy script that
  uploads the Worker and binds the `api.eniak.org/*` route.

Public TLS is served by Cloudflare's Universal SSL (Let's Encrypt cert covering
`*.eniak.org`). Origin TLS to Railway uses the existing `*.up.railway.app` cert
in "Full" mode. No certbot, no waiting.

To redeploy:

```bash
bash infra/cloudflare/deploy_proxy_worker.sh
```
