from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SHARED_TAXONOMY_PATH = ROOT / "shared" / "taxonomy.json"
TAXONOMY_SPEC_PATH = ROOT / "docs" / "taxonomy-spec.md"


def test_taxonomy_spec_keeps_japanese_and_korean_as_separate_primary_categories():
    taxonomy = json.loads(SHARED_TAXONOMY_PATH.read_text(encoding="utf-8"))
    categories = {item["name"]: item for item in taxonomy["categories"]}
    spec = TAXONOMY_SPEC_PATH.read_text(encoding="utf-8")

    assert "日式料理" in categories
    assert "韓式料理" in categories
    assert "日韓料理" not in categories
    assert "日韓料理" not in spec
    assert "`韓式料理` is already a primary category" in spec


def test_taxonomy_spec_does_not_keep_obsolete_korean_watchlist_language():
    spec = TAXONOMY_SPEC_PATH.read_text(encoding="utf-8")

    assert "韓式主類取消" not in spec
    assert "not enough to restore as main category yet" not in spec
    assert "弘大一號出口 | 火鍋 | 2002 日式燒肉" not in spec
    assert "梨谷韓式鐵板烤肉 忠孝總店 | 日式燒肉 | 2002 日式燒肉" not in spec
    assert "弘大一號出口` / `梨谷韓式鐵板烤肉` -> `2009` + `#韓式`" in spec
