from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.taxonomy import classify_shop
from scripts.generate_taxonomy_audit import build_audit_rows


RAW_DIR = ROOT / "data" / "raw"
FIXTURE_SHOPS_PATH = ROOT / "tests" / "fixtures" / "taxonomy_shops.json"
MANUAL_OVERRIDES_PATH = ROOT / "data" / "taxonomy" / "manual_overrides.json"
SHARED_TAXONOMY_PATH = ROOT.parent / "shared" / "taxonomy.json"

APPROVED_PRIMARY_TYPE_IDS = {
    10099: 2004, 10100: 2004, 10101: 2008, 10102: 2001, 10103: 2011, 10104: 2011,
    10105: 2003, 10106: 2011, 10107: 2002, 10108: 2012, 10109: 2008, 10110: 2007,
    10111: 2008, 10112: 2010, 10113: 2008, 10114: 2008, 10115: 2001, 10116: 2008,
    10117: 2008, 10118: 2008, 10119: 2008, 10120: 2008, 10121: 2008, 10122: 2010,
    10123: 2008, 10124: 2008, 10125: 2007, 10126: 2008, 10127: 2001, 10128: 2001,
    10129: 2008, 10130: 2013, 10131: 2001, 10132: 2008, 10133: 2012, 10134: 2008,
    10135: 2008, 10136: 2010, 10137: 2001, 10138: 2007, 10139: 2005, 10140: 2010,
    10141: 2008, 10142: 2010, 10143: 2008, 10144: 2001, 10145: 2008, 10146: 2008,
    10147: 2008, 10148: 2008, 10149: 2007, 10150: 2012, 10151: 2012, 10152: 2001,
    10153: 2008, 10154: 2008, 10155: 2008, 10156: 2001, 10157: 2008, 10158: 2007,
    10159: 2007, 10160: 2008, 10161: 2008, 10162: 2001, 10163: 2011, 10164: 2008,
    10165: 2009, 10166: 2001, 10167: 2008, 10168: 2001, 10169: 2005, 10170: 2005,
    10171: 2002, 10172: 2001, 10173: 2002, 10174: 2012, 10175: 2002, 10176: 2011,
    10177: 2001, 10178: 2008, 10179: 2001, 10180: 2010, 10181: 2010, 10182: 2001,
    10183: 2007, 10184: 2008, 10185: 2001, 10186: 2001, 10187: 2012, 10188: 2001,
    10189: 2008, 10190: 2009, 10191: 2008, 10192: 2003, 10193: 2007, 10194: 2012,
    10195: 2010, 10196: 2007, 10197: 2001, 10198: 2008, 10199: 2003, 10200: 2004,
    10201: 2010,
}


def load_shops() -> dict[int, dict]:
    shops: dict[int, dict] = {}
    if FIXTURE_SHOPS_PATH.exists():
        payload = json.loads(FIXTURE_SHOPS_PATH.read_text(encoding="utf-8"))
        for shop in payload.get("shops", []):
            shop_id = shop.get("shop_id")
            if shop_id:
                shops[shop_id] = shop

    for path in sorted(RAW_DIR.glob("places_extracted_*.json")):
        payload = json.loads(path.read_text())
        for shop in payload.get("shops", []):
            shop_id = shop.get("shop_id")
            if shop_id:
                shops[shop_id] = shop
    return shops


def load_manual_overrides() -> dict:
    return json.loads(MANUAL_OVERRIDES_PATH.read_text(encoding="utf-8"))


def canonical_type_ids() -> set[int]:
    payload = json.loads(SHARED_TAXONOMY_PATH.read_text(encoding="utf-8"))
    return {int(item["type_id"]) for item in payload["categories"]}


def test_primary_type_map_has_no_duplicate_keys():
    source = (ROOT / "app" / "taxonomy.py").read_text(encoding="utf-8")
    start = source.index("PRIMARY_TYPE_MAP = {")
    end = source.index("\n}\n", start)
    keys = []
    for line in source[start:end].splitlines():
        stripped = line.strip()
        if stripped.startswith('"'):
            keys.append(stripped.split('"', 2)[1])

    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    assert duplicates == []


def test_manual_override_fixture_schema_and_type_ids():
    payload = load_manual_overrides()
    assert payload["meta"]["version"] == 1

    valid_type_ids = canonical_type_ids()
    primary_rows = payload["primary_type_overrides"]
    suppress_rows = payload["suppress_tags"]

    assert primary_rows
    assert suppress_rows
    assert len({row["match"] for row in primary_rows}) == len(primary_rows)
    assert len({row["match"] for row in suppress_rows}) == len(suppress_rows)

    for row in primary_rows:
        assert row["source"] == "manual_audit"
        assert row["match"].strip()
        assert row["type_id"] in valid_type_ids

    for row in suppress_rows:
        assert row["source"] == "manual_audit"
        assert row["match"].strip()
        assert row["tags"] == ["韓式"]


