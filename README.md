# ENIAK

Evidence-Native Intelligent Academic Kernel.

ENIAK is a monorepo for an automated research and book-building system. It is designed around five layers:

1. Research radar: continuously monitor papers, industry reports, white papers, and regulatory documents.
2. Evidence layer: download, parse, index, and cite PDFs, web pages, reports, DOI records, arXiv entries, retrieval dates, and page references.
3. Research orchestration: decompose a research goal into questions, hypotheses, evidence collection, counter-evidence, synthesis, and chapters.
4. Writing layer: produce book outlines, chapter drafts, figures, evidence cards, and references.
5. Feishu publishing: sync to Lark/Feishu Docs or Wiki with version records.

## Repository Layout

```text
apps/
  api/                 # Backend service
  web/                 # Frontend workspace
packages/
  shared/              # Shared schemas and generated types
eniak/
  radar/               # Research radar layer
  evidence/            # Evidence layer
  orchestrator/        # Research orchestration layer
  writer/              # Writing layer
  publisher/           # Feishu publishing layer
infra/
  docker/              # Docker and deployment assets
  migrations/          # Database migrations
docs/
  brainstorm.md        # Architecture brainstorm
  plan.md              # Build plan
  references.md        # Reference project index
refs/                  # Local reference repos, ignored by git
```

## Status

Project bootstrap is in progress. The first milestone is a dry-run research loop:

```text
research topic -> radar scan -> evidence record -> chapter draft -> Feishu publish dry-run
```

