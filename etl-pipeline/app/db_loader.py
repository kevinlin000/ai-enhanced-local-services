import argparse
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
    "soup_restaurant": 2001,
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
    "teppanyaki_restaurant": 2011,
    "fine_dining_restaurant": 2011,
    "buffet_restaurant": 2011,
    "steak_house": 2006,
    "italian_restaurant": 2007,
    "french_restaurant": 2007,
    "european_restaurant": 2007,
    "bistro": 2007,
    "gastropub": 2007,
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

HOTPOT_KEYWORDS = {
    "火鍋", "鍋物", "麻辣鍋", "酸菜白肉鍋", "酸菜白肉", "羊肉爐", "涮涮", "涮涮鍋",
    "涮涮屋", "壽喜燒", "鍋底", "鴛鴦鍋", "和牛涮", "石二鍋", "詹記",
}
YAKINIKU_KEYWORDS = {"燒肉", "烤肉", "和牛燒肉", "牛舌"}
IZAKAYA_KEYWORDS = {"居酒屋", "串燒", "酒場", "小酒館"}
JAPANESE_KEYWORDS = {"日式", "和食", "壽司", "生魚片", "拉麵", "天婦羅", "懷石", "沾麵", "烏龍麵"}
FINE_DINING_KEYWORDS = {
    "鐵板燒", "teppanyaki", "fine dining", "高級", "吃到飽", "buffet", "自助餐",
    "和食集錦", "饗饗", "旭集", "宴請", "套餐", "儀式感",
}
EUROPEAN_KEYWORDS = {"義式", "義大利", "法式", "歐陸", "bistro", "pub", "dining pub"}
KOREAN_KEYWORDS = {"韓式", "豆腐鍋", "韓國料理", "韓式炸雞"}
BRUNCH_KEYWORDS = {"早午餐", "brunch", "漢堡"}
CAFE_KEYWORDS = {"咖啡", "cafe", "coffee", "甜點", "蛋糕", "下午茶"}
CHINESE_KEYWORDS = {"台菜", "滬菜", "粵菜", "港點", "熱炒", "台式", "川菜", "客家", "小籠包", "麵食"}
BUFFET_KEYWORDS = {"自助餐", "buffet", "吃到飽", "饗食天堂", "旭集", "饗饗", "inparadise"}

NAME_OVERRIDES = {
    "一蘭": 2004,
    "鼎泰豐": 2008,
    "葉公館": 2008,
    "紅翻天": 2008,
    "港都熱炒": 2008,
    "欣葉": 2008,
    "海霸王": 2008,
    "饗食天堂": 2011,
    "旭集": 2011,
    "饗饗": 2011,
    "雙月食品社": 2008,
    "雙月": 2008,
    "和牛涮": 2001,
    "一番地壽喜燒": 2001,
    "大樹先生的家": 2010,
    "蔬食百匯": 2011,
    "旭穗蔬食": 2012,
}