def test_manual_audit_overrides_are_loaded_before_legacy_name_rules():
    result = classify_shop({
        "display_name": "品田牧場 台北松山車站店",
        "primary_type": "restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "日式豬排、套餐與定食。"},
    })
    assert result["primary_type_id"] == 2004


def test_classifier_matches_approved_primary_type_ids():
    shops = load_shops()
    missing_ids = sorted(set(APPROVED_PRIMARY_TYPE_IDS) - set(shops))
    if missing_ids:
        pytest.skip(
            "full raw taxonomy corpus is unavailable; "
            f"missing approved shop ids: {missing_ids[:8]}"
        )

    mismatches = []

    for shop_id, expected_type_id in sorted(APPROVED_PRIMARY_TYPE_IDS.items()):
        actual_type_id = classify_shop(shops[shop_id])["primary_type_id"]
        if actual_type_id != expected_type_id:
            mismatches.append(
                f"{shop_id} {shops[shop_id]['display_name']}: expected {expected_type_id}, got {actual_type_id}"
            )

    assert not mismatches, "classifier diff vs approved remap:\n" + "\n".join(mismatches)


def test_committed_taxonomy_fixture_matches_approved_primary_type_ids():
    shops = load_shops()
    fixture_payload = json.loads(FIXTURE_SHOPS_PATH.read_text(encoding="utf-8"))
    fixture_ids = sorted(shop["shop_id"] for shop in fixture_payload["shops"])
    assert fixture_ids == [10099, 10104, 10171, 10181, 10183, 10190]

    mismatches = []
    for shop_id in fixture_ids:
        expected_type_id = APPROVED_PRIMARY_TYPE_IDS[shop_id]
        actual_type_id = classify_shop(shops[shop_id])["primary_type_id"]
        if actual_type_id != expected_type_id:
            mismatches.append(
                f"{shop_id} {shops[shop_id]['display_name']}: expected {expected_type_id}, got {actual_type_id}"
            )

    assert not mismatches, "classifier diff vs committed fixtures:\n" + "\n".join(mismatches)


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
    assert result["primary_type_id"] == 2009
    assert "韓式" in result["tags"]


def test_classifier_korean_restaurant_maps_to_korean_primary_category():
    result = classify_shop({
        "display_name": "新村站著吃烤肉",
        "primary_type": "korean_barbecue_restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "韓式烤肉、泡菜鍋與石鍋拌飯。"},
    })
    assert result["primary_type_id"] == 2009
    assert "韓式" in result["tags"]


def test_classifier_indian_restaurant_maps_to_international_category():
    result = classify_shop({
        "display_name": "亞瑟蘭印度餐廳",
        "primary_type": "indian_restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "印度料理、烤餅、瑪莎拉與清真餐點。"},
    })
    assert result["primary_type_id"] == 2013
    assert "印度" in result["tags"]


def test_mexican_restaurant_maps_to_international_category():
    result = classify_shop({
        "display_name": "墨西哥塔可餐廳",
        "primary_type": "mexican_restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "墨西哥料理、taco、辣醬與玉米餅。"},
    })
    assert result["primary_type_id"] == 2013


def test_kimchi_side_dish_does_not_create_korean_tag():
    result = classify_shop({
        "display_name": "日式燒肉測試店",
        "primary_type": "yakiniku_restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "日式燒肉、牛舌、味噌湯與泡菜小菜。"},
    })
    assert result["primary_type_id"] == 2002
    assert "韓式" not in result["tags"]


def test_manual_audit_override_beats_conflicting_keywords():
    result = classify_shop({
        "display_name": "溫咖哩 Wen Curry",
        "primary_type": "restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "日式咖哩與牛排套餐。"},
    })
    assert result["primary_type_id"] == 2004


def test_manual_no_korean_tag_override_suppresses_keyword_tag():
    result = classify_shop({
        "display_name": "TankQ cafe&Bar忠孝敦化店",
        "primary_type": "restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "美式餐點、義大利麵與韓式炸雞風味小點。"},
    })
    assert result["primary_type_id"] == 2010
    assert "韓式" not in result["tags"]


def test_second_manual_audit_overrides_edge_cases():
    cases = [
        ("品田牧場 台北松山車站店", "豬排、套餐與日式定食，甜點為附餐。", 2004),
        ("小紐約披薩 中山店", "美式披薩、酒吧與聚餐餐點。", 2010),
        ("神燈搓一下", "印度、中東與墨西哥風味的異國料理。", 2013),
        ("胖肚肚燒肉 大安店", "炭火燒肉吃到飽與牛舌。", 2002),
    ]
    for name, summary, expected_type_id in cases:
        result = classify_shop({
            "display_name": name,
            "primary_type": "restaurant",
            "types": ["restaurant", "food"],
            "ai_extracted": {"ai_summary": summary},
        })
        assert result["primary_type_id"] == expected_type_id


