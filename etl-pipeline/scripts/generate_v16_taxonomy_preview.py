from __future__ import annotations

import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT.parent / "docs" / "_internal"
RAW_DIR = ROOT / "data" / "raw"
SPEC_PATH = ROOT.parent / "docs" / "taxonomy-spec.md"
sys.path.append(str(ROOT))

from app.taxonomy import classify_shop  # noqa: E402


OLD_NAME_TO_ID = {
    "火鍋": 2001,
    "日式燒肉": 2002,
    "居酒屋": 2003,
    "日式料理": 2004,
    "義法料理": 2007,
    "中式料理": 2008,
    "美式 / Brunch": 2010,
    "高級餐廳": 2011,
    "特色咖啡": 2012,
}

SEEDED_TAG_CODES = {
    "Brunch",
    "早午餐",
    "牛排",
    "韓式",
    "法式",
    "義式",
    "餐酒館",
    "鐵板燒",
    "吃到飽",
    "約會",
    "商務",
    "包廂",
    "景觀",
    "親子",
    "免訂金",
    "HotSeat",
}

TYPE_REPURPOSE = [
    (2005, "素食"),
    (2011, "自助餐"),
    (2012, "咖啡/甜點"),
]

TYPE_DEACTIVATE = [2006, 2009]


def load_shops() -> dict[int, dict]:
    shops: dict[int, dict] = {}
    for path in sorted(RAW_DIR.glob("places_extracted_*.json")):
        payload = json.loads(path.read_text())
        for shop in payload.get("shops", []):
            shop_id = shop.get("shop_id")
            if shop_id:
                shops[shop_id] = shop
    return shops


def parse_old_type_ids_from_spec() -> dict[int, int]:
    old_ids: dict[int, int] = {}
    for line in SPEC_PATH.read_text().splitlines():
        if not line.startswith("| "):
            continue
        match = re.match(r"^\|\s*(\d+)\s*\|\s*.*?\|\s*([^|]+?)\s*\|\s*\d+\s+[^|]+\|", line)
        if not match:
            continue
        shop_id = int(match.group(1))
        old_name = match.group(2).strip()
        if old_name in OLD_NAME_TO_ID:
            old_ids[shop_id] = OLD_NAME_TO_ID[old_name]
    return old_ids


def parse_spec_tags_from_spec() -> dict[int, list[str]]:
    tags_by_shop: dict[int, list[str]] = {}
    in_full_remap = False
    for raw_line in SPEC_PATH.read_text().splitlines():
        line = raw_line.strip()
        if line == "### 4.2 Full 103-Shop Remap":
            in_full_remap = True
            continue
        if not in_full_remap:
            continue
        if line.startswith("## ") and line != "### 4.2 Full 103-Shop Remap":
            break
        if not line.startswith("| "):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 8:
            continue
        if parts[1] in {"shop_id", "---"}:
            continue
        try:
            shop_id = int(parts[1])
        except ValueError:
            continue
        raw_tags = parts[6]
        if raw_tags == "-" or not raw_tags:
            tags_by_shop[shop_id] = []
            continue
        tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
        tags_by_shop[shop_id] = tags
    return tags_by_shop


