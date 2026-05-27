import json
import re
import sqlite3
from html import unescape
from pathlib import Path

from pymongo import MongoClient


OUT = Path("/Users/kevinlintingwei/projects/ai-enhanced-local-services/web/data/shop-media.json")
REVIEW_DB = Path("/Users/kevinlintingwei/projects/ai-enhanced-local-services/tools/reviews-scraper/reviews.db")
LODGE_RE = re.compile(r"(住宿|旅館|民宿|旅社|房間|訂房|入住|hotel|room|bed|shower|bathroom)", re.I)
BAD_MEDIA_RE = re.compile(r"(菜單|menu|餐單|價目|帳單|發票|停車券|收據|單據|截圖|screenshot|qr|網址|browser|app|網站|網頁)", re.I)
PEOPLE_RE = re.compile(r"(自拍|合照|朋友|家人|兒子|女兒|小孩|孩子|寶寶|壽星|生日|男友|女友|老公|老婆|聚會照)", re.I)
LEFTOVER_RE = re.compile(r"(剩菜|吃剩|空盤|殘羹)", re.I)
NON_FOOD_SCENE_RE = re.compile(r"(大樓|建築|路口|街景|停車|門口|招牌|廁所|洗手間|洗手台|房卡)", re.I)
GOOD_FOOD_RE = re.compile(r"(好吃|美味|推薦|必點|招牌|湯|肉|海鮮|甜點|咖啡|蛋糕|炒飯|火鍋|牛|蝦|魚|麵|飯|蟹|龍蝦|烤鴨|叉燒|飲料|酒吧|bar|燒肉|壽喜燒|小籠包|拉麵|麻辣鍋|鵝肉|鐵板燒|沙拉|buffet)", re.I)
GOOD_SCENE_RE = re.compile(r"(環境|裝潢|空間|氣氛|座位|包廂|吧台|景觀|服務|店景|內裝)", re.I)


def normalize_url(url: str) -> str:
    value = unescape(url or "").strip()
    value = value.replace('"', "")
    value = re.sub(r"\s+", "", value)
    return value


def photo_score(url: str, text: str, rating: float | int | None) -> int:
    score = 0
    url = normalize_url(url)

    size = re.search(r"=w(\d+)-h(\d+)-", url)
    if size:
        width = int(size.group(1))
        height = int(size.group(2))
        if width > height:
            score += 8
        if width / max(height, 1) >= 1.3:
            score += 4
        if width >= 600:
            score += 2
        if height > width:
            score -= 3
        if width <= 220 or height <= 150:
            score -= 14

    if "grass-cs" in url:
        score -= 18
    if "gps-cs-s" in url:
        score += 10
    if "googleusercontent.com" in url and "gps-cs-s" not in url and "grass-cs" not in url:
        score += 2

    if GOOD_FOOD_RE.search(text):
        score += 10
    if GOOD_SCENE_RE.search(text):
        score += 6
    if not text:
        score -= 12
    if BAD_MEDIA_RE.search(text):
        score -= 18
    if PEOPLE_RE.search(text):
        score -= 10
    if LEFTOVER_RE.search(text):
        score -= 12
    if NON_FOOD_SCENE_RE.search(text) and not GOOD_FOOD_RE.search(text):
        score -= 8
    if LODGE_RE.search(text):
        score -= 40
    if rating and float(rating) >= 4:
        score += 2
    elif rating and float(rating) <= 2.5 and not GOOD_FOOD_RE.search(text):
        score -= 4

    return score


def build_shop_payload(urls_with_scores: list[tuple[str, int]], text_stat: tuple[int, int]) -> dict[str, object]:
    total, bad = text_stat
    if total and bad / total >= 0.4:
        return {"photoUrls": [], "coverUrl": None, "galleryUrls": []}

    best_by_url: dict[str, int] = {}
    for url, score in urls_with_scores:
        url = normalize_url(url)
        if not url:
            continue
        prev = best_by_url.get(url)
        if prev is None or score > prev:
            best_by_url[url] = score

    ranked = sorted(best_by_url.items(), key=lambda item: item[1], reverse=True)
    filtered = [url for url, score in ranked if score >= 0]
    if not filtered:
        filtered = [url for url, _score in ranked]

    cover = filtered[0] if filtered else None
    gallery = filtered[:8]
    return {
        "photoUrls": gallery,
        "coverUrl": cover,
        "galleryUrls": gallery,
    }


def load_overview_metadata() -> dict[str, dict]:
    if not REVIEW_DB.exists():
        return {}
    conn = sqlite3.connect(REVIEW_DB)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute("SELECT overview_metadata FROM places WHERE overview_metadata IS NOT NULL").fetchall()
        except sqlite3.OperationalError:
            return {}
        result: dict[str, dict] = {}
        for row in rows:
            raw = row["overview_metadata"]
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            shop_id = data.get("shop_id")
            if shop_id:
                result[str(shop_id)] = data
        return result
    finally:
        conn.close()


def main() -> None:
    client = MongoClient("mongodb://localhost:27017")
    try:
        collection = client["bytebites_reviews"]["google_reviews"]
        overview_by_shop = load_overview_metadata()
        docs = collection.find(
            {"shop_id": {"$exists": True}},
            {"shop_id": 1, "user_images": 1, "description": 1, "rating": 1, "_id": 0},
        )

        grouped: dict[str, list[tuple[str, int]]] = {}
        text_stats: dict[str, tuple[int, int]] = {}
        for doc in docs:
            shop_id = doc.get("shop_id")
            if not shop_id:
                continue
            key = str(shop_id)
            grouped.setdefault(key, [])
            text = doc.get("description")
            if isinstance(text, dict):
                text = " ".join(v or "" for v in text.values())
            text = str(text or "").strip()
            total, bad = text_stats.get(key, (0, 0))
            if text:
                total += 1
                if LODGE_RE.search(text):
                    bad += 1
            text_stats[key] = (total, bad)

            for url in doc.get("user_images") or []:
                if not url:
                    continue
                score = photo_score(url, text, doc.get("rating"))
                grouped[key].append((url, score))

        shops_payload = {}
        for shop_id, urls in grouped.items():
            shop_payload = build_shop_payload(urls, text_stats.get(shop_id, (0, 0)))
            overview = overview_by_shop.get(shop_id, {})
            overview_urls = [normalize_url(url) for url in overview.get("overview_photo_urls", []) if url]
            if overview_urls:
                overview_ranked = sorted(
                    ((url, photo_score(url, "", 5)) for url in overview_urls),
                    key=lambda item: item[1],
                    reverse=True,
                )
                preferred_overview = [url for url, score in overview_ranked if score >= -2]
                overview_gallery = preferred_overview or [url for url, _score in overview_ranked]
                merged = overview_gallery + [normalize_url(url) for url in shop_payload["galleryUrls"] if normalize_url(url) not in overview_gallery]
                shop_payload["coverUrl"] = merged[0] if merged else None
                shop_payload["galleryUrls"] = merged[:8]
                shop_payload["photoUrls"] = merged[:8]
            if overview:
                shop_payload["overview"] = {
                    key: value
                    for key, value in overview.items()
                    if key in {"price_overview", "price_report_count", "price_buckets", "popular_time", "visit_duration"}
                    and value not in (None, "", [], {})
                }
            shops_payload[shop_id] = shop_payload

        payload = {"shops": shops_payload}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"shops": len(payload["shops"]), "out": str(OUT)}, ensure_ascii=False))
    finally:
        client.close()


if __name__ == "__main__":
    main()
