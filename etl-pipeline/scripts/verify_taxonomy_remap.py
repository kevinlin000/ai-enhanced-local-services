from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
sys.path.append(str(ROOT / "app"))

import db_loader  # noqa: E402


OLD_TYPE_NAME = {
    2001: "火鍋",
    2002: "日式燒肉",
    2003: "居酒屋",
    2004: "日式料理",
    2007: "義法料理",
    2008: "中式料理",
    2010: "美式 / Brunch",
    2011: "高級餐廳",
    2012: "特色咖啡",
}

NEW_TYPE_NAME = {
    2001: "火鍋",
    2002: "日式燒肉",
    2003: "居酒屋",
    2004: "日式料理",
    2005: "素食",
    2007: "義法料理",
    2008: "中式料理",
    2010: "美式料理",
    2011: "自助餐",
    2012: "咖啡/甜點",
}

EXPECTED_COUNTS = {
    2001: 20,
    2002: 6,
    2003: 3,
    2004: 3,
    2005: 4,
    2007: 8,
    2008: 37,
    2010: 10,
    2011: 5,
    2012: 7,
}

# Source of truth for proposed remap in docs/taxonomy-spec.md
PROPOSED_TYPE_IDS = {
    10099: 2004,
    10100: 2004,
    10101: 2008,
    10102: 2001,
    10103: 2011,
    10104: 2011,
    10105: 2003,
    10106: 2011,
    10107: 2002,
    10108: 2012,
    10109: 2008,
    10110: 2007,
    10111: 2008,
    10112: 2010,
    10113: 2008,
    10114: 2008,
    10115: 2001,
    10116: 2008,
    10117: 2008,
    10118: 2008,
    10119: 2008,
    10120: 2008,
    10121: 2008,
    10122: 2010,
    10123: 2008,
    10124: 2005,
    10125: 2007,
    10126: 2008,
    10127: 2001,
    10128: 2001,
    10129: 2008,
    10130: 2008,
    10131: 2001,
    10132: 2008,
    10133: 2012,
    10134: 2008,
    10135: 2008,
    10136: 2010,
    10137: 2001,
    10138: 2007,
    10139: 2005,
    10140: 2010,
    10141: 2008,
    10142: 2010,
    10143: 2008,
    10144: 2001,
    10145: 2008,
    10146: 2008,
    10147: 2008,
    10148: 2008,
    10149: 2007,
    10150: 2012,
    10151: 2012,
    10152: 2001,
    10153: 2008,
    10154: 2008,
    10155: 2008,
    10156: 2001,
    10157: 2008,
    10158: 2010,
    10159: 2007,
    10160: 2008,
    10161: 2008,
    10162: 2001,
    10163: 2011,
    10164: 2008,
    10165: 2002,
    10166: 2001,
    10167: 2008,
    10168: 2001,
    10169: 2005,
    10170: 2005,
    10171: 2002,
    10172: 2001,
    10173: 2002,
    10174: 2012,
    10175: 2002,
    10176: 2011,
    10177: 2001,
    10178: 2008,
    10179: 2001,
    10180: 2010,
    10181: 2010,
    10182: 2001,
    10183: 2007,
    10184: 2008,
    10185: 2001,
    10186: 2001,
    10187: 2012,
    10188: 2001,
    10189: 2008,
    10190: 2002,
    10191: 2008,
    10192: 2003,
    10193: 2007,
    10194: 2012,
    10195: 2010,
    10196: 2007,
    10197: 2001,
    10198: 2008,
    10199: 2003,
    10200: 2004,
    10201: 2010,
}

DEFAULT_FOCUS_IDS = [10171, 10181, 10183]


def load_shops() -> dict[int, dict]:
    shops: dict[int, dict] = {}
    for path in sorted(RAW_DIR.glob("places_extracted_*.json")):
        payload = json.loads(path.read_text())
        for shop in payload.get("shops", []):
            shop_id = shop.get("shop_id")
            if shop_id:
                shops[shop_id] = shop
    return shops


def short(value: object, limit: int = 180) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def verify_counts(shops: dict[int, dict]) -> int:
    exit_code = 0
    unique_count = len(shops)
    print(f"unique shops: {unique_count}")
    if unique_count != 103:
        print("ERROR unique shop count mismatch: expected 103")
        exit_code = 1

    missing = sorted(set(shops) - set(PROPOSED_TYPE_IDS))
    unknown = sorted(set(PROPOSED_TYPE_IDS) - set(shops))
    if missing:
        print(f"ERROR shops missing from proposed map: {missing}")
        exit_code = 1
    if unknown:
        print(f"ERROR proposed map ids not found in data: {unknown}")
        exit_code = 1

    counts = Counter(PROPOSED_TYPE_IDS.values())
    print("\nproposed group by new_type_id")
    for type_id in sorted(NEW_TYPE_NAME):
        count = counts.get(type_id, 0)
        expected = EXPECTED_COUNTS.get(type_id)
        status = "OK" if count == expected else f"EXPECTED {expected}"
        print(f"{type_id} {NEW_TYPE_NAME[type_id]}: {count} [{status}]")
        if expected is not None and count != expected:
            exit_code = 1

    return exit_code


def dump_cross_category_moves(shops: dict[int, dict]) -> None:
    print("\ncross-category moves")
    for shop_id in sorted(PROPOSED_TYPE_IDS):
        old_type_id = db_loader.smart_type_id(shops[shop_id])
        new_type_id = PROPOSED_TYPE_IDS[shop_id]
        if old_type_id == new_type_id:
            continue
        old_name = OLD_TYPE_NAME.get(old_type_id, str(old_type_id))
        new_name = NEW_TYPE_NAME.get(new_type_id, str(new_type_id))
        print(f"{shop_id} {shops[shop_id].get('display_name')}: {old_name} -> {new_name}")


def dump_focus(shops: dict[int, dict], focus_ids: list[int]) -> None:
    print("\nfocus evidence")
    for shop_id in focus_ids:
        shop = shops.get(shop_id)
        if not shop:
            print(f"{shop_id}: not found")
            continue
        old_type_id = db_loader.smart_type_id(shop)
        new_type_id = PROPOSED_TYPE_IDS.get(shop_id)
        ai = shop.get("ai_extracted", {}) or {}
        print(f"\n[{shop_id}] {shop.get('display_name')}")
        print(f"old={OLD_TYPE_NAME.get(old_type_id, old_type_id)} new={NEW_TYPE_NAME.get(new_type_id, new_type_id)}")
        print(f"primary_type={shop.get('primary_type')}")
        print(f"types={', '.join(shop.get('types', [])[:8])}")
        print(f"price={ai.get('price_per_person')}")
        print(f"atmosphere={ai.get('atmosphere_tags')}")
        print(f"dishes={ai.get('signature_dishes')}")
        print(f"summary={short(ai.get('ai_summary'))}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--focus-ids",
        nargs="*",
        type=int,
        default=DEFAULT_FOCUS_IDS,
        help="shop ids to dump evidence for",
    )
    parser.add_argument(
        "--no-cross-moves",
        action="store_true",
        help="skip full cross-category move dump",
    )
    args = parser.parse_args()

    shops = load_shops()
    exit_code = verify_counts(shops)
    if not args.no_cross_moves:
        dump_cross_category_moves(shops)
    dump_focus(shops, args.focus_ids)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
