<div align="center">

# ENIAK

### Evidence-Native Intelligent Academic Kernel

*An open research operating layer for traceable, book-quality knowledge work.*

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: Phase 2](https://img.shields.io/badge/status-phase_2_dry--run-amber.svg)](docs/plan.md)
[![Site: eniak.org](https://img.shields.io/badge/site-www.eniak.org-c2410c.svg)](https://www.eniak.org)
[![API: api.eniak.org](https://img.shields.io/badge/api-api.eniak.org-c2410c.svg)](https://api.eniak.org/docs)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](#)
[![Node](https://img.shields.io/badge/node-20+-339933.svg?logo=node.js&logoColor=white)](#)
[![Frontend: Cloudflare Pages](https://img.shields.io/badge/frontend-Cloudflare%20Pages-F38020.svg?logo=cloudflare&logoColor=white)](https://pages.cloudflare.com)
[![Backend: Railway](https://img.shields.io/badge/backend-Railway-0B0D0E.svg?logo=railway&logoColor=white)](https://railway.com)
[![LLM: Kimi/Qwen](https://img.shields.io/badge/LLM-Aliyun%20Kimi%20%2F%20Qwen-FF6A00.svg)](#)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#contributing)

</div>

---

## What is ENIAK?

ENIAK is **not** another general agent framework. It is the kernel for a long-running research program that has to produce something a human is willing to put their name on — a chapter, a report, a literature review, an internal whitepaper, a book.

It optimises for the things most agent stacks treat as afterthoughts:

| Default in most agent stacks | ENIAK's bias |
|---|---|
| Fluent prose | **Evidence traceability** — every claim points back to a source |
| One-shot chat answers | **Durable research state** — runs are resumable, auditable, citable |
| Unchecked autonomy | **Human review gates** — nothing publishes without an approved state transition |
| Single-vendor lock-in | **Modular providers** — swap LLMs, search APIs, vector stores, publishers |
| Isolated reports | **Book-quality organisation** — parts, chapters, sections, cross-references |

Think of it as the operating layer between *"I have a research question"* and *"here is a chapter I can publish to Feishu / Wiki / PDF with every claim cited and every prompt versioned."*

## ENIAK 是什么？（中文）

ENIAK 不是又一个通用 Agent 框架，而是一个面向长周期研究项目的**操作内核**——为那些必须产出可署名内容（章节、报告、综述、白皮书、整本书）的研究流程而设计。

它把大部分 Agent 栈忽略的几件事当成一等公民：

- **证据可追溯**：每一个 claim 都能回溯到 source、检索时间、页码、prompt 版本。
- **研究状态持久化**：每一次 run 都可恢复、可审计、可引用。
- **人审门禁**：没有经过审核态切换的内容不会被发布。
- **多供应商**：LLM / 搜索 / 向量库 / 发布渠道都可换。
- **书的组织**：篇 / 章 / 节 / 交叉引用，而不是孤立的报告。

定位：从"我有一个研究问题"到"这是一篇可以发到飞书 / Wiki / PDF 的章节，每个论断都有出处、每个 prompt 都有版本"之间的那一层。

---

## Architecture

ENIAK is structured as a **hexagonal core with a workflow runtime**, not a strict 5-layer stack. The evidence model is the domain core; the other components are ports/adapters around it.

```
                            ┌──────────────────────────────┐
                            │       Workflow Runtime       │
                            │   (orchestrator / runtime)   │
                            └──────────────────────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
       ┌────────────┐           ┌─────────────────┐           ┌──────────────┐
       │   RADAR    │           │  EVIDENCE CORE  │           │    WRITER    │
       │            │   feeds   │                 │  fuels    │              │
       │ arXiv      │──────────▶│  Source         │──────────▶│ Outline      │
       │ S2 / OAlex │           │  Document       │           │ Chapter      │
       │ PubMed     │           │  EvidenceCard   │           │ FigureSpec   │
       │ Web search │           │  Citation       │           │ Bibliography │
       │ Regulators │           │  Claim          │           │              │
       └────────────┘           │  Contradiction  │           └──────────────┘
                                │  Run            │                  │
                                │  PromptTemplate │                  │
                                │  ReviewState    │                  ▼
                                │  CostLedger     │           ┌──────────────┐
                                └─────────────────┘           │  PUBLISHER   │
                                                              │              │
                                                              │ Markdown     │
                                                              │ Lark/Feishu  │
                                                              │ Quarto/PDF   │
                                                              └──────────────┘
```

Detailed design rationale lives in [`docs/brainstorm.md`](docs/brainstorm.md). The phase-by-phase build plan is in [`docs/plan.md`](docs/plan.md). The full reference index (15 pinned open-source projects we learn from) is in [`docs/references.md`](docs/references.md) and [`refs/MANIFEST.json`](refs/MANIFEST.json).

---

## Status / 当前状态

> **Phase 2 — Dry-run loop live.** Backend + frontend deployed. Mock radar feeds Qwen 3.5-plus extraction, citation-faithful chapter draft, Markdown export.

### Try it

- **UI:** https://www.eniak.org — enter a topic, get an evidence-cited draft in ~30-90s.
- **API:** https://api.eniak.org/docs — OpenAPI playground (`POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/chapter.md`).

### Pipeline (Phase 2)

```text
research topic → mock radar (3 sources) → LLM extracts evidence cards (1 call per source)
              → LLM drafts chapter citing card IDs → claim/citation graph persisted
              → Markdown export → CostLedger entry per call
```

See [`docs/plan.md`](docs/plan.md) for the full roadmap (Phase 0 → 5) and
[`docs/DEPLOY.md`](docs/DEPLOY.md) for the live deployment topology.

---

## Repository layout

```text
apps/
  api/                       # FastAPI + SQLAlchemy 2.0 backend (Railway)
    src/eniak_api/           # routers, config, app factory
    migrations/              # Alembic
    tests/                   # pytest dry-run end-to-end
  web/                       # Next.js 15 (App Router) frontend (Cloudflare Pages)
    src/app                  # routes
    src/components           # UI primitives
    src/lib/api.ts           # typed client of the FastAPI backend

packages/                    # Python workspace members (uv)
  eniak-evidence/            # Domain core: Source, Document, EvidenceCard, Claim, Citation,
                             #              Contradiction, Run, PromptTemplate, ReviewState, CostLedger,
                             #              Book, Chapter, Section
  eniak-radar/               # Source monitoring (mock in Phase 2; real providers in Phase 3)
  eniak-orchestrator/        # Workflow runtime (small explicit graph)
  eniak-writer/              # LiteLLM client + prompts
  eniak-publisher/           # Markdown (live) + Lark/Quarto/PDF (planned)

infra/
  docker/                    # docker-compose for local Postgres + pgvector
  scripts/cf_dns_setup.sh    # Idempotent DNS upsert on eniak.org

docs/
  brainstorm.md              # Architecture rationale
  plan.md                    # Phased build plan
  references.md              # Reference project index (15 pinned repos)
  DEPLOY.md                  # Live deployment topology + redeploy commands

refs/                        # 15 pinned open-source references for local study (gitignored)
  MANIFEST.json              # Pinned commit SHAs (tracked)

Dockerfile                   # Backend image (used by Railway)
railway.json                 # Railway deploy config
pyproject.toml               # uv workspace root
```

---

## Standing on the shoulders of...

ENIAK does not reinvent. It studies and ports from 15 pinned references — see [`refs/MANIFEST.json`](refs/MANIFEST.json) for the exact commit SHAs.

| Layer | Primary references |
|---|---|
| Orchestrator | [langgraph](https://github.com/langchain-ai/langgraph), [deer-flow](https://github.com/bytedance/deer-flow), [open_deep_research](https://github.com/langchain-ai/open_deep_research) |
| Evidence | [paper-qa](https://github.com/Future-House/paper-qa), [graphiti](https://github.com/getzep/graphiti) |
| Writer | [storm](https://github.com/stanford-oval/storm), [LongWriter](https://github.com/THUDM/LongWriter), [quarto-cli](https://github.com/quarto-dev/quarto-cli) |
| Publisher | [research-claw](https://github.com/nanoAgentTeam/research-claw), [oapi-sdk-python](https://github.com/larksuite/oapi-sdk-python) |
| Prompts / Cost / Eval | [langfuse](https://github.com/langfuse/langfuse), [litellm](https://github.com/BerriAI/litellm), [phoenix](https://github.com/Arize-ai/phoenix), [agentevals](https://github.com/langchain-ai/agentevals) |
| Skill banks | [ljg-skills](https://github.com/lijigang/ljg-skills), [de-anthropocentric-research-engine](https://github.com/yogsoth-ai/de-anthropocentric-research-engine) |

When a pattern is ported, the design doc cites the pinned SHA — e.g. *"ported from `storm@fb951af7`"*.

---

## Bring your own keys

ENIAK ships no API keys. Copy the template and fill in what you need:

```bash
cp .env.example .env
```

Required at minimum for the dry-run loop: an LLM gateway (`OPENAI_API_KEY` or any LiteLLM-compatible provider). Optional but recommended: Semantic Scholar, Tavily / Brave / Serper for web search, Lark App credentials for Feishu publishing.

Storage default is SQLite for development; Postgres + pgvector is the canonical target (see `infra/docker/`).

---

## Contributing

This repo is in **Phase 0**. Issues and design feedback are welcome, especially on:

- The hexagonal-vs-layered architecture question (see `docs/brainstorm.md`)
- The Python-primary vs polyglot monorepo decision (see `docs/plan.md` Phase 1)
- Missing reference projects worth pinning into `refs/MANIFEST.json`

PRs that add code are deferred until Phase 1 closes.

---

## License

[Apache License 2.0](LICENSE) — see also [`NOTICE`](NOTICE).

Referenced projects under `refs/` (gitignored) each retain their own upstream licenses.

---

<div align="center">

*"Evidence-native, human-gated, book-shaped."*

</div>
