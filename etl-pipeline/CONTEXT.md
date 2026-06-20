# ETL Pipeline Context

## Scope

`etl-pipeline` owns restaurant metadata preparation, taxonomy quality, Qdrant payload synchronization, and audit artifacts used by the AI service.

## Technology

- Python
- uv
- MySQL
- Qdrant
- Metadata/audit scripts

## Domain Terms

- `Taxonomy`: controlled restaurant category and tag vocabulary
- `Payload sync`: update of Qdrant payload fields from source metadata
- `Metadata audit`: report that identifies taxonomy drift or low-quality restaurant metadata
- `Category slug`: normalized category identifier used across search and UI

## Boundaries

- ETL can transform and sync metadata for search.
- ETL should not directly implement user-facing booking behavior.
- When taxonomy changes, verify downstream AI search and UI assumptions.