def test_manual_buffet_tag_can_stay_secondary_to_vegetarian():
    result = classify_shop({
        "display_name": "果然匯 台北天母店",
        "primary_type": "vegetarian_restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "蔬食自助餐與吃到飽餐檯。"},
    })
    assert result["primary_type_id"] == 2005
    assert "吃到飽" in result["tags"]


def test_third_manual_audit_overrides_special_cases():
    cases = [
        ("麥味登 文山饗食大亨店", "台式連鎖早餐、漢堡、蛋餅與咖啡。", 2008),
        ("大河牧場 漢堡排洋食館-內湖大全聯店", "日式洋食漢堡排與壽喜燒風味套餐。", 2004),
        ("東京家庭義大利麵 堺人餐飲 天母", "日式義大利麵、明太子麵與和風洋食。", 2004),
        ("試試工作室", "義式料理、私廚手作料理與甜點。", 2007),
    ]
    for name, summary, expected_type_id in cases:
        result = classify_shop({
            "display_name": name,
            "primary_type": "restaurant",
            "types": ["restaurant", "food"],
            "ai_extracted": {"ai_summary": summary},
        })
        assert result["primary_type_id"] == expected_type_id


def test_fourth_manual_audit_overrides_defaulted_chinese_cases():
    cases = [
        ("吉豚屋 石牌店", "日式豬排、味噌湯與高麗菜絲。", 2004),
        ("勝魂丼飯專門店（丼飯.咖哩）", "日式丼飯、咖哩、味噌湯與炸物。", 2004),
        ("Mr. 雪腐 公館店", "雪花冰、豆花、甜湯與手作甜點。", 2012),
        ("mama says yes 大馬人 | 內湖本店", "馬來西亞料理、炒粿條、海南雞飯與椰漿飯。", 2013),
        ("Haooyun Station 好運站", "美式早午餐、酸種麵包餐盤與咖啡。", 2010),
    ]
    for name, summary, expected_type_id in cases:
        result = classify_shop({
            "display_name": name,
            "primary_type": "restaurant",
            "types": ["restaurant", "food"],
            "ai_extracted": {"ai_summary": summary},
        })
        assert result["primary_type_id"] == expected_type_id


def test_final_manual_audit_overrides_and_removes_bad_korean_tags():
    cases = [
        ("花嶼輕食館Flower Island Brunch", "下午茶、咖啡、巴斯克蛋糕與甜點。", 2012, []),
        ("知初植物系永續廚房（Last order time is 14:15 / 20:00）", "植物基蔬食、永續飲食與披薩。", 2005, []),
        ("KiKi餐廳（ATT 4 FUN信義店）", "蒼蠅頭、老皮嫩肉與川味台式熱炒。", 2008, []),
        ("燒肉眾精緻炭火燒肉 台北西門店", "日式燒肉、牛舌、泡菜小菜。", 2002, []),
        ("大樹先生的家", "親子餐廳、義大利麵、燉飯與兒童烏龍麵。", 2007, ["義式"]),
        ("神來一爐燒肉民生店", "日式炭火燒肉、牛舌、泡菜小菜。", 2002, []),
        ("IKIGAI燒肉專門店-微風百貨店", "日式個人燒肉、味噌湯、泡菜湯品。", 2002, []),
        ("蘋果肉桂 Café & Bistro", "咖啡、甜點、蘋果肉桂、義大利麵與韓式泡菜小菜。", 2012, ["義式"]),
    ]
    for name, summary, expected_type_id, expected_tags in cases:
        result = classify_shop({
            "display_name": name,
            "primary_type": "restaurant",
            "types": ["restaurant", "food"],
            "ai_extracted": {"ai_summary": summary},
        })
        assert result["primary_type_id"] == expected_type_id
        assert "韓式" not in result["tags"]
        for tag in expected_tags:
            assert tag in result["tags"]


def test_classifier_fixture_10104_buffet_premium():
    shop = load_shops()[10104]
    result = classify_shop(shop)
    assert result["primary_type_id"] == 2011
    assert result["badges"] == ["高級"]
    assert "景觀" in result["tags"]


def test_v20_burger_restaurant_maps_to_american():
    result = classify_shop({
        "display_name": "Fa Burger",
        "primary_type": "restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "美式漢堡、薯條與早午餐。"},
    })
    assert result["primary_type_id"] == 2010


