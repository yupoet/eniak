# ENIAK Brainstorm

## Working Name

ENIAK: Evidence-Native Intelligent Academic Kernel.

The name should be used for the technical kernel and repository. A Chinese presentation name can remain separate, such as "Yanshu" or "Research Hub", but the codebase should stay English-first.

## Product Intent

ENIAK is not a general-purpose agent framework. It is a research operating layer for long-running academic and industry research programs that must produce traceable written output.

The system should optimize for:

- Evidence traceability over fluent prose.
- Durable research state over one-shot chat answers.
- Human review gates over unchecked autonomous publishing.
- Modular providers over single-vendor lock-in.
- Book-quality organization over isolated reports.

## Five-Layer Model

### 1. Research Radar

The radar layer watches sources and turns external changes into candidate evidence.

Candidate providers:

- arXiv
- Semantic Scholar
- OpenAlex
- PubMed
- Crossref
- Web search providers
- Company white paper feeds
- Regulatory websites

Initial output:

- source candidate
- source metadata
- topic match score
- deduplication key
- retrieval timestamp

### 2. Evidence Layer

The evidence layer is the source-of-truth for claims, sources, files, citations, and retrieval history.

Core objects:

- Source
- Document
- EvidenceCard
- Citation
- Claim
- Contradiction
- RetrievalRun

Important design rule: generated claims must point back to evidence cards, and evidence cards must point back to source metadata.

### 3. Research Orchestration

The orchestration layer coordinates planner and actor loops.

Borrowed ideas from Aime:

- Dynamic Planner: update the research plan as new evidence arrives.
- Actor Factory: instantiate task-specific actors from templates.
- Dynamic Actor: run bounded ReAct-style tool loops.
- Progress Management: persist task trees and state transitions.

The first implementation should be a small explicit graph, not a sprawling multi-agent system.

### 4. Writing Layer

The writing layer turns evidence into durable book artifacts.

Core objects:

- Book
- Part
- Chapter
- Section
- Draft
- FigureSpec
- Bibliography

Writing should happen in Markdown first, with later export to Feishu Docs, PDF, or DOCX.

### 5. Feishu Publishing

The publishing layer synchronizes reviewed drafts to Lark/Feishu.

Required behavior:

- Dry-run mode by default.
- Versioned publish records.
- Idempotent updates.
- Clear mapping from local chapter IDs to Feishu document or wiki IDs.
- No clinical or regulatory claims published without explicit review state.

## Reference Stack Hypothesis

Use LangGraph as the core durable orchestration primitive.

Use PaperQA2-style ideas for scientific document RAG and citation grounding.

Use DeerFlow, STORM, GPT Researcher, Research Claw, and DARE as references, not as hard dependencies in the initial kernel.

## Non-Goals

- Do not build a GPU training system.
- Do not clone Aime from scratch.
- Do not put dynamic agents into regulated medical-device runtime paths.
- Do not auto-publish unreviewed conclusions.
- Do not make Feishu the only storage of truth.

