# ByteBites — AI Dining Operations Platform

[中文 README](README.md)

ByteBites is an AI-assisted dining operations system for Taiwan restaurant scenarios. It extends restaurant discovery into booking, payment state, conversational rescheduling, real-time incident handling, LINE notifications, merchant operations, refund visibility, and verified data quality.

The core boundary:

```text
AI interprets intent and coordinates the workflow.
Java owns booking, payment, incident, and refund state.
```

This repository is not positioned as a chatbot demo. It is a contract-tested full-stack system showing how an AI product can operate around transactional state without letting the model become the source of truth.

## Quick Read

| Area | Evidence |
|---|---|
| Product | AI dining operations platform, not one-shot restaurant recommendation. |
| State ownership | Web, LINE, and AI are entry points; Java owns business state. |
| Data | 600 active Taipei shops, media coverage, review sync, ABSA, taxonomy audit, Qdrant payload sync. |
| Verification | `scripts/verify-portfolio.sh`, Portfolio CI, release readiness, clean MySQL migration smoke. |
| Design | Architecture docs, dbdiagram DBML ER model, query/index evidence, engineering case studies. |

## Review Path

| Time | Start Here |
|---|---|
| 30 seconds | This README: Quick Read and Core Workflow. |
| 3 minutes | [Architecture Overview](docs/architecture-overview.md), [Booking Operations ER Model](docs/er-model-booking-operations.md), [Data Coverage Report](docs/data-coverage-report.md). |
| 10 minutes | [Performance And Query Evidence](docs/performance-query-evidence.md), [Nginx Public Deployment Boundary](docs/deployment-nginx.md), [Engineering Case Studies](docs/case-studies/README.md). |
| Verification | Run `scripts/verify-portfolio.sh` or inspect Portfolio CI. |

## Core Workflow

```text
natural-language dining need
  -> restaurant retrieval and recommendation
  -> structured recommendation cards
  -> booking and demo deposit payment
  -> Web / LINE state sync
  -> conversational reschedule
  -> real-time incident handling and merchant proposal
  -> top-up / refund / operations digest
  -> private dining memory and private offers
```

The strongest example is real-time incident handling:

1. The user tells AI: `我塞車會晚到 20 分鐘`.
2. AI does not guess the booking. It asks Java for the latest valid booking.
3. Java creates `tb_booking_incident` and exposes the state to Web and LINE.
4. The merchant proposes an alternative slot.
5. The customer accepts or declines from Web or LINE.
6. Java validates slot capacity, identity, and deposit policy before applying any booking change.

## Engineering Evidence

### Java-owned transaction state

Spring Boot owns booking, payment, rescheduling, incident, proposal, deposit adjustment, refund reconciliation, and merchant notification state. The AI service does not mutate transactional state directly.

Evidence:

- [Booking Operations ER Model](docs/er-model-booking-operations.md), including dbdiagram DBML source and normalization notes.
- [Web / LINE Booking Sync Case Study](docs/case-studies/07-web-line-booking-sync.md)
- [Portfolio Verification Case Study](docs/case-studies/14-portfolio-verification.md)

### Deterministic AI orchestration

The AI service handles intent, recommendation context, conversation state, and LINE cards. Booking, rescheduling, incident creation, and refund workflows are routed through backend contracts.

Evidence:

- [AI Dialogue State Case Study](docs/case-studies/10-ai-dialogue-state.md)
- [AI Concierge Quality Hardening Case Study](docs/case-studies/13-ai-concierge-quality-hardening.md)
- `ai-service-python/evals/`

### Data quality before prompt quality

Recommendation quality is backed by data coverage and repeatable checks, not just prompt tuning.

| Metric | Status |
|---|---|
| Active Taipei shops | 600 |
| Cover image / media manifest | 100% |
| AI summary coverage | 100% |
| ABSA / Mongo review coverage | 99%+ |
| Price signal coverage | 85%+ |

Full report: [Data Coverage Report](docs/data-coverage-report.md)

## Architecture

```text
Browser / LINE
  |
  v
Next.js Web
  |-- discovery, AI chat, bookings, merchant console
  |
  +--> Spring Boot Java
  |      |-- auth / shop / booking / payment / incident / refund / parking
  |      |-- MySQL / Flyway / Redis / RabbitMQ
  |      |-- LINE identity and notification contracts
  |
  +--> FastAPI AI service
         |-- Gemini agent and dialogue policy
         |-- Qdrant semantic search
         |-- LINE Messaging webhook and Flex cards

ETL / data quality
  |-- Google Places / Maps crawler
  |-- Mongo review sync
  |-- ABSA pipeline
  |-- taxonomy audit and Qdrant payload sync
```

Full details: [Architecture Overview](docs/architecture-overview.md)

## Stack

| Area | Stack |
|---|---|
| Frontend | Next.js |
| Backend | Spring Boot 3.2 / Java 17 / MySQL / Redis / RabbitMQ / Flyway |
| AI service | FastAPI, Gemini agent, semantic search, LINE cards |
| Vector DB | Qdrant |
| Data | Python ETL, Google Places / Maps crawler, Mongo-backed reviews, ABSA metadata |
| Deployment | Nginx reverse-proxy blueprint, Docker Compose public-proxy overlay, local ngrok demo |
| Verification | Java, Python, ETL, data-quality, Web, release readiness, clean migration smoke |

## Verification

```bash
scripts/verify-portfolio.sh
```

The portfolio gate covers Java contract tests, AI service tests, ETL tests, data-quality checks, Nginx route contracts, clean migration contracts, release-boundary checks, query evidence checks, Web tests, and a production build.

Release rehearsal:

```bash
scripts/release-readiness.sh --offline
scripts/smoke-clean-mysql-migrations.sh --timeout 180
```

## Selected Case Studies

- [Real Streaming for an AI Agent](docs/case-studies/01-sse-streaming-debug.md)
- [ABSA Review Intelligence Pipeline](docs/case-studies/02-absa-pipeline.md)
- [Data Crawling and Coverage](docs/case-studies/06-data-crawler-coverage.md)
- [Web / LINE Booking Sync](docs/case-studies/07-web-line-booking-sync.md)
- [AI Dialogue State](docs/case-studies/10-ai-dialogue-state.md)
- [Public Deployment Rehearsal](docs/case-studies/11-demo-deployment.md)

Full list: [Engineering Case Studies](docs/case-studies/README.md)

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

This project is portfolio-ready and contract-tested. It is not claimed as a production SaaS rollout. Production rollout would require managed secrets, cloud data stores, backup and restore policy, observability dashboards, real PSP refund provider integration, merchant notification preferences, and operations playbooks.