def test_v20_pasta_restaurant_maps_to_euro():
    result = classify_shop({
        "display_name": "Pastaio 光復店",
        "primary_type": "restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "現做義大利麵、pizza 與燉飯。"},
    })
    assert result["primary_type_id"] == 2007


def test_v20_cafe_restaurant_maps_to_cafe():
    result = classify_shop({
        "display_name": "山角咖啡",
        "primary_type": "restaurant",
        "types": ["restaurant", "cafe"],
        "ai_extracted": {"ai_summary": "咖啡、手沖、甜點與下午茶。"},
    })
    assert result["primary_type_id"] == 2012


def test_v20_ambiguous_hotpot_maps_to_hotpot():
    result = classify_shop({
        "display_name": "麻辣鍋物研究所",
        "primary_type": "asian_restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "麻辣鍋底、鴛鴦鍋與涮涮鍋。"},
    })
    assert result["primary_type_id"] == 2001


def test_v20_steak_name_override_maps_to_american():
    result = classify_shop({
        "display_name": "B&B STEAK 福德店",
        "primary_type": "restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "牛排、排餐與西式料理。"},
    })
    assert result["primary_type_id"] == 2010


def test_v20_dessert_name_override_maps_to_cafe():
    result = classify_shop({
        "display_name": "初心菓寮",
        "primary_type": "restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "甜點、茶飲與日式菓子。"},
    })
    assert result["primary_type_id"] == 2012


def test_v20_wilsonpark_steak_wine_maps_to_american():
    result = classify_shop({
        "display_name": "WilsonPark 威爾森公園 （Steak & Wine）",
        "primary_type": "restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "牛排、葡萄酒與西式餐點。"},
    })
    assert result["primary_type_id"] == 2010


def test_manual_pin_tian_pork_cutlet_maps_to_japanese():
    result = classify_shop({
        "display_name": "品田牧場 台北松山車站店",
        "primary_type": "restaurant",
        "types": ["restaurant", "food"],
        "ai_extracted": {"ai_summary": "豬排、排餐與套餐。"},
    })
    assert result["primary_type_id"] == 2004


def test_v20_zhangmen_craft_beer_maps_to_izakaya():
    result = classify_shop({
        "display_name": "掌門精釀啤酒 內湖店",
        "primary_type": "restaurant",
        "types": ["restaurant", "bar", "food"],
        "ai_extracted": {"ai_summary": "精釀啤酒、酒吧與下酒菜。"},
    })
    assert result["primary_type_id"] == 2003


def test_v20_craft_beer_bar_maps_to_izakaya():
    result = classify_shop({
        "display_name": "來吧台北日式暢飲餐酒館 | 信義暢飲 | 酒吧 | 國父紀念館",
        "primary_type": "restaurant",
        "types": ["restaurant", "bar", "food"],
        "ai_extracted": {"ai_summary": "暢飲、酒吧、精釀啤酒與下酒菜。"},
    })
    assert result["primary_type_id"] == 2003


def test_taxonomy_audit_does_not_flag_high_impact_only_rows():
    rows = build_audit_rows(
        {
            1: {
                "shop_id": 1,
                "display_name": "人氣台菜餐廳",
                "current_type_id": 2008,
                "comments": 5000,
                "score": 48,
                "db_tags": [],
                "ai_extracted": {
                    "ai_summary": "主打台菜、熱炒與家庭聚餐。",
                    "signature_dishes": ["熱炒"],
                    "atmosphere_tags": ["親子"],
                },
            },
            2: {
                "shop_id": 2,
                "display_name": "韓式烤肉測試店",
                "current_type_id": 2008,
                "comments": 5000,
                "score": 48,
                "db_tags": ["韓式"],
                "ai_extracted": {
                    "ai_summary": "韓式烤肉與泡菜鍋。",
                    "signature_dishes": ["烤肉"],
                    "atmosphere_tags": [],
                },
            },
        },
        {2002: "日式燒肉", 2008: "中式料理", 2009: "韓式料理", 2013: "異國料理"},
    )

    assert [row.shop_id for row in rows] == [2]
    assert "korean_tag_review" in rows[0].flags


def test_taxonomy_audit_suppresses_manually_verified_conflicts():
    rows = build_audit_rows(
        {
            1: {
                "shop_id": 1,
                "display_name": "溫咖哩 Wen Curry",
                "current_type_id": 2004,
                "comments": 5000,
                "score": 48,
                "db_tags": [],
                "ai_extracted": {
                    "ai_summary": "日式咖哩與牛排套餐。",
                    "signature_dishes": ["咖哩", "牛排"],
                    "atmosphere_tags": ["約會"],
                },
            },
        },
        {2004: "日式料理", 2010: "美式料理"},
    )

    assert rows == []
