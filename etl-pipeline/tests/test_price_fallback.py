from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.price import resolved_avg_price, resolved_price_label


PRICE_LEVEL_TO_AVG = {"PRICE_LEVEL_MODERATE": 600}
PRICE_LEVEL_TO_LABEL = {"PRICE_LEVEL_MODERATE": "$400-800"}


def test_rebuild_prefers_manifest_price_over_coarse_price_level():
    shop = {"price_level": "PRICE_LEVEL_MODERATE", "ai_extracted": {"price_per_person": "未提及"}}
    media = {"overview": {"price_overview": "$200-400"}}

    assert resolved_avg_price(shop, media, PRICE_LEVEL_TO_AVG) == 300


def test_restore_writes_manifest_price_label_when_ai_price_is_missing():
    shop = {"price_level": "PRICE_LEVEL_MODERATE", "ai_extracted": {"price_per_person": "未提及"}}
    media = {"overview": {"price_overview": "$200-400"}}

    assert resolved_avg_price(shop, media, PRICE_LEVEL_TO_AVG) == 300
    assert resolved_price_label(shop, media, PRICE_LEVEL_TO_LABEL) == "$200-400"


def test_ai_extracted_price_still_takes_precedence():
    shop = {"price_level": "PRICE_LEVEL_MODERATE", "ai_extracted": {"price_per_person": "$350-450"}}
    media = {"overview": {"price_overview": "$200-400"}}

    assert resolved_avg_price(shop, media, PRICE_LEVEL_TO_AVG) == 400
    assert resolved_price_label(shop, media, PRICE_LEVEL_TO_LABEL) == "$350-450"
