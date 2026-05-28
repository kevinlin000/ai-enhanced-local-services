import json
from datetime import datetime
from pathlib import Path
import os
import argparse

from pymongo import MongoClient
import pymysql
import structlog
from dotenv import load_dotenv


log = structlog.get_logger()
RAW_DIR = Path("data/raw")
VALUE_KEYWORDS = {
    "price": ["元", "$", "nt$", "價位", "價格", "套餐", "人均", "預算", "cp值", "划算", "值得"],
    "booking": ["訂位", "排隊", "候位", "現場", "熱門", "難訂", "預約", "包廂"],
    "service": ["服務", "店員", "態度", "桌邊", "上菜", "節奏", "親切", "專業"],
    "environment": ["環境", "氣氛", "裝潢", "座位", "空間", "包廂", "景觀", "舒適"],
    "dish": ["推薦", "必點", "招牌", "好吃", "口感", "湯頭", "肉", "蝦", "蟹", "甜點", "牛", "魚", "雞"],
    "negative": ["太鹹", "偏鹹", "太慢", "太久", "失望", "普通", "不推", "太貴", "擁擠", "吵", "退步", "冷掉"],
}

LODGING_KEYWORDS = [
    "住宿", "入住", "退房", "check in", "check-in", "check out", "check-out",
    "房間", "民宿", "飯店", "hotel", "room", "front desk", "櫃檯", "床", "枕頭",
    "洗衣機", "房務", "四人房", "雙人房", "住宿體驗", "睡眠品質",
]


def latest_extracted_file() -> Path:
    files = sorted(RAW_DIR.glob("places_extracted_*.json"))
    if not files:
        raise SystemExit("no places_extracted_*.json found")
    return files[-1]


def normalize_review(doc: dict) -> dict:
    description = doc.get("description") or {}
    text = ""
    if isinstance(description, dict):
        text = description.get("zh") or description.get("zh-TW") or description.get("en") or ""
        if not text and description:
            text = next((str(v) for v in description.values() if v), "")
    elif isinstance(description, str):
        text = description

    publish_time = doc.get("review_date") or doc.get("created_date")
    if hasattr(publish_time, "isoformat"):
        publish_time = publish_time.isoformat()
    return {
        "author": doc.get("author"),
        "rating": doc.get("rating"),
        "text": text,
        "publish_time": publish_time,
        "relative_time": None,
        "source": "mongo_reviews_scraper",
    }


def existing_review_key(review: dict) -> tuple:
    return (
        str(review.get("author") or "").strip(),
        str(review.get("text") or "").strip(),
    )


def review_text(review: dict) -> str:
    return str(review.get("text") or "").strip()


def is_likely_lodging_review(review: dict) -> bool:
    text = review_text(review).lower()
    if not text:
        return False
    hits = sum(1 for keyword in LODGING_KEYWORDS if keyword in text)
    return hits >= 2


def review_rating(review: dict) -> float:
    try:
        return float(review.get("rating") or 0)
    except Exception:
        return 0.0


def value_score(review: dict) -> int:
    text = review_text(review)
    if not text:
        return 0

    lower = text.lower()
    score = min(len(text), 600) // 40
    score += text.count("，") + text.count("。") + text.count("\n")

    for keywords in VALUE_KEYWORDS.values():
        if any(keyword in lower for keyword in keywords):
            score += 3

    if any(keyword in lower for keyword in VALUE_KEYWORDS["price"]):
        score += 4
    if any(keyword in lower for keyword in VALUE_KEYWORDS["booking"]):
        score += 4
    if any(keyword in lower for keyword in VALUE_KEYWORDS["negative"]):
        score += 2

    rating = review_rating(review)
    if rating and rating <= 3:
        score += 1

    return score


def select_best_reviews(mongo_reviews: list[dict], original_reviews: list[dict]) -> list[dict]:
    merged_reviews = []
    seen = set()

    def add_unique(review: dict):
        key = existing_review_key(review)
        if key in seen:
            return
        seen.add(key)
        merged_reviews.append(review)

    for review in mongo_reviews:
        if review_text(review) and not is_likely_lodging_review(review):
            add_unique(review)
    for review in original_reviews:
        if review_text(review) and not is_likely_lodging_review(review):
            add_unique(review)

    nonempty = merged_reviews
    scored = sorted(nonempty, key=lambda review: (value_score(review), review.get("publish_time") or ""), reverse=True)
    negative = [
        review for review in scored
        if review_rating(review) <= 3 and value_score(review) >= 8
    ][:4]

    picked = []
    picked_keys = set()
    for review in negative:
        key = existing_review_key(review)
        if key not in picked_keys:
            picked.append(review)
            picked_keys.add(key)

    for review in scored:
        key = existing_review_key(review)
        if key in picked_keys:
            continue
        picked.append(review)
        picked_keys.add(key)
        if len(picked) >= 20:
            break

    if len(picked) < 20:
        empties = [review for review in mongo_reviews if not review_text(review) and not is_likely_lodging_review(review)]
        for review in empties:
            key = existing_review_key(review)
            if key in picked_keys:
                continue
            picked.append(review)
            picked_keys.add(key)
            if len(picked) >= 20:
                break

    return picked[:20]


def load_shop_index() -> dict[str, dict]:
    load_dotenv(".env")
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, place_id
                FROM tb_shop
                WHERE place_id IS NOT NULL
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return {
        place_id: {"shop_id": shop_id, "name": name}
        for shop_id, name, place_id in rows
        if place_id
    }


def merge(input_file: str | None = None) -> Path:
    src = Path(input_file) if input_file else latest_extracted_file()
    log.info("reading", file=str(src))
    payload = json.loads(src.read_text())
    shops = payload["shops"]
    shop_index = load_shop_index()

    mongo = MongoClient("mongodb://localhost:27017")
    collection = mongo["bytebites_reviews"]["google_reviews"]

    updated = 0
    missing = 0
    total_reviews = 0

    try:
        for shop in shops:
            place_id = shop.get("place_id")
            match = shop_index.get(place_id)
            if match:
                shop["shop_id"] = match["shop_id"]
                shop["display_name"] = match["name"]

            shop_id = shop.get("shop_id")
            query = {"shop_id": shop_id} if shop_id else {"place_id": place_id}
            docs = list(collection.find(query).sort("created_date", -1))
            if not docs and place_id:
                docs = list(collection.find({"place_id": place_id}).sort("created_date", -1))

            if not docs:
                missing += 1
                continue

            normalized = [normalize_review(doc) for doc in docs]
            normalized = select_best_reviews(normalized, shop.get("reviews") or [])
            shop["reviews"] = normalized
            updated += 1
            total_reviews += len(normalized)
    finally:
        mongo.close()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RAW_DIR / f"places_merged_reviews_{ts}.json"
    out.write_text(
        json.dumps(
            {
                "timestamp": ts,
                "source_file": str(src.name),
                "total": len(shops),
                "updated": updated,
                "missing": missing,
                "total_reviews": total_reviews,
                "shops": shops,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    log.info("merged", out=str(out), updated=updated, missing=missing, total_reviews=total_reviews)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="source extracted json file")
    args = parser.parse_args()
    merge(args.input)
