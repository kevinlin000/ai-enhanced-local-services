"""用「正確的原始編號」重建 tb_shop catalog（Strategy A）。

問題：restore_active_600_shops.py 把 manifest 編號和 extracted 店家「按位置」配對，
導致 DB 的 shop_id 跟所有檔案資料（manifest 照片、extracted、mongo 評論全用原始編號）錯位，
前端用 DB 新編號查 → 照片/評論/特色張冠李戴 ~480 家。

修法：把每家店的 id 設回它的原始編號。
- 原始編號 = mongo google_reviews 的 shop_id（= manifest key = 抓評論當時的編號）。
- 每個 mongo shop_id 的身分（店名 company）→ 用名稱對到 extracted 取得 place_id/地址/座標/分類。
- 照片從 manifest[原始id] 取。
結果：DB id = mongo id = manifest key，照片/評論/metadata/ABSA 一次全對齊。
新北/雜項店（mongo 沒抓過）自動淘汰；82 家被擠掉的台北店自動回來。

FK demo 資料（券/商家/訂位）用 current_db_id -> original_id 表 remap；對不到的（被淘汰的店）刪除。
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import pymysql
from pymongo import MongoClient

from app.normalizer import extract_district_from_address
from app.taxonomy import classify_shop

ROOT = Path(__file__).resolve().parents[2]
RAW_GLOB = str(ROOT / "etl-pipeline" / "data" / "raw" / "places_extracted_*.json")
MANIFEST = ROOT / "web" / "data" / "shop-media.json"
TAXONOMY = ROOT / "shared" / "taxonomy.json"
ID_MAP = ROOT / "etl-pipeline" / "data" / "mongo_shop_id_map.json"  # current_db_id -> original_id

MONGO_URI = "mongodb://localhost:27017"
OFFSET = 90_000_000  # FK remap 暫存偏移，避開 id 碰撞

PRICE_LEVEL_TO_RANGE = {"PRICE_LEVEL_INEXPENSIVE": 1, "PRICE_LEVEL_MODERATE": 2, "PRICE_LEVEL_EXPENSIVE": 3, "PRICE_LEVEL_VERY_EXPENSIVE": 4}
PRICE_LEVEL_TO_AVG = {"PRICE_LEVEL_INEXPENSIVE": 250, "PRICE_LEVEL_MODERATE": 600, "PRICE_LEVEL_EXPENSIVE": 1000, "PRICE_LEVEL_VERY_EXPENSIVE": 1800}

# FK / shop_id 子表（重建 tb_shop 前要處理）。derive 表直接清空後重生；demo 表 remap。
REGEN_TABLES = ["tb_review", "tb_shop_ai_metadata", "tb_shop_absa"]
REMAP_TABLES = [
    "tb_voucher", "tb_merchant_shop", "tb_booking", "tb_booking_incident",
    "tb_booking_deposit_adjustment", "tb_booking_slot_inventory",
    "tb_merchant_notification_dispatch", "tb_dining_memory", "tb_availability_watch",
    "tb_user_notification", "tb_shop_badge", "tb_shop_tag", "tb_private_ai_offer",
]


def n2(s: str | None) -> str:
    return re.sub(r"[\s　|｜/／()（）\[\]【】·・,，、.。\-—_]+", "", (s or "")).lower()


def db_config() -> dict:
    import os
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"), "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"), "password": os.getenv("MYSQL_PASSWORD", "password"),
        "database": os.getenv("MYSQL_DATABASE", "hmdp"), "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }


def build_canonical() -> list[dict]:
    """回傳 599 家 canonical 店家 row（id = 原始 mongo 編號）。"""
    m = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000).bytebites_reviews.google_reviews
    sid_company: dict[int, str] = {}
    for d in m.find({}, {"shop_id": 1, "company": 1}):
        sid_company.setdefault(d.get("shop_id"), d.get("company"))

    ex_by_name: dict[str, dict] = {}
    import glob
    for f in sorted(glob.glob(RAW_GLOB)):
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        for s in (data.get("shops") if isinstance(data, dict) else data) or []:
            nm = n2(s.get("display_name"))
            if nm:
                ex_by_name[nm] = s

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")).get("shops", {})
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    cat_names = {int(c["type_id"]): c["name"] for c in taxonomy.get("categories", [])}

    rows = []
    now = datetime.now()
    for sid, company in sid_company.items():
        ex = ex_by_name.get(n2(company))
        if not ex:
            continue
        address = str(ex.get("formatted_address") or ex.get("full_address") or "")[:255]
        district = str(extract_district_from_address(address, ex.get("district")) or "")[:20]
        type_id = int(classify_shop(ex)["primary_type_id"])
        price_level = ex.get("price_level")
        media = manifest.get(str(sid), {})
        image = str(media.get("coverUrl") or "/icons/default.jpg")[:1024]
        rows.append({
            "id": sid,
            "name": str(ex.get("display_name") or company)[:128],
            "type_id": type_id,
            "images": image,
            "area": district,
            "address": address,
            "x": float(ex.get("longitude") or 0),
            "y": float(ex.get("latitude") or 0),
            "avg_price": PRICE_LEVEL_TO_AVG.get(price_level),
            "comments": int(ex.get("user_rating_count") or 0),
            "score": int(round(float(ex.get("rating") or 0) * 10)),
            "district": district,
            "price_range": PRICE_LEVEL_TO_RANGE.get(price_level),
            "place_id": str(ex.get("place_id") or "")[:255],
            "now": now,
        })
    return rows


INSERT_SHOP = """
INSERT INTO tb_shop (
    id, name, type_id, images, area, address, x, y, avg_price,
    sold, comments, score, open_hours, mrt_station, mrt_distance_meters,
    district, price_range, business_hours, place_id, source, is_active,
    create_time, update_time
) VALUES (
    %(id)s, %(name)s, %(type_id)s, %(images)s, %(area)s, %(address)s, %(x)s, %(y)s, %(avg_price)s,
    0, %(comments)s, %(score)s, '', NULL, NULL,
    %(district)s, %(price_range)s, NULL, %(place_id)s, 'google_places', 1,
    %(now)s, %(now)s
)
"""


def rebuild(dry_run: bool) -> None:
    rows = build_canonical()
    id_map = {int(k): int(v) for k, v in json.loads(ID_MAP.read_text()).items()}
    new_ids = {r["id"] for r in rows}
    print(f"canonical shops: {len(rows)} | id range {min(new_ids)}-{max(new_ids)}")
    print(f"FK remap entries (current->original): {len(id_map)}")

    conn = pymysql.connect(**db_config())
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")

            # 1. FK demo 表 remap：current_db_id -> original_id；對不到的刪除。
            for tbl in REMAP_TABLES:
                try:
                    cur.execute(f"SELECT COUNT(*) c FROM {tbl}")
                except pymysql.err.ProgrammingError:
                    continue
                if cur.fetchone()["c"] == 0:
                    continue
                # 刪掉指向被淘汰店家的列
                placeholders = ",".join(["%s"] * len(id_map)) or "NULL"
                if dry_run:
                    cur.execute(f"SELECT COUNT(*) c FROM {tbl} WHERE shop_id NOT IN ({placeholders})", tuple(id_map.keys()) or (0,))
                    print(f"  {tbl}: would DELETE {cur.fetchone()['c']} rows (dropped shops), remap rest")
                    continue
                cur.execute(f"DELETE FROM {tbl} WHERE shop_id NOT IN ({placeholders})", tuple(id_map.keys()) or (0,))
                # offset 後逐一映射，避開碰撞
                cur.execute(f"UPDATE {tbl} SET shop_id = shop_id + %s WHERE shop_id IN ({placeholders})", (OFFSET, *id_map.keys()))
                for cur_id, orig_id in id_map.items():
                    cur.execute(f"UPDATE {tbl} SET shop_id = %s WHERE shop_id = %s", (orig_id, cur_id + OFFSET))

            # 2. 重生表清空
            for tbl in REGEN_TABLES:
                if dry_run:
                    print(f"  {tbl}: would TRUNCATE (regenerate after)")
                else:
                    cur.execute(f"DELETE FROM {tbl}")

            # 3. 重建 tb_shop
            if dry_run:
                cur.execute("SELECT COUNT(*) c FROM tb_shop")
                print(f"  tb_shop: would replace {cur.fetchone()['c']} rows with {len(rows)} canonical rows")
            else:
                cur.execute("DELETE FROM tb_shop")
                cur.executemany(INSERT_SHOP, rows)
                cur.execute("ALTER TABLE tb_shop AUTO_INCREMENT = %s", (max(new_ids) + 1,))

            cur.execute("SET FOREIGN_KEY_CHECKS=1")
        if not dry_run:
            conn.commit()
            print("COMMITTED.")
    finally:
        conn.close()

    if not dry_run:
        conn = pymysql.connect(**db_config())
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM tb_shop WHERE is_active=1")
            print(f"verify active shops: {cur.fetchone()['c']}")
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    rebuild(ap.parse_args().dry_run)


if __name__ == "__main__":
    main()
