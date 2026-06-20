# ByteBites — AI Dining Operations Platform

ByteBites is an AI-assisted dining operations platform for Taiwan restaurant scenarios. It goes beyond restaurant discovery into booking, payment state, conversational rescheduling, real-time incident handling, LINE coordination, merchant operations, refund visibility, and verified data quality.

Core architecture principle:

```text
AI orchestrates the workflow.
Java owns booking, payment, incident, and refund state.
```

## Review Entry Points

- [Project Journey](docs/project-journey.md)
- [Architecture Overview](docs/architecture-overview.md)
- [Booking Operations ER Model](docs/er-model-booking-operations.md)
- [Performance And Query Evidence](docs/performance-query-evidence.md)
- [Data Coverage Report](docs/data-coverage-report.md)
- [Nginx Public Deployment Boundary](docs/deployment-nginx.md)
- [Engineering Case Studies](docs/case-studies/README.md)

## What It Does

- AI dining concierge with clarification, recommendation context, and booking follow-ups.
- Structured recommendation cards backed by shared `recommended_shop_ids`.
- Java-owned booking, payment, rescheduling, incident, proposal, deposit adjustment, and refund state.
- LINE Login plus Messaging API integration for cross-channel booking and incident actions.
- Merchant console for slot inventory, incident proposals, refund SLA visibility, and operations digest.
- Private dining memory and private AI-matched offers.
- Data pipeline for Google Places / Maps crawling, review sync, media coverage, ABSA, taxonomy audit, and Qdrant payloads.

## System Snapshot

| Area | Stack |
|---|---|
| Frontend | Next.js |
| Backend | Spring Boot 3.2 / Java 17 / MySQL / Redis / RabbitMQ / Flyway |
| AI service | FastAPI, Gemini agent, semantic search, LINE cards |
| Vector DB | Qdrant |
| Data | 600 active Taipei shops, media coverage, Mongo-backed reviews, ABSA metadata |
| Deployment | Local ngrok demo, Nginx reverse-proxy blueprint, Docker Compose public-proxy overlay |
| Verification | Java, Python, ETL, data-quality, Web, release readiness, clean migration smoke |

## Verification

```bash
scripts/verify-portfolio.sh
```

The portfolio gate covers Java contract tests, AI service tests, ETL tests, data-quality checks, Nginx route contracts, clean migration contracts, release-boundary checks, query evidence checks, Web tests, and a production build.

For release rehearsal:

```bash
scripts/release-readiness.sh --offline
scripts/smoke-clean-mysql-migrations.sh --timeout 180
```

## Local Development

```bash
docker compose up -d

cd backend-java
set -a; source .env; set +a
mvn spring-boot:run

cd ../ai-service-python
set -a; source .env; set +a
uv run uvicorn app.main:app --reload --port 8000

cd ../web
npm run dev
```

## Production Boundary

This is portfolio-ready and contract-tested. It is not claimed as a production SaaS rollout. Production work would require managed secrets, cloud data stores, backup and restore policy, observability dashboards, real PSP refund provider integration, merchant notification preferences, and operations playbooks.
