from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from scripts.sync_manual_taxonomy_to_db import ShopRow, build_sync_plan


def test_build_sync_plan_updates_primary_types_and_suppresses_tags():
    overrides = {
        "primary_type_overrides": [
            {"match": "品田牧場", "type_id": 2004, "source": "manual_audit"},
            {"match": "大樹先生的家", "type_id": 2007, "source": "manual_audit"},
        ],
        "suppress_tags": [
            {"match": "大樹先生的家", "tags": ["韓式"], "source": "manual_audit"},
            {"match": "肉次方 燒肉放題 台北峨眉店", "tags": ["韓式"], "source": "manual_audit"},
        ],
    }
    shops = [
        ShopRow(id=1, name="品田牧場 台北松山車站店", type_id=2010),
        ShopRow(id=2, name="大樹先生的家", type_id=2007, tag_codes=("韓式", "親子")),
        ShopRow(id=3, name="肉次方 燒肉放題 台北峨眉店", type_id=2002, tag_codes=("吃到飽",)),
    ]

    plan = build_sync_plan(overrides, shops)

    assert [(item.shop_id, item.old_type_id, item.new_type_id) for item in plan.primary_updates] == [
        (1, 2010, 2004)
    ]
    assert [(item.shop_id, item.tag_code) for item in plan.tag_deletes] == [(2, "韓式")]
    assert plan.primary_unchanged == 1
    assert plan.missing_matches == ()


def test_build_sync_plan_reports_missing_matches_once():
    overrides = {
        "primary_type_overrides": [
            {"match": "不存在餐廳", "type_id": 2004, "source": "manual_audit"},
        ],
        "suppress_tags": [
            {"match": "不存在餐廳", "tags": ["韓式"], "source": "manual_audit"},
        ],
    }

    plan = build_sync_plan(overrides, [])

    assert plan.primary_updates == ()
    assert plan.tag_deletes == ()
    assert plan.missing_matches == ("不存在餐廳",)
