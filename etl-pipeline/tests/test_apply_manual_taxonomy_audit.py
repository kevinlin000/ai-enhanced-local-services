from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from scripts.apply_manual_taxonomy_audit import apply_rows, parse_audit_text


CATEGORY_MAP = {
    "中式料理": 2008,
    "火鍋": 2001,
    "美式料理": 2010,
    "韓式料理": 2009,
    "異國料理": 2013,
    "義法料理": 2007,
    "咖啡/甜點": 2012,
    "日式燒肉": 2002,
    "自助餐": 2011,
    "素食": 2005,
    "居酒屋": 2003,
    "日式料理": 2004,
    "印度料理": 2013,
}


def test_parse_manual_audit_text_common_user_formats():
    rows = parse_audit_text(
        """
        花嶼輕食館Flower Island Brunch：改為 咖啡/甜點
        知初植物系永續廚房 維持 素食
        亞瑟蘭印度餐廳(士林店)Asrah Indian Cuisines 清真認證Halal 是印度料理
        燒肉眾精緻炭火燒肉 台北西門店：維持 日式燒肉（並移除「韓式」tag）
        大樹先生的家 是 義法料理（並移除「韓式」tag）
        大叔食事 是 日式料理（沒有韓式標籤）
        """,
        CATEGORY_MAP,
    )

    assert [(row.match, row.type_id, row.suppress_tags) for row in rows] == [
        ("花嶼輕食館Flower Island Brunch", 2012, ()),
        ("知初植物系永續廚房", 2005, ()),
        ("亞瑟蘭印度餐廳", 2013, ()),
        ("燒肉眾精緻炭火燒肉 台北西門店", 2002, ("韓式",)),
        ("大樹先生的家", 2007, ("韓式",)),
        ("大叔食事", 2004, ("韓式",)),
    ]


def test_apply_rows_adds_and_updates_without_duplicate_matches():
    payload = {
        "meta": {"version": 1},
        "primary_type_overrides": [
            {"match": "品田牧場", "type_id": 2010, "source": "manual_audit"},
            {"match": "大樹先生的家", "type_id": 2007, "source": "manual_audit"},
        ],
        "suppress_tags": [
            {"match": "大樹先生的家", "tags": ["韓式"], "source": "manual_audit"},
        ],
    }
    rows = parse_audit_text(
        """
        品田牧場 台北松山車站店 改為 日式料理
        大樹先生的家 是 義法料理（並移除「韓式」tag）
        新測試餐廳 改為 火鍋
        """,
        CATEGORY_MAP,
    )

    next_payload, stats = apply_rows(payload, rows)

    by_match = {row["match"]: row for row in next_payload["primary_type_overrides"]}
    suppress_by_match = {row["match"]: row for row in next_payload["suppress_tags"]}
    assert by_match["品田牧場 台北松山車站店"]["type_id"] == 2004
    assert by_match["大樹先生的家"]["type_id"] == 2007
    assert by_match["新測試餐廳"]["type_id"] == 2001
    assert suppress_by_match["大樹先生的家"]["tags"] == ["韓式"]
    assert stats == {
        "primary_added": 2,
        "primary_updated": 0,
        "primary_unchanged": 1,
        "suppress_added": 0,
        "suppress_unchanged": 1,
    }
