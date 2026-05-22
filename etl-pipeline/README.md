# ByteBites ETL Pipeline

Google Places ETL pipeline for first-stage district search around Taipei commercial areas.

## Setup

```bash
uv sync
cp .env.example .env
```

## Run

```bash
uv run python -m app.crawler
```

Raw API search output is written to `data/raw/`.
