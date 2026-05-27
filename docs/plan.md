# ENIAK Build Plan

Status timeline (current as of 2026-05-28):

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — Repository bootstrap | ✅ done | scaffold, refs/, LICENSE, design docs |
| Phase 1 — Architecture skeleton | ✅ done | uv workspace, hexagonal core, Pydantic→TS plan |
| Phase 2 — Dry-run loop | ✅ done | mock radar → evidence → chapter, persisted on Supabase |
| Phase 3 — Real providers | ✅ done | arXiv + OpenAlex live, parallel extraction |
| Phase 4 — Evidence quality | ✅ done | PDF fetch + page-aware quote + contradiction detection |
| Phase 5 — Writing + publishing | ✅ done | Book builder + Markdown + Feishu (dry-run/live) + state machine |
| Phase 6 — Reviewer UX & eval | planned | accept/reject UI exists; eval harness via Phoenix + agentevals is next |

## Phase 0: Repository Bootstrap (done)

- `/data/eniak` initialised against `https://github.com/yupoet/eniak`
- `.gitignore`, `.env.example`, Apache-2.0 LICENSE + NOTICE
- `refs/MANIFEST.json` pins 15 reference projects (gitignored bodies)
- Design docs in `docs/`

## Phase 1: Architecture Skeleton (done)

- uv workspace with members: `apps/api`, `packages/eniak-{evidence,radar,orchestrator,writer,publisher}`
- Hexagonal layout — `evidence` is the domain core; radar / writer / publisher are ports
- Apps: `apps/api` (FastAPI on Railway) + `apps/web` (Next.js on Cloudflare Workers via OpenNext)
- `packages/eniak-evidence/schemas.py` is the canonical Pydantic surface, mirrored to TypeScript in `apps/web/src/lib/api-types.ts`

## Phase 2: Dry-run loop (done)

Pipeline: `topic → mock radar → evidence card → chapter draft → markdown export`. Citation invariant enforced (no cite-all fallback). Bearer-token auth + per-IP rate limit on POST. Live at `https://api.eniak.org/runs`.

## Phase 3: Real providers (done)

`eniak_radar.registry.RadarFanout` runs arXiv + OpenAlex in parallel, dedupes by DOI/arxiv id, ranks by relevance. Falls back to MockRadar when both return empty. Selected via `ENIAK_RADAR_PROVIDERS` (default `arxiv,openalex`). Evidence extraction LLM calls run in parallel with a 4-wide semaphore so a 3-source run takes ~30-60s instead of ~3 min.

## Phase 4: Evidence quality (done)

- `eniak_radar.pdf.fetch_and_extract` downloads a PDF over HTTPS, runs pypdf, returns per-page text with `[page N]` markers.
- The orchestrator threads the PDF text into the extraction prompt; the LLM returns `page` + `section` for each evidence card.
- `eniak_orchestrator.dry_run` runs one extra LLM pass to detect contradictions between cards in a run and persists `Contradiction` rows. Surfaced on `/runs/{id}`.
- Toggles: `ENIAK_FETCH_PDFS=true`, `ENIAK_DETECT_CONTRADICTIONS=true`.

## Phase 5: Writing + publishing (done)

- `BookOrchestrator` plans an outline (`title + chapters + themes`) then runs the dry-run loop per chapter, persisting `Chapter` rows under one `Book`.
- New endpoints: `POST /books`, `GET /books`, `GET /books/{id}`, `POST /books/{id}/publish/{chapter_id}`, `GET /books/{id}/publish`.
- `MarkdownPublisher` (live since Phase 2) and `FeishuPublisher` (Phase 5) implement a common `Publisher` shape. `FeishuPublisher` renders the chapter as Lark docx blocks; dry-run mode returns the block JSON, live mode hits `/docx/v1/documents` + `/blocks/batch_update` using `LARK_APP_ID` + `LARK_APP_SECRET`.
- `PublishRecord` table tracks every emission with `target`, `mode`, `external_id`, `external_url`, `version`. Idempotent — chapter row's `review_state` flips to `published` only on successful `mode=live`.
- Review state machine endpoints: `PATCH /runs/{id}/cards/{card_id}` and `PATCH /chapters/{id}`. Transition table enforced server-side; illegal moves return 409.
- Frontend: `/books` index + form, `/books/{id}` per-chapter review panel with accept/reject buttons + publish buttons. `/runs/{id}` shows contradictions and lets you accept/reject individual evidence cards.

## Phase 6: Reviewer UX + eval (next)

Planned:

- Cumulative cost dashboard (CostLedger groupings by book + by model)
- Eval harness: hand-curated dataset → metrics on retrieval recall + citation faithfulness, surfaced as a `/eval` page that runs daily
- Better evidence card annotation (free-text + rubric scoring)
- Multi-tenant: Supabase Auth on the frontend, runs scoped to user
- Cross-chapter consistency check (one chapter's claims shouldn't contradict another's)

## Review Checklist (kept current)

Codex review should check:

- [x] Is `refs/` fully ignored?
- [x] Are secrets excluded? (`.env` gitignored; Worker secrets used for API key)
- [x] Are layers cleanly separated? (radar / evidence / writer / publisher hexagonal)
- [x] Is the first dry-run loop small enough? (≈150 lines for Phase 2 happy path)
- [x] Are evidence and citation objects first-class? (own tables, citation invariant enforced)
- [x] Is Feishu publishing idempotent and review-gated? (PublishRecord versioning, `live` requires `approved`)
