from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.taxonomy import classify_shop


RAW_DIR = ROOT / "data" / "raw"

APPROVED_PRIMARY_TYPE_IDS = {
    10099: 2004, 10100: 2004, 10101: 2008, 10102: 2001, 10103: 2011, 10104: 2011,
    10105: 2003, 10106: 2011, 10107: 2002, 10108: 2012, 10109: 2008, 10110: 2007,
    10111: 2008, 10112: 2010, 10113: 2008, 10114: 2008, 10115: 2001, 10116: 2008,
    10117: 2008, 10118: 2008, 10119: 2008, 10120: 2008, 10121: 2008, 10122: 2010,
    10123: 2008, 10124: 2005, 10125: 2007, 10126: 2008, 10127: 2001, 10128: 2001,
    10129: 2008, 10130: 2008, 10131: 2001, 10132: 2008, 10133: 2012, 10134: 2008,
    10135: 2008, 10136: 2010, 10137: 2001, 10138: 2007, 10139: 2005, 10140: 2010,
    10141: 2008, 10142: 2010, 10143: 2008, 10144: 2001, 10145: 2008, 10146: 2008,
    10147: 2008, 10148: 2008, 10149: 2007, 10150: 2012, 10151: 2012, 10152: 2001,
    10153: 2008, 10154: 2008, 10155: 2008, 10156: 2001, 10157: 2008, 10158: 2010,
    10159: 2007, 10160: 2008, 10161: 2008, 10162: 2001, 10163: 2011, 10164: 2008,
    10165: 2002, 10166: 2001, 10167: 2008, 10168: 2001, 10169: 2005, 10170: 2005,
    10171: 2002, 10172: 2001, 10173: 2002, 10174: 2012, 10175: 2002, 10176: 2011,
    10177: 2001, 10178: 2008, 10179: 2001, 10180: 2010, 10181: 2010, 10182: 2001,
    10183: 2007, 10184: 2008, 10185: 2001, 10186: 2001, 10187: 2012, 10188: 2001,
    10189: 2008, 10190: 2002, 10191: 2008, 10192: 2003, 10193: 2007, 10194: 2012,
    10195: 2010, 10196: 2007, 10197: 2001, 10198: 2008, 10199: 2003, 10200: 2004,
    10201: 2010,
}


def load_shops() -> dict[int, dict]:
    shops: dict[int, dict] = {}
    for path in sorted(RAW_DIR.glob("places_extracted_*.json")):
        payload = json.loads(path.read_text())
        for shop in payload.get("shops", []):
            shop_id = shop.get("shop_id")
            if shop_id:
                shops[shop_id] = shop
    return shops


def test_classifier_matches_approved_primary_type_ids():
    shops = load_shops()
    mismatches = []

    for shop_id, expected_type_id in sorted(APPROVED_PRIMARY_TYPE_IDS.items()):
        actual_type_id = classify_shop(shops[shop_id])["primary_type_id"]
        if actual_type_id != expected_type_id:
            mismatches.append(
                f"{shop_id} {shops[shop_id]['display_name']}: expected {expected_type_id}, got {actual_type_id}"
            )

    assert not mismatches, "classifier diff vs approved remap:\n" + "\n".join(mismatches)


def test_classifier_fixture_10171_yakiniku():
    shop = load_shops()[10171]
    result = classify_shop(shop)
    assert result["primary_type_id"] == 2002
    assert result["badges"] == []
    assert result["tags"] == []


def test_classifier_fixture_10181_american_bbq():
    shop = load_shops()[10181]
    result = classify_shop(shop)
    assert result["primary_type_id"] == 2010
    assert result["badges"] == []


def test_classifier_fixture_10183_bistro():
    shop = load_shops()[10183]
    result = classify_shop(shop)
    assert result["primary_type_id"] == 2007
    assert "餐酒館" in result["tags"]


def test_classifier_fixture_10190_korean_yakiniku():
    shop = load_shops()[10190]
    result = classify_shop(shop)
    assert result["primary_type_id"] == 2002
    assert "韓式" in result["tags"]


def test_classifier_fixture_10104_buffet_premium():
    shop = load_shops()[10104]
    result = classify_shop(shop)
    assert result["primary_type_id"] == 2011
    assert result["badges"] == ["高級"]
    assert "景觀" in result["tags"]
