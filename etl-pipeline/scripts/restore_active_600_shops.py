from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import pymysql

from app.normalizer import extract_district_from_address
from app.price import resolved_avg_price, resolved_price_label
from app.taxonomy import classify_shop


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "etl-pipeline" / "data" / "raw"
MEDIA_MANIFEST = ROOT / "web" / "data" / "shop-media.json"
TAXONOMY = ROOT / "shared" / "taxonomy.json"

PRICE_LEVEL_TO_RANGE = {
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

PRICE_LEVEL_TO_AVG = {
    "PRICE_LEVEL_INEXPENSIVE": 250,
    "PRICE_LEVEL_MODERATE": 600,
    "PRICE_LEVEL_EXPENSIVE": 1000,
    "PRICE_LEVEL_VERY_EXPENSIVE": 1800,
}

PRICE_LEVEL_TO_LABEL = {
    "PRICE_LEVEL_INEXPENSIVE": "$200-400",
    "PRICE_LEVEL_MODERATE": "$400-800",
    "PRICE_LEVEL_EXPENSIVE": "$800-1200",
    "PRICE_LEVEL_VERY_EXPENSIVE": "$1200+",
}


def load_media_ids(limit: int) -> list[int]:
    manifest = json.loads(MEDIA_MANIFEST.read_text(encoding="utf-8"))
    ids = sorted(int(shop_id) for shop_id in manifest.get("shops", {}).keys())
    if len(ids) < limit:
        raise RuntimeError(f"media manifest has only {len(ids)} shop ids, need {limit}")
    return ids[:limit]


def load_media_manifest() -> dict:
    return json.loads(MEDIA_MANIFEST.read_text(encoding="utf-8")).get("shops", {})


def load_category_names() -> dict[int, str]:
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    return {int(item["type_id"]): item["name"] for item in taxonomy.get("categories", [])}


def load_first_seen_shops(limit: int) -> list[dict]:
    shops_by_place_id: dict[str, dict] = {}
    ordered_place_ids: list[str] = []

    for path in sorted(RAW_DIR.glob("places_extracted_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        shops = data.get("shops") if isinstance(data, dict) else data
        for shop in shops or []:
            place_id = shop.get("place_id")
            if not place_id or place_id in shops_by_place_id:
                continue
            shops_by_place_id[place_id] = shop
            ordered_place_ids.append(place_id)
            if len(ordered_place_ids) == limit:
                return [shops_by_place_id[item] for item in ordered_place_ids]

    raise RuntimeError(f"raw extracted files contain only {len(ordered_place_ids)} unique shops, need {limit}")


def connect_mysql():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
        autocommit=False,
    )


def rating_score(shop: dict) -> int:
    return int(round(float(shop.get("rating") or 0) * 10))


def comments_count(shop: dict) -> int:
    return int(shop.get("user_rating_count") or 0)


def clean_text(value: object, max_len: int) -> str:
    text = str(value or "").strip()
    return text[:max_len]


def review_text(shop: dict) -> str | None:
    for review in shop.get("reviews") or []:
        text = clean_text(review.get("text"), 500)
        if text:
            return text
    return None


def atmosphere_tags(shop: dict) -> list[str]:
    tags = ["聚餐"]
    primary_type = str(shop.get("primary_type") or "")
    if "cafe" in primary_type or "ramen" in primary_type:
        tags.append("一人")
    if comments_count(shop) >= 1000:
        tags.append("熱門")
    return tags


def booking_difficulty(shop: dict) -> str:
    comments = comments_count(shop)
    if comments >= 1000:
        return "預約困難"
    if comments >= 300:
        return "建議預約"
    return "現場可入"


def ai_summary(shop: dict, district: str, category_name: str) -> str:
    name = clean_text(shop.get("display_name"), 128)
    rating = shop.get("rating")
    comments = comments_count(shop)
    rating_part = f"Google 評分 {rating:.1f}" if isinstance(rating, (int, float)) else "具在地評價"
    return (
        f"{name} 位於台北{district}，屬於{category_name}。"
        f"{rating_part}、累積 {comments} 則評論，適合用於推薦、訂位與候位通知 demo。"
    )


def restore(limit: int, dry_run: bool = False) -> None:
    media_ids = load_media_ids(limit)
    media_manifest = load_media_manifest()
    category_names = load_category_names()
    shops = load_first_seen_shops(limit)

    if dry_run:
        print(f"would_restore={len(shops)}")
        print(f"first={media_ids[0]} {shops[0]['display_name']}")
        print(f"last={media_ids[-1]} {shops[-1]['display_name']}")
        return

    conn = connect_mysql()
    restored = 0
    now = datetime.now()

    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE tb_shop SET is_active = 0 WHERE source <> 'google_places'")

            for shop_id, shop in zip(media_ids, shops, strict=True):
                place_id = clean_text(shop.get("place_id"), 255)
                name = clean_text(shop.get("display_name"), 128)
                address = clean_text(shop.get("formatted_address") or shop.get("full_address"), 255)
                district = clean_text(
                    extract_district_from_address(address, shop.get("district")),
                    20,
                )
                classified = classify_shop(shop)
                type_id = int(classified["primary_type_id"])
                category_name = clean_text(category_names.get(type_id, "餐廳"), 50)
                media = media_manifest.get(str(shop_id), {})
                image = clean_text(media.get("coverUrl") or "/icons/default.jpg", 1024)
                price_level = shop.get("price_level")

                cur.execute(
                    """
                    INSERT INTO tb_shop (
                        id, name, type_id, images, area, address, x, y, avg_price,
                        sold, comments, score, open_hours, mrt_station, mrt_distance_meters,
                        district, price_range, business_hours, place_id, source, is_active,
                        create_time, update_time
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        0, %s, %s, '', NULL, NULL,
                        %s, %s, NULL, %s, 'google_places', 1,
                        %s, %s
                    )
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        type_id = VALUES(type_id),
                        images = VALUES(images),
                        area = VALUES(area),
                        address = VALUES(address),
                        x = VALUES(x),
                        y = VALUES(y),
                        avg_price = VALUES(avg_price),
                        comments = VALUES(comments),
                        score = VALUES(score),
                        district = VALUES(district),
                        price_range = VALUES(price_range),
                        place_id = VALUES(place_id),
                        source = 'google_places',
                        is_active = 1,
                        update_time = VALUES(update_time)
                    """,
                    (
                        shop_id,
                        name,
                        type_id,
                        image,
                        district,
                        address,
                        float(shop.get("longitude") or 0),
                        float(shop.get("latitude") or 0),
                        resolved_avg_price(shop, media, PRICE_LEVEL_TO_AVG),
                        comments_count(shop),
                        rating_score(shop),
                        district,
                        PRICE_LEVEL_TO_RANGE.get(price_level),
                        place_id,
                        now,
                        now,
                    ),
                )

                cur.execute("DELETE FROM tb_shop_ai_metadata WHERE shop_id = %s", (shop_id,))
                cur.execute(
                    """
                    INSERT INTO tb_shop_ai_metadata (
                        shop_id, ai_summary, highlight_review, signature_dishes,
                        atmosphere_tags, booking_difficulty, price_per_person,
                        phone, opening_hours, extracted_at, model_version
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        shop_id,
                        ai_summary(shop, district, category_name),
                        review_text(shop),
                        json.dumps([], ensure_ascii=False),
                        json.dumps(atmosphere_tags(shop), ensure_ascii=False),
                        booking_difficulty(shop),
                        resolved_price_label(shop, media, PRICE_LEVEL_TO_LABEL),
                        clean_text(shop.get("phone"), 50),
                        json.dumps(shop.get("opening_hours") or [], ensure_ascii=False),
                        now,
                        "local-restore-600",
                    ),
                )
                restored += 1

            cur.execute(
                """
                INSERT IGNORE INTO tb_merchant_shop (user_id, shop_id, role)
                SELECT 1001, id, 'owner'
                FROM tb_shop
                WHERE is_active = 1
                  AND (
                      id IN (
                          10673, 10709, 10404, 10610, 10701,
                          10113, 10108, 10598, 10225, 10111,
                          10115, 10102, 10116
                      )
                      OR name LIKE '刁民%%'
                  )
                """
            )
            cur.execute("ALTER TABLE tb_shop AUTO_INCREMENT = %s", (max(media_ids) + 1,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"restored={restored}")
    print(f"id_min={media_ids[0]}")
    print(f"id_max={media_ids[-1]}")


def main() -> None:
    # !!! 已停用 — 這支腳本有嚴重 bug：它把 manifest 編號和 extracted 店家「按位置」配對，
    # 會把每家店的 shop_id 跟它的照片/評論/metadata 錯開（張冠李戴），且只灌淺層佔位介紹。
    # 2026-06-24 已用 scripts/rebuild_catalog_correct_ids.py（依身分對應正確編號）取代。
    # 若真的要重建 catalog，請用那支；不要跑這支。詳見 RECOVERY.md。
    raise SystemExit(
        "DISABLED: restore_active_600_shops.py scrambles shop_id vs file-stores. "
        "Use scripts/rebuild_catalog_correct_ids.py instead. See RECOVERY.md."
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    restore(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