def _build_text_blob(shop: dict) -> str:
    ai = shop.get("ai_extracted", {}) or {}
    parts = [
        shop.get("display_name", ""),
        shop.get("primary_type", ""),
        " ".join(shop.get("types", []) or []),
        ai.get("ai_summary", ""),
        " ".join(ai.get("signature_dishes", []) or []),
        " ".join(ai.get("atmosphere_tags", []) or []),
        ai.get("booking_difficulty", ""),
        ai.get("price_per_person", ""),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _contains_any(text: str, keywords: set[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def smart_type_id(shop):
    primary_type = shop.get("primary_type", "restaurant")
    name = shop.get("display_name", "")
    text = _build_text_blob(shop)
    ai = shop.get("ai_extracted", {}) or {}
    avg_price = extract_avg_price(ai.get("price_per_person", ""))

    # 1. 先看 primary_type
    if primary_type in TYPE_MAPPING:
        type_id = TYPE_MAPPING[primary_type]
    else:
        type_id = 2008  # fallback

    for keyword, override_type_id in NAME_OVERRIDES.items():
        if keyword.lower() in text:
            return override_type_id

    # 2. 高優先關鍵字覆寫：先解決最容易誤判的餐廳
    if _contains_any(text, BUFFET_KEYWORDS):
        return 2011
    if _contains_any(text, HOTPOT_KEYWORDS):
        return 2001
    if _contains_any(text, CHINESE_KEYWORDS):
        return 2008
    if _contains_any(text, FINE_DINING_KEYWORDS) and ((avg_price or 0) >= 1200 or "套餐" in text or "鐵板燒" in text):
        return 2011
    if _contains_any(text, YAKINIKU_KEYWORDS):
        return 2002
    if _contains_any(text, IZAKAYA_KEYWORDS):
        return 2003
    if _contains_any(text, KOREAN_KEYWORDS):
        return 2009
    if _contains_any(text, BRUNCH_KEYWORDS):
        return 2010
    if _contains_any(text, EUROPEAN_KEYWORDS):
        return 2007
    if _contains_any(text, CAFE_KEYWORDS):
        return 2012
    if _contains_any(text, JAPANESE_KEYWORDS):
        return 2004

    # 3. 店名補強
    name_lower = name.lower()
    if "pub" in name_lower or "bistro" in name_lower:
        return 2007
    if "ramen" in name_lower or "udon" in name_lower:
        return 2004

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


def reclassify_existing():
    raw_dir = Path("data/raw")
    latest = sorted(raw_dir.glob("places_extracted_*.json"))[-1]
    log.info("reading_for_reclassify", file=str(latest))
    data = json.loads(latest.read_text())
    shops = data["shops"]

    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
        autocommit=False,
    )

    updated = 0
    unchanged = 0

    try:
        with conn.cursor() as cur:
            for shop in shops:
                place_id = shop["place_id"]
                new_type_id = smart_type_id(shop)
                cur.execute(
                    "SELECT id, type_id, name FROM tb_shop WHERE place_id = %s AND source = 'google_places'",
                    (place_id,),
                )
                row = cur.fetchone()
                if not row:
                    continue
                shop_id, old_type_id, name = row
                if old_type_id == new_type_id:
                    unchanged += 1
                    continue
                cur.execute(
                    "UPDATE tb_shop SET type_id = %s WHERE id = %s",
                    (new_type_id, shop_id),
                )
                updated += 1
                log.info("reclassified", shop_id=shop_id, name=name, old_type_id=old_type_id, new_type_id=new_type_id)
            conn.commit()
    finally:
        conn.close()

    log.info("reclassify_done", updated=updated, unchanged=unchanged)


def refresh_metadata_existing():
    raw_dir = Path("data/raw")
    latest = sorted(raw_dir.glob("places_extracted_*.json"))[-1]
    log.info("reading_for_metadata_refresh", file=str(latest))
    data = json.loads(latest.read_text())
    shops = data["shops"]

    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
        autocommit=False,
    )

    refreshed = 0
    missing = 0

    try:
        with conn.cursor() as cur:
            for shop in shops:
                place_id = shop["place_id"]
                ai = shop.get("ai_extracted", {}) or {}

                cur.execute(
                    "SELECT id, name FROM tb_shop WHERE place_id = %s AND source = 'google_places'",
                    (place_id,),
                )
                row = cur.fetchone()
                if not row:
                    missing += 1
                    continue

                shop_id, name = row
                avg_price = extract_avg_price(ai.get("price_per_person", ""))
                score = int((shop.get("rating") or 0) * 10)

                cur.execute(
                    """
                    UPDATE tb_shop
                    SET avg_price = %s,
                        comments = %s,
                        score = %s,
                        district = %s,
                        price_range = %s,
                        update_time = NOW()
                    WHERE id = %s
                    """,
                    (
                        avg_price,
                        shop.get("user_rating_count", 0),
                        score,
                        shop.get("district"),
                        PRICE_LEVEL_MAP.get(shop.get("price_level")) if shop.get("price_level") else None,
                        shop_id,
                    ),
                )

                cur.execute(
                    "DELETE FROM tb_shop_ai_metadata WHERE shop_id = %s",
                    (shop_id,),
                )
                cur.execute(
                    """
                    INSERT INTO tb_shop_ai_metadata
                    (shop_id, ai_summary, highlight_review, signature_dishes,
                     atmosphere_tags, booking_difficulty, price_per_person,
                     phone, opening_hours, extracted_at, model_version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
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
                    ),
                )
                refreshed += 1
                log.info("metadata_refreshed", shop_id=shop_id, name=name)

            conn.commit()
    finally:
        conn.close()

    log.info("metadata_refresh_done", refreshed=refreshed, missing=missing)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reclassify", action="store_true", help="reclassify existing google_places shops by latest extracted json")
    parser.add_argument("--refresh-metadata", action="store_true", help="refresh existing google_places metadata by latest extracted json")
    args = parser.parse_args()

    if args.reclassify:
        reclassify_existing()
    elif args.refresh_metadata:
        refresh_metadata_existing()
    else:
        load()
