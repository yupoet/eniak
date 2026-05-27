# Reference Projects

Reference repositories are cloned into `refs/` for local reading only. They are not part of the ENIAK repository history. The pinned commit SHAs live in [`refs/MANIFEST.json`](../refs/MANIFEST.json) and should be cited when porting a pattern (e.g. "ported from storm@fb951af7").

## How to read this index

Each ref maps to one or more ENIAK layers (radar / evidence / orchestrator / writer / publisher) or to cross-cutting concerns (model gateway, prompts, cost, eval, observability). Fit ratings:

- **STRONG** — direct port candidate or canonical reference for a problem ENIAK actually has.
- **OK** — useful background or partial overlap; do not treat as architecture template.

## Active references

### Orchestrator

- **`refs/langgraph`** — STRONG. Durable graph runtime with checkpointers (Postgres / SQLite) and HITL interrupts. Candidate substrate for Phase 3+; **not used in Phase 2**.
- **`refs/deer-flow`** — STRONG. ByteDance super-agent harness with skills, sub-agents, sandboxes, memory, MCP. Closest end-to-end architectural twin.
- **`refs/open_deep_research`** — OK. LangGraph-native deep-research blueprint; useful as a worked example of langgraph multi-agent patterns.

### Evidence

- **`refs/paper-qa`** — STRONG. Scientific-document RAG with PDF chunking, citation grounding, and agentic retrieval. Directly transplantable to `EvidenceCard` generation.
- **`refs/graphiti`** — STRONG. Bi-temporal knowledge graph (`Episode → EntityNode → EntityEdge`) with validity windows and hybrid (BM25 + vector + rerank) search. Model for ENIAK's cross-document claim/citation graph.

### Writer

- **`refs/storm`** — STRONG. Two-stage outline → article with multi-perspective question asking and Co-STORM mind-map. Best long-form structured writing reference; no substitute.
- **`refs/LongWriter`** — STRONG. AgentWrite `plan → write-per-paragraph → stitch` pipeline for >10k-word outputs (ICLR 2025). Port as the chapter expansion stage.
- **`refs/quarto-cli`** — STRONG. Book project layout (`_quarto.yml`, parts, chapters, cross-refs via `@sec-foo`). Writer should emit Quarto-flavored Markdown; Publisher exports.

### Publisher

- **`refs/research-claw`** — STRONG. Self-hosted research assistant with `channels/feishu.py`, project/session model, Overleaf + Git sync. Only ref that already implements a Feishu publishing channel.
- **`refs/oapi-sdk-python`** — STRONG. Official Lark/Feishu v2 Python SDK. Source for the docx block schema, wiki node API, and tenant token auto-refresh pattern.

### Cross-cutting

- **`refs/litellm`** — STRONG. OpenAI-format unification across 100+ providers, built-in cost-per-call, budget manager, retry semantics. Drop-in for the ENIAK model layer.
- **`refs/langfuse`** — STRONG. Content-addressed prompt registry with labels (`production` / `staging`) + token/cost ledger + tracing. Source of truth for `PromptTemplate` and `CostLedger` entities.
- **`refs/phoenix`** — STRONG. OTel traces + LLM-as-judge + datasets/experiments. Eval harness for retrieval recall and citation faithfulness. **Caveat: ELv2 license, self-host only.**
- **`refs/agentevals`** — OK. Lightweight trajectory match (strict / unordered / subset) + LLM-as-judge. Wire into orchestrator regression tests.

### Radar + skill banks

- **`refs/de-anthropocentric-research-engine`** — OK. ~800 Markdown research SOPs (gap detection, hypothesis generation, adversarial stress-testing). Treat as a prompt/skill library, not as orchestrator architecture.
- **`refs/ljg-skills`** — STRONG. Claude Code skill set including `ljg-paper` (paper digestion for non-specialists), `ljg-paper-river` (citation lineage), `ljg-book` (5-element book breakdown), `ljg-read` (translation / structure / cross-disciplinary). Port the skill schemas as Writer prompts and the book-breakdown structure as a `Book` outline template. **Caveat: no LICENSE detected at clone time (2026-05-27) — study-only, do not copy text verbatim into ENIAK.**

## Dropped from refs/

These were considered and removed on 2026-05-27. See `refs/MANIFEST.json -> dropped` for the pinned reasoning.

- **`autoresearch` (karpathy/autoresearch)** — single-GPU self-modifying training loop; zero overlap with a research + book pipeline. Also confusingly shares a name with an unrelated private project, which would pollute readers' mental model of ENIAK.
- **`agent-framework` (microsoft/agent-framework)** — .NET-primary, Python is afterthought; every orchestration capability is already covered by `langgraph` with better Python ergonomics.
- **`gpt-researcher`** — same shape as `open_deep_research` (plan → parallel search → summarize → report) but with more cruft. `open_deep_research` is retained as the canonical langgraph-native reference.

## Provenance discipline

For an "evidence-native" project to cite its own influences loosely would be ironic. Rules:

1. When a design doc references a pattern from `refs/<repo>`, cite the pinned SHA: `ported from <repo>@<short-sha>`.
2. To bump a reference, update its `commit` in `refs/MANIFEST.json` in the same change that uses the new behavior, and note the diff in the commit message.
3. `refs/MANIFEST.json` is tracked; everything else under `refs/` is ignored.

## Gaps without a strong reference

These are problems ENIAK will have to design itself; no ref above fully solves them:

- **Review/approval state machine** for `EvidenceCard` and `Chapter` — no ref models `draft → in_review → approved → published` with audit trail.
- **HITL UI primitives** for accept/reject/annotate evidence — `langfuse` traces, but doesn't provide a research-reviewer UI.
- **Book-level assembly with cross-references** — `quarto-cli` is the output target, but the *generator* that decides which chapter cites which claim is bespoke.
- **Contradiction detection across sources** — `paper-qa` does single-doc QA; cross-doc contradiction is an open problem.
