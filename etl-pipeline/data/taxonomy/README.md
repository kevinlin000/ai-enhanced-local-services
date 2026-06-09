# Taxonomy Manual Overrides

`manual_overrides.json` stores human-reviewed restaurant classification decisions.
Keep reviewer decisions here instead of hard-coding them in `app/taxonomy.py` or
running one-off SQL updates.

## Fields

- `primary_type_overrides`: name-match rules that force the canonical category
  `type_id`. These run before legacy name rules and keyword correction.
- `suppress_tags`: name-match rules that remove misleading secondary tags. Today
  this is used to remove bad `韓式` tags caused by menu side dishes such as kimchi.

## After Editing

Run:

```bash
uv run pytest -q tests/test_taxonomy.py tests/test_normalizer.py
uv run python scripts/verify_taxonomy_sync.py
```

From the repository root, also run:

```bash
python3 etl-pipeline/scripts/generate_taxonomy_audit.py
```
