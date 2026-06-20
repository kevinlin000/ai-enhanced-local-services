# Context Map

This repo is a multi-context project. Read the context file that matches the area being changed.

| Context | File | Scope |
| --- | --- | --- |
| Backend Java | `backend-java/CONTEXT.md` | Spring Boot domain model, auth, booking, payments, cache, concurrency, persistence |
| AI Service | `ai-service-python/CONTEXT.md` | FastAPI, RAG, semantic search, agent behavior, guardrails, LINE integration |
| Web | `web/CONTEXT.md` | Next.js frontend, UI flows, AI concierge, booking and payment screens |
| ETL Pipeline | `etl-pipeline/CONTEXT.md` | Restaurant metadata, taxonomy, Qdrant payload sync, data quality |

System-wide architecture decisions live in `docs/adr/`.
