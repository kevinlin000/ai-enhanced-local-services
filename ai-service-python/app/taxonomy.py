"""Canonical taxonomy loader. Single source of truth = shared/taxonomy.json.
Both web (Next.js) and ai-service-python MUST read from this file.
Do not hand-copy slug/type_id mappings anywhere else.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TAXONOMY_PATH = _REPO_ROOT / "shared" / "taxonomy.json"


def _load() -> dict[str, Any]:
    with open(_TAXONOMY_PATH, encoding="utf-8") as f:
        return json.load(f)


_data = _load()

CATEGORIES: list[dict] = _data["categories"]
BADGES: list[dict] = _data["badges"]
TAGS: list[dict] = _data["tags"]

CATEGORY_BY_TYPE_ID: dict[int, dict] = {c["type_id"]: c for c in CATEGORIES}
CATEGORY_BY_SLUG: dict[str, dict] = {c["slug"]: c for c in CATEGORIES}
TAG_BY_CODE: dict[str, dict] = {t["code"]: t for t in TAGS}


def get_slug_by_type_id(type_id: int) -> str | None:
    cat = CATEGORY_BY_TYPE_ID.get(type_id)
    return cat["slug"] if cat else None


def get_type_id_by_slug(slug: str) -> int | None:
    cat = CATEGORY_BY_SLUG.get(slug)
    return cat["type_id"] if cat else None