def sql_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def build_up_sql(shops: dict[int, dict], spec_tags_by_shop: dict[int, list[str]]) -> str:
    rows = []
    badge_rows = []
    tag_rows = []

    for shop_id in sorted(shops):
        result = classify_shop(shops[shop_id])
        rows.append((shop_id, int(result["primary_type_id"])))
        for badge_code in result["badges"]:
            badge_rows.append((shop_id, badge_code, "allowlist"))
        for tag_code in spec_tags_by_shop.get(shop_id, []):
            tag_rows.append((shop_id, tag_code))

    lines: list[str] = []
    lines.append("-- V16 taxonomy backfill preview")
    lines.append("START TRANSACTION;")
    lines.append("")
    for type_id, name in TYPE_REPURPOSE:
        lines.append(
            f"UPDATE tb_shop_type SET name = {sql_quote(name)}, is_active = 1 WHERE id = {type_id};"
        )
    lines.append(
        "UPDATE tb_shop_type SET is_active = 0 WHERE id IN (2006, 2009);"
    )
    lines.append("")

    lines.append("INSERT INTO tb_shop_badge (shop_id, badge_code, source)")
    lines.append("VALUES")
    for idx, (shop_id, badge_code, source) in enumerate(badge_rows):
        suffix = "," if idx < len(badge_rows) - 1 else ""
        lines.append(f"  ({shop_id}, {sql_quote(badge_code)}, {sql_quote(source)}){suffix}")
    lines.append("ON DUPLICATE KEY UPDATE source = VALUES(source);")
    lines.append("")

    lines.append("INSERT IGNORE INTO tb_shop_tag (shop_id, tag_code)")
    lines.append("VALUES")
    for idx, (shop_id, tag_code) in enumerate(tag_rows):
        suffix = "," if idx < len(tag_rows) - 1 else ""
        lines.append(f"  ({shop_id}, {sql_quote(tag_code)}){suffix}")
    lines.append(";")
    lines.append("")

    lines.append("UPDATE tb_shop")
    lines.append("SET type_id = CASE id")
    for shop_id, type_id in rows:
        lines.append(f"  WHEN {shop_id} THEN {type_id}")
    lines.append("  ELSE type_id")
    lines.append("END")
    lines.append(
        "WHERE id IN (" + ", ".join(str(shop_id) for shop_id, _ in rows) + ");"
    )
    lines.append("")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def build_rollback_sql(
    shops: dict[int, dict],
    old_type_ids: dict[int, int],
    spec_tags_by_shop: dict[int, list[str]],
) -> str:
    badge_rows = []
    tag_rows = []
    for shop_id in sorted(shops):
        result = classify_shop(shops[shop_id])
        for badge_code in result["badges"]:
            badge_rows.append((shop_id, badge_code))
        for tag_code in spec_tags_by_shop.get(shop_id, []):
            tag_rows.append((shop_id, tag_code))

    lines: list[str] = []
    lines.append("-- V16 taxonomy rollback preview")
    lines.append("START TRANSACTION;")
    lines.append("")
    lines.append("UPDATE tb_shop_type SET name = '無菜單料理', is_active = 1 WHERE id = 2005;")
    lines.append("UPDATE tb_shop_type SET name = '高級餐廳', is_active = 1 WHERE id = 2011;")
    lines.append("UPDATE tb_shop_type SET name = '特色咖啡', is_active = 1 WHERE id = 2012;")
    lines.append("UPDATE tb_shop_type SET is_active = 1 WHERE id IN (2006, 2009);")
    lines.append("")
    if badge_rows:
        lines.append("DELETE FROM tb_shop_badge")
        lines.append("WHERE (shop_id, badge_code) IN (")
        for idx, (shop_id, badge_code) in enumerate(badge_rows):
            suffix = "," if idx < len(badge_rows) - 1 else ""
            lines.append(f"  ({shop_id}, {sql_quote(badge_code)}){suffix}")
        lines.append(");")
        lines.append("")
    if tag_rows:
        lines.append("DELETE FROM tb_shop_tag")
        lines.append("WHERE (shop_id, tag_code) IN (")
        for idx, (shop_id, tag_code) in enumerate(tag_rows):
            suffix = "," if idx < len(tag_rows) - 1 else ""
            lines.append(f"  ({shop_id}, {sql_quote(tag_code)}){suffix}")
        lines.append(");")
        lines.append("")
    lines.append("UPDATE tb_shop")
    lines.append("SET type_id = CASE id")
    for shop_id in sorted(old_type_ids):
        lines.append(f"  WHEN {shop_id} THEN {old_type_ids[shop_id]}")
    lines.append("  ELSE type_id")
    lines.append("END")
    lines.append(
        "WHERE id IN (" + ", ".join(str(shop_id) for shop_id in sorted(old_type_ids)) + ");"
    )
    lines.append("")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def main() -> None:
    shops = load_shops()
    old_type_ids = parse_old_type_ids_from_spec()
    spec_tags_by_shop = parse_spec_tags_from_spec()
    if len(shops) != 103:
        raise SystemExit(f"expected 103 shops, got {len(shops)}")
    if len(old_type_ids) != 103:
        raise SystemExit(f"expected 103 old type ids from spec, got {len(old_type_ids)}")
    if len(spec_tags_by_shop) != 103:
        raise SystemExit(f"expected 103 spec tag rows, got {len(spec_tags_by_shop)}")

    used_tag_codes = {tag for tags in spec_tags_by_shop.values() for tag in tags}
    missing_tag_codes = sorted(used_tag_codes - SEEDED_TAG_CODES)
    print("spec_tag_codes=", sorted(used_tag_codes))
    print("missing_seeded_tag_codes=", missing_tag_codes)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    up_path = DOCS_DIR / "V16__taxonomy_backfill.preview.sql"
    rollback_path = DOCS_DIR / "V16__taxonomy_backfill.rollback.preview.sql"
    up_path.write_text(build_up_sql(shops, spec_tags_by_shop))
    rollback_path.write_text(build_rollback_sql(shops, old_type_ids, spec_tags_by_shop))
    print(up_path)
    print(rollback_path)


if __name__ == "__main__":
    main()
