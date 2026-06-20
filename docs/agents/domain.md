# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root — points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — system-wide architectural decisions (e.g. Java/Python split, HTTP-only communication, tech stack choices).
- Per-context ADRs: `<context>/docs/adr/` for decisions scoped to that sub-system.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions actually get resolved.

## File structure (multi-context)

This is a monorepo with four independent contexts:

```
/
├── CONTEXT-MAP.md                      ← root index; points at each context below
├── docs/adr/                           ← system-wide decisions
│   └── 0001-java-python-split.md
├── backend-java/
│   ├── CONTEXT.md                      ← Java/Spring Boot domain language
│   └── docs/adr/                       ← backend-specific decisions
├── ai-service-python/
│   ├── CONTEXT.md                      ← RAG/AI service domain language
│   └── docs/adr/                       ← AI service-specific decisions
├── web/
│   ├── CONTEXT.md                      ← Next.js frontend domain language
│   └── docs/adr/                       ← frontend-specific decisions
└── etl-pipeline/
    ├── CONTEXT.md                      ← ETL pipeline domain language
    └── docs/adr/                       ← pipeline-specific decisions
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in the relevant `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
