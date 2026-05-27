# ENIAK Build Plan

## Phase 0: Repository Bootstrap

Status: in progress.

Tasks:

- Create `/data/eniak` from `https://github.com/yupoet/eniak`.
- Add `.gitignore` and environment template.
- Create monorepo directory layout.
- Create `refs/` for local reference repositories and keep it ignored by git.
- Clone reference projects into `refs/`.

## Phase 1: Architecture Skeleton

Create backend package boundaries:

- `eniak.radar`
- `eniak.evidence`
- `eniak.orchestrator`
- `eniak.writer`
- `eniak.publisher`

Create app boundaries:

- `apps/api` for the backend API.
- `apps/web` for the frontend workspace.
- `packages/shared` for shared schemas and generated API types.

Deliverables:

- Architecture document.
- Data model draft.
- Backend package skeleton.
- Frontend workspace skeleton.

## Phase 2: Dry-Run Research Loop

Implement the first local-only workflow:

```text
topic config -> mock radar result -> evidence card -> chapter draft -> Feishu dry-run record
```

Deliverables:

- CLI command or API endpoint to run the loop.
- SQLite persistence.
- One frontend page showing runs, evidence cards, and draft output.
- Tests for the data model and dry-run workflow.

## Phase 3: Real Providers

Add real ingestion providers in this order:

1. arXiv
2. Semantic Scholar
3. OpenAlex
4. PubMed
5. generic web search
6. regulatory source adapters

Each provider must output normalized source candidates.

## Phase 4: Evidence Quality

Add:

- PDF retrieval and local storage.
- Text extraction.
- Citation metadata normalization.
- Evidence card generation.
- Claim-to-evidence linking.
- Basic contradiction detection.

## Phase 5: Writing and Publishing

Add:

- Book outline model.
- Chapter and section draft generation.
- Reference list generation.
- Feishu Doc/Wiki publishing adapter.
- Publish history and diff records.

## Review Checklist

Codex review should check:

- Is `refs/` fully ignored?
- Are secrets excluded?
- Are layers cleanly separated?
- Is the first dry-run loop small enough?
- Are evidence and citation objects first-class?
- Is Feishu publishing idempotent and review-gated?

