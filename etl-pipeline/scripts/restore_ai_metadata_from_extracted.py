"""從 places_extracted_*.json 還原真實 AI metadata 到 tb_shop_ai_metadata。

背景：restore_active_600_shops.py 把每家店的 ai_summary 蓋成佔位文
（model_version='local-restore-600'），導致前端餐廳介紹/招牌菜/標籤消失。
本腳本用「真實」的 ai_extracted 內容覆蓋回去。

關鍵設計：以 place_id join，而非 extracted 檔內的 shop_id 欄位。
restore 腳本重新編過 shop_id，extracted 檔的 shop_id 已過期，
直接用會張冠李戴（例如把雞家莊的介紹掛到下港吔）。place_id 是穩定鍵。

合併規則與前端 extractedShops.ts 一致：掃所有 places_extracted_*.json，
同一 place_id 後出現的檔案覆蓋先前的（last-wins）。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[2]
RAW_GLOB = str(ROOT / "etl-pipeline" / "data" / "raw" / "places_extracted_*.json")
MODEL_VERSION = "extracted-restore-v1"
MIN_SUMMARY_LEN = 100  # 視為「有料」的最短介紹長度


def db_config() -> dict:
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "password"),
        "database": os.getenv("MYSQL_DATABASE", "hmdp"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }


def load_extracted_by_place_id() -> dict[str, dict]:
    """所有 extracted 檔合併，以 place_id 為鍵，last-wins，只留有料介紹。"""
    by_pid: dict[str, dict] = {}
    for path in sorted(glob.glob(RAW_GLOB)):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        shops = data.get("shops") if isinstance(data, dict) else data
        for shop in shops or []:
            pid = shop.get("place_id")
            ai = (shop.get("ai_extracted") or {}).get("ai_summary") or ""
            if pid and len(ai) >= MIN_SUMMARY_LEN:
                by_pid[pid] = shop
    return by_pid


def as_json(value) -> str:
    """list/dict -> JSON 字串；None/空 -> '[]'（欄位是 JSON 型別，需合法 JSON）。"""
    if value is None or value == "":
        return "[]"
    if isinstance(value, str):
        try:
            json.loads(value)
            return value
        except json.JSONDecodeError:
            return json.dumps([value], ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False)


UPSERT = """
INSERT INTO tb_shop_ai_metadata (
    shop_id, ai_summary, highlight_review, signature_dishes,
    atmosphere_tags, booking_difficulty, price_per_person,
    phone, opening_hours, extracted_at, model_version
) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
    ai_summary = VALUES(ai_summary),
    highlight_review = VALUES(highlight_review),
    signature_dishes = VALUES(signature_dishes),
    atmosphere_tags = VALUES(atmosphere_tags),
    booking_difficulty = VALUES(booking_difficulty),
    price_per_person = VALUES(price_per_person),
    phone = VALUES(phone),
    opening_hours = VALUES(opening_hours),
    extracted_at = VALUES(extracted_at),
    model_version = VALUES(model_version)
"""


def restore(dry_run: bool) -> None:
    by_pid = load_extracted_by_place_id()
    conn = pymysql.connect(**db_config())
    now = datetime.now()
    updated = skipped = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, place_id FROM tb_shop WHERE is_active = 1")
            shops = cur.fetchall()
            for shop in shops:
                rec = by_pid.get(shop["place_id"])
                if not rec:
                    skipped += 1
                    continue
                ai = rec.get("ai_extracted") or {}
                params = (
                    shop["id"],
                    (ai.get("ai_summary") or "").strip(),
                    (rec.get("highlight_review") or ai.get("highlight_review") or "")[:500] or None,
                    as_json(ai.get("signature_dishes")),
                    as_json(ai.get("atmosphere_tags")),
                    (ai.get("booking_difficulty") or None),
                    (ai.get("price_per_person") or None),
                    (rec.get("phone") or None),
                    as_json(rec.get("opening_hours")),
                    now,
                    MODEL_VERSION,
                )
                if dry_run:
                    if updated < 3:
                        print(f"  [{shop['id']}] {shop['name']}: {params[1][:50]}... dishes={params[3][:40]}")
                else:
                    cur.execute(UPSERT, params)
                updated += 1
        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    print(f"\n{'DRY-RUN ' if dry_run else ''}done: updated={updated} skipped_no_extracted={skipped}")
    # 自我驗證：寫入後不應再有 local-restore-600 佔位（除非該店無 extracted）
    if not dry_run:
        conn = pymysql.connect(**db_config())
        with conn.cursor() as cur:
            cur.execute(
                "SELECT model_version, COUNT(*) c FROM tb_shop_ai_metadata GROUP BY model_version"
            )
            for row in cur.fetchall():
                print(f"  model_version {row['model_version']}: {row['c']}")
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    restore(ap.parse_args().dry_run)


if __name__ == "__main__":
    main()
