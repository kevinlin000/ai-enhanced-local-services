# ByteBites AI Service

Python FastAPI service for AI features (RAG, agent, evaluation).

## Setup

```bash
uv sync
cp .env.example .env
```

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## Endpoints

- `GET /health`
- `GET /api/ai/ping-java` - verify java backend connectivity
