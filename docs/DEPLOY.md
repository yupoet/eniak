# Deploying ENIAK

Live as of 2026-05-27 (post-Supabase + OpenNext migration):

| Surface | URL | Host |
|---|---|---|
| Frontend | https://www.eniak.org · https://eniak.org | Cloudflare Workers (OpenNext build of Next.js 15) |
| Backend | https://api.eniak.org | Railway (`eniak-api-production.up.railway.app`) via Cloudflare Worker proxy |
| Database | Supabase Postgres 17 (`db.jkpqhiepvitzxweatqfn.supabase.co`) + pgvector | session pooler 5432 for Alembic, transaction pooler 6543 for app |
| LLM | Aliyun DashScope coding plan (Qwen 3.5-plus) | `https://coding.dashscope.aliyuncs.com/v1` |
| Auth | Bearer token on POST /runs | rotated key in `ENIAK_API_KEYS` on Railway + `ENIAK_API_KEY` Worker secret |

## What the deploy did

```text
Cloudflare Workers:
  ✓ Worker     eniak-web (OpenNext build of Next.js — full SSR + assets binding)
  ✓ custom_domain bindings declared in apps/web/wrangler.jsonc:
                  www.eniak.org, eniak.org
  ✓ secret     ENIAK_API_KEY (used by /app/api/runs route handler to call backend)
  ✓ vars       NEXT_PUBLIC_API_BASE=https://api.eniak.org

  ✓ Worker     eniak-api-proxy (rewrites Host for api.eniak.org -> Railway)
  ✓ route      api.eniak.org/* -> eniak-api-proxy

Cloudflare DNS (zone eniak.org):
  ✓ All A/CNAME records created automatically by `wrangler deploy` per the
    custom_domain bindings. infra/scripts/cf_dns_setup.sh is kept for DR only.

Supabase:
  ✓ project    eniak (jkpqhiepvitzxweatqfn) in ap-southeast-1
  ✓ extension  pgvector enabled
  ✓ schema     11 tables migrated via Alembic (revision 9eef2ff220cc)

Railway (workspace: Paris Y.'s Projects):
  ✓ project    eniak (80368c35-863b-4bbd-a02f-f3c32d4be400)
  ✓ service    eniak-api (942e79ae-a730-4a7a-a4b6-b40bf2449f27)
  ✓ env vars   LLM_API_KEY, LLM_BASE_URL, ENIAK_DEFAULT_MODEL, ENIAK_ENV=production,
               ENIAK_CORS_ORIGINS, PORT=8000, ENIAK_API_KEYS,
               DATABASE_URL=postgresql+asyncpg://...@aws-1-ap-southeast-1.pooler.supabase.com:6543/...,
               DATABASE_URL_DIRECT=postgresql+psycopg://...:5432/postgres
  ✓ domain     api.eniak.org via the Cloudflare Worker proxy (no Railway-issued cert needed)
  ✓ deployed   via `railway up --service eniak-api --ci`
```

## Re-deploying

### Frontend (Cloudflare Workers via OpenNext)

```bash
cd apps/web
# First-time only: register the secret on the Worker.
echo "$ENIAK_API_KEY" | npx wrangler secret put ENIAK_API_KEY --name eniak-web

# Build + deploy.
CLOUDFLARE_API_TOKEN=$CF_API_TOKEN CLOUDFLARE_ACCOUNT_ID=$CF_ACCOUNT_ID \
  npm run deploy
```

`wrangler.jsonc` declares the custom domains (`www.eniak.org`, `eniak.org`); the
deploy creates the routes + DNS records automatically.

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
