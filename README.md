# ByteBites — AI-Powered Restaurant Recommendation Platform

> Full-stack AI recommendation system for local restaurants.
> Spring Boot + FastAPI + Next.js, with Gemini Agent, ABSA review analysis, Qdrant semantic search, and structured recommendation cards.

## What It Does

ByteBites is an AI restaurant recommendation platform benchmarked against inline.app. Users ask natural-language questions like **「推薦信義區的火鍋」**, and the system searches real shop data, routes through an AI Agent, analyzes reviews with ABSA (Aspect-Based Sentiment Analysis), and returns recommendation cards with photos, review carousel, Google Maps, positive highlights, and booking CTA.

The project focuses on production-style engineering decisions, not a demo-only chatbot: real streaming, model ablation, taxonomy migrations, review verification, and UX consistency between agent narrative and rendered cards.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Spring Boot 3.2 / Java 17 / JPA / MySQL 8.4 / Redis / RabbitMQ / Flyway |
| AI Service | FastAPI / Gemini Agent / Gemini ABSA / Gemini Embedding / SSE |
| Vector DB | Qdrant semantic search |
| Frontend | Next.js / React / TypeScript / Tailwind / shadcn |
| Data | Google Places API / review scraper / taxonomy backfill |
| Infra | Docker Compose / Prometheus metrics |

## Architecture

```text
Browser
  |
  v
Next.js web
  |-- AI Chat UI + SSE stream
  |-- recommendation cards
  |
  +--> Spring Boot backend
  |      |-- shop API
  |      |-- booking / voucher APIs
  |      |-- MySQL taxonomy + ABSA JSON
  |      |-- Redis / RabbitMQ
  |
  +--> FastAPI AI service
         |-- Gemini function-calling agent
         |-- Qdrant semantic search
         |-- structured recommendation decision
         |-- SSE done payload
```

## Highlights

- **Structured AI Agent decisions**: agent emits `recommended_shop_ids`, `rejected_shop_ids`, `rejection_summary`, and `narrative`; frontend renders cards from the same IDs.
- **True SSE streaming**: debugged fake streaming, tool-call history contamination, and model latency floor; TTFT improved from effectively infinite to 908ms.
- **ABSA review analysis**: LLM-based aspect extraction with two-layer faithfulness verification; measured F1 0.955 on a hand-labeled gold set.
- **Model ablation**: benchmarked model latency, quality, tool routing, and cost; selected Gemini Flash Lite for agent work instead of blindly choosing the fastest model.
- **Production taxonomy**: migrated from string tags to a 3-axis taxonomy with Flyway migrations and third-party validation anchors.
- **Recommendation UX**: removed raw mixed-sentiment bars from recommendation cards and replaced them with positive-only highlights while preserving full ABSA on detail pages.

## Case Studies

1. [AI Agent 真實串流 — 三層 debug 走完](docs/case-studies/01-sse-streaming-debug.md)
   Fake streaming, synchronous SDK calls, tool-call history pollution, context compression, and model swap.

2. [ABSA Pipeline — 從模板到 LLM, F1 0.955](docs/case-studies/02-absa-pipeline.md)
   Aspect-level sentiment extraction, character verifier, semantic fallback, gold set, batch issues.

3. [Model 選擇不是「越貴越好」](docs/case-studies/03-model-ablation.md)
   Task-specific model ablation across latency, tool routing, quality, and cost.

4. [Taxonomy 從 0 到 production](docs/case-studies/04-taxonomy-migration.md)
   V15-V19 Flyway migrations, taxonomy design, and third-party validation anchors.

5. [推薦卡 UX — 從暴露 ABSA 到正面 framing](docs/case-studies/05-recommendation-ux.md)
   Product judgment around what belongs on recommendation cards vs detail pages.

## Project Structure

```text
ai-enhanced-local-services/
├── backend-java/          # Spring Boot, JPA, Flyway, shop/booking APIs
├── ai-service-python/     # FastAPI, Gemini Agent, ABSA, semantic search
├── web/                   # Next.js AI UI and recommendation cards
├── etl-pipeline/          # scraper, Qdrant loader, taxonomy verification
├── tools/                 # scraper utilities
└── docs/
    ├── case-studies/      # engineering case studies
    └── taxonomy-spec.md
```

## Local Development

```bash
# 1. Start infra
docker compose up -d

# 2. Backend
cd backend-java
set -a; source .env; set +a
mvn spring-boot:run

# 3. AI service
cd ai-service-python
uv sync
uv run uvicorn app.main:app --reload --port 8000

# 4. Frontend
cd web
npm run dev
```

Required environment variables include Gemini API keys, Java backend URL, and local service URLs. Secrets are intentionally ignored by git.

## Built With AI as a Force Multiplier

Claude and Codex were used throughout the project for hypothesis generation, code audit, boilerplate, and debugging support. The case studies explicitly separate what AI suggested from what I verified, challenged, measured, and shipped.

The core thesis: AI tools accelerate engineering work, but the engineer still owns judgment, validation, trade-offs, and product responsibility.

## Contact

- GitHub: [@kevinlin000](https://github.com/kevinlin000)
