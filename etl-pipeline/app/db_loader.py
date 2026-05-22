import os
import json
import re
from pathlib import Path
from datetime import datetime
import pymysql
import structlog

log = structlog.get_logger()

# Google primary_type 對到新 2xxx
TYPE_MAPPING = {
    "hot_pot_restaurant": 2001,
    "shabu_shabu_restaurant": 2001,
    "barbecue_restaurant": 2002,
    "korean_barbecue_restaurant": 2002,
    "yakiniku_restaurant": 2002,
    "mongolian_barbecue_restaurant": 2002,
    "yakitori_restaurant": 2003,
    "japanese_pub": 2003,
    "izakaya": 2003,
    "japanese_izakaya_restaurant": 2003,
    "japanese_restaurant": 2004,
    "ramen_restaurant": 2004,
    "sushi_restaurant": 2004,
    "udon_noodle_restaurant": 2004,
    "sukiyaki_restaurant": 2004,
    "fine_dining_restaurant": 2011,
    "buffet_restaurant": 2011,
    "steak_house": 2006,
    "italian_restaurant": 2007,
    "french_restaurant": 2007,
    "european_restaurant": 2007,
    "mediterranean_restaurant": 2007,
    "chinese_restaurant": 2008,
    "taiwanese_restaurant": 2008,
    "cantonese_restaurant": 2008,
    "dim_sum_restaurant": 2008,
    "seafood_restaurant": 2008,
    "middle_eastern_restaurant": 2008,
    "vietnamese_restaurant": 2008,
    "thai_restaurant": 2008,
    "asian_restaurant": 2008,
    "vegan_restaurant": 2008,
    "korean_restaurant": 2009,
    "brunch_restaurant": 2010,
    "american_restaurant": 2010,
    "australian_restaurant": 2010,
    "mexican_restaurant": 2010,
    "hot_dog_restaurant": 2010,
    "bar_and_grill": 2010,
    "cafe": 2012,
    "coffee_shop": 2012,
    "dessert_shop": 2012,
    "pastry_shop": 2012,
    "restaurant": 2008,  # fallback 中式
    "bar": 2003,
}


def smart_type_id(shop):
    primary_type = shop.get("primary_type", "restaurant")
    name = shop.get("display_name", "")

    # 1. 先看 primary_type
    if primary_type in TYPE_MAPPING:
        type_id = TYPE_MAPPING[primary_type]
    else:
        type_id = 2008  # fallback

    # 2. 店名關鍵字覆寫
    name_lower = name.lower()
    if "咖啡" in name or "cafe" in name_lower or "coffee" in name_lower:
        return 2012
    if "壽喜燒" in name:
        return 2004
    if "燒肉" in name and type_id == 2008:
        return 2002
    if "義" in name and "大利" in name:
        return 2007
    if "甜點" in name or "蛋糕" in name:
        return 2012

    return type_id

PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def extract_avg_price(price_str):
    """從 '$600-1000' 或 '$1500' 抽出平均數字"""
    if not price_str or price_str == "未提及":
        return None
    nums = re.findall(r'\d+', price_str.replace(",", ""))
    if not nums:
        return None
    nums = [int(n) for n in nums]
    if len(nums) >= 2:
        return (nums[0] + nums[1]) // 2
    return nums[0]


def load():
    # 讀最新 extracted json
    raw_dir = Path("data/raw")
    latest = sorted(raw_dir.glob("places_extracted_*.json"))[-1]
    log.info("reading", file=str(latest))
    data = json.loads(latest.read_text())
    shops = data["shops"]
    log.info("shops_to_load", count=len(shops))

    # 連 DB
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
        autocommit=False,
    )

    success = 0
    skipped = 0
    failed = []

    try:
        with conn.cursor() as cur:
            for shop in shops:
                place_id = shop["place_id"]
                name = shop["display_name"]

                # 1. 檢查 place_id 是否已存在
                cur.execute("SELECT id FROM tb_shop WHERE place_id = %s", (place_id,))
                row = cur.fetchone()
                if row:
                    log.info("skip_existing", name=name)
                    skipped += 1
                    continue

                try:
                    # 2. type_id mapping
                    type_id = smart_type_id(shop)

                    # 3. price_range
                    price_level = shop.get("price_level")
                    price_range = PRICE_LEVEL_MAP.get(price_level) if price_level else None

                    # 4. avg_price 從 ai_extracted
                    ai = shop.get("ai_extracted", {})
                    avg_price = extract_avg_price(ai.get("price_per_person", ""))

                    # 5. score = rating × 10
                    score = int((shop.get("rating") or 0) * 10)

                    # 6. INSERT tb_shop
                    cur.execute("""
                        INSERT INTO tb_shop
                        (name, type_id, images, area, address, x, y, avg_price,
                         sold, comments, score, open_hours, district, price_range,
                         place_id, source, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, %s, 'google_places', 1)
                    """, (
                        name,
                        type_id,
                        "/icons/default.jpg",
                        shop.get("district"),
                        shop.get("formatted_address", ""),
                        shop.get("longitude", 0),  # x = lng
                        shop.get("latitude", 0),   # y = lat
                        avg_price,
                        shop.get("user_rating_count", 0),
                        score,
                        "",  # open_hours 舊欄位、空字串
                        shop.get("district"),
                        price_range,
                        place_id,
                    ))
                    shop_id = cur.lastrowid

                    # 7. INSERT tb_shop_ai_metadata
                    cur.execute("""
                        INSERT INTO tb_shop_ai_metadata
                        (shop_id, ai_summary, highlight_review, signature_dishes,
                         atmosphere_tags, booking_difficulty, price_per_person,
                         phone, opening_hours, extracted_at, model_version)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        shop_id,
                        ai.get("ai_summary"),
                        ai.get("highlight_review"),
                        json.dumps(ai.get("signature_dishes", []), ensure_ascii=False),
                        json.dumps(ai.get("atmosphere_tags", []), ensure_ascii=False),
                        ai.get("booking_difficulty"),
                        ai.get("price_per_person"),
                        shop.get("phone"),
                        json.dumps(shop.get("opening_hours", []), ensure_ascii=False),
                        datetime.now(),
                        os.getenv("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite"),
                    ))

                    conn.commit()
                    success += 1
                    log.info("loaded", idx=success, name=name, type_id=type_id)
                except Exception as e:
                    conn.rollback()
                    log.error("load_failed", name=name, error=str(e))
                    failed.append({"name": name, "error": str(e)})
    finally:
        conn.close()

    log.info("done", success=success, skipped=skipped, failed=len(failed))
    if failed:
        for f in failed[:5]:
            log.error("failed_sample", **f)


if __name__ == "__main__":
    load()
