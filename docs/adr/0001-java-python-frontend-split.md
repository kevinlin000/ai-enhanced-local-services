# ADR 0001: Keep Java, Python AI, ETL, and Web Responsibilities Separate

## Status

Accepted

## Context

This project is a Taiwan-localized review and reservation platform with AI-assisted restaurant discovery. It combines a Java backend, Python AI service, ETL pipeline, and Next.js frontend.

The portfolio value depends on showing both Java backend competence and AI application competence without blurring their responsibilities.

## Decision

Keep responsibilities separated:

- Java backend is the source of truth for business data and transactional workflows.
- Python AI service owns RAG, semantic search, agent behavior, guardrails, and LINE-facing AI responses.
- ETL pipeline owns restaurant metadata quality and Qdrant payload synchronization.
- Next.js frontend owns customer-facing UI and demo flows.

Communication remains HTTP REST unless explicitly revisited.

## Consequences

- Do not move RAG or LLM orchestration into Java.
- Do not make Python the source of truth for booking or payment state.
- Cross-service changes should verify both contract and user-facing behavior.
