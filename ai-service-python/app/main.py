import asyncio
import json
import logging
import re
import httpx
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo
from app import session_store
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from app.guardrail import GuardrailViolation, check_input, filter_output
from app.line_bot import (
    LINE_PHOTO_VERSION,
    best_shop_photo_url,
    build_line_flex_message,
    build_text_message,
    push_messages,
    reply_messages,
    show_loading_animation,
    verify_line_signature,
)
from google import genai
from google.genai.errors import ClientError, ServerError
from google.genai import types
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from prometheus_client import CONTENT_TYPE_LATEST, Counter as PromCounter, Histogram, generate_latest
from qdrant_client import QdrantClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class Settings(BaseSettings):
    java_backend_url: str = "http://localhost:8081"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "shops"
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_chat_model: str = "gemini-3.1-flash-lite"
    gemini_agent_model: str = "gemini-3.1-flash-lite"
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    line_signature_verify: bool = True
    line_reply_enabled: bool = False
    line_public_web_url: str = "http://localhost:3000"
    line_background_push_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
app = FastAPI(title="ByteBites AI Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
_gemini_client: genai.Client | None = None
_qdrant_client: QdrantClient | None = None
ai_requests = PromCounter("bytebites_ai_requests_total", "AI endpoint requests", ["endpoint"])
ai_tokens = PromCounter("bytebites_ai_tokens_total", "Gemini token usage", ["model", "kind"])
ai_latency = Histogram("bytebites_ai_latency_seconds", "AI endpoint latency", ["endpoint"])
logger = logging.getLogger("bytebites.ai")
LINE_RECOMMENDATION_TTL_SECONDS = 1800
LINE_LOCATION_TTL_SECONDS = 1800
_LINE_MEDIA_CACHE: dict | None = None
PREMIUM_HOTPOT_SUPPLEMENT_IDS = (10009,)


def taipei_today() -> date_cls:
    return datetime.now(ZoneInfo("Asia/Taipei")).date()

from app.taxonomy import CATEGORY_BY_TYPE_ID as _tax_map

TYPE_ID_TO_CATEGORY: dict[int, str] = {
    tid: cat["slug"] for tid, cat in _tax_map.items()
}

INTENT_HINTS = {
    "約會": {"約會", "浪漫", "紀念日", "慶生"},
    "商務": {"商務", "請客", "正式", "聚會"},
    "聚餐": {"聚餐", "朋友", "多人", "聚會"},
    "一人": {"一個人", "自己吃", "獨食", "單人"},
    "親子": {"親子", "小孩", "家庭"},
    "寵物友善": {"寵物", "毛孩"},
}

CATEGORY_HINTS = {
    "hotpot": {"火鍋", "鍋物", "麻辣鍋", "涮涮鍋", "shabu"},
    "yakiniku": {"燒肉", "烤肉", "yakiniku"},
    "izakaya": {"居酒屋", "串燒", "宵夜", "下酒", "下酒菜", "酒場", "酒吧", "精釀", "啤酒", "暢飲"},
    "japanese": {"日式", "日式料理", "日料", "日本料理", "壽司", "拉麵", "懷石"},
    "omakase": {"無菜單", "omakase"},
    "american": {"美式", "漢堡", "早午餐", "brunch", "牛排", "排餐", "steak"},
    "euro": {"義式", "法式", "義法", "歐陸", "義大利麵", "pasta", "pizza", "披薩"},
    "chinese": {"中菜", "中式", "台菜", "熱炒", "烤鴨", "港式", "粵菜", "川菜", "滬菜", "港點", "小籠包", "湯包", "上海湯包", "牛肉麵", "鵝肉"},
    "korean": {"韓式", "韓國料理", "豆腐鍋"},
    "vegetarian": {"素食", "蔬食", "全素", "蛋奶素", "vegan", "vegetarian"},
    "fine-dining": {"高級餐廳", "高檔餐廳", "fine dining", "精緻料理", "鐵板燒"},
    "cafe": {"咖啡", "咖啡廳", "下午茶", "甜點"},
}

CATEGORY_FALLBACK_KEYWORDS = {
    "hotpot": {"火鍋", "鍋物", "麻辣鍋", "酸菜白肉鍋", "涮涮屋", "涮涮鍋", "壽喜燒", "羊肉爐", "湯頭", "鴛鴦鍋", "鍋底"},
    "yakiniku": {"燒肉", "烤肉", "牛舌", "和牛燒肉"},
    "izakaya": {"居酒屋", "串燒", "烤串", "酒場", "酒吧", "精釀", "啤酒", "暢飲", "下酒菜"},
    "japanese": {"日式", "日式料理", "日料", "日本料理", "壽司", "生魚片", "拉麵", "天婦羅", "鰻魚飯"},
    "omakase": {"無菜單", "板前", "omakase"},
    "american": {"美式", "漢堡", "早午餐", "brunch", "牛排", "肋眼", "菲力", "排餐", "班尼迪克蛋"},
    "euro": {"義大利麵", "燉飯", "牛小排燉飯", "法式", "歐陸", "pasta", "pizza", "披薩"},
    "chinese": {"台菜", "熱炒", "烤鴨", "粵菜", "川菜", "滬菜", "港點", "中菜", "小籠包", "湯包", "上海湯包", "牛肉麵", "鵝肉"},
    "korean": {"韓式", "豆腐鍋", "炸雞", "石鍋拌飯"},
    "vegetarian": {"素食", "蔬食", "全素", "蛋奶素", "vegan", "vegetarian"},
    "fine-dining": {"fine dining", "高級餐廳", "高檔餐廳", "套餐", "品酒", "鐵板燒"},
    "cafe": {"咖啡", "拿鐵", "手沖", "甜點", "下午茶", "蛋糕"},
}

CATEGORY_ALIASES = {
    "brunch": "american",
    "steakhouse": "american",
    "european": "euro",
    "cafe-premium": "cafe",
}

SUPPORTED_CATEGORY_SLUGS = set(CATEGORY_FALLBACK_KEYWORDS)


def _canonical_category_slug(slug: str | None) -> str:
    normalized = str(slug or "").strip().lower()
    return CATEGORY_ALIASES.get(normalized, normalized)

STATION_HINTS = {
    "中山國小站": {"中山國小", "中山國小站"},
    "中山站": {"中山", "中山站"},
    "雙連站": {"雙連", "雙連站"},
    "行天宮站": {"行天宮", "行天宮站"},
    "市政府站": {"市政府", "市政府站"},
    "信義安和站": {"信義安和", "信義安和站", "大安站"},
    "象山站": {"象山", "象山站"},
}

DISTRICT_HINTS = {
    "中山": {"中山區", "中山"},
    "信義": {"信義區", "信義"},
    "大安": {"大安區", "大安"},
    "松山": {"松山區", "松山"},
    "中正": {"中正區", "中正"},
    "士林": {"士林區", "士林"},
    "內湖": {"內湖區", "內湖"},
    "南港": {"南港區", "南港"},
    "文山": {"文山區", "文山", "木柵", "景美", "萬芳"},
    "大同": {"大同區", "大同"},
    "萬華": {"萬華區", "萬華", "西門"},
    "北投": {"北投區", "北投", "天母"},
}

STATION_NEIGHBORHOODS = {
    "中山國小": {"中山國小": 1.0, "行天宮": 0.55, "雙連": 0.45, "中山": 0.35},
    "中山": {"中山": 1.0, "雙連": 0.75, "中山國小": 0.45},
    "雙連": {"雙連": 1.0, "中山": 0.75, "中山國小": 0.45},
    "市政府": {"市政府": 1.0, "信義安和": 0.55, "象山": 0.45},
    "信義安和": {"信義安和": 1.0, "市政府": 0.55, "象山": 0.35},
    "行天宮": {"行天宮": 1.0, "中山國小": 0.45, "雙連": 0.3},
    "象山": {"象山": 1.0, "市政府": 0.45, "信義安和": 0.35},
}

LUXURY_HINTS = {"高級", "精緻", "約會大餐", "請客", "慶生", "高檔", "高價"}
HOTPOT_STRONG_HINTS = {"火鍋", "鍋物", "麻辣鍋", "酸菜白肉鍋", "涮涮鍋", "涮涮屋", "壽喜燒", "羊肉爐", "鴛鴦鍋"}
HOTPOT_BLOCK_HINTS = {"拉麵", "鐵板燒", "韓式烤肉", "燒肉", "串燒"}


def get_gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        if not settings.gemini_api_key:
            raise HTTPException(503, "GEMINI_API_KEY not configured")
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def get_qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=settings.qdrant_url)
    return _qdrant_client


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=3, min=10, max=120),
    retry=retry_if_exception_type((ClientError, ServerError)),
)
def generate(model: str, contents, config=None):
    response = get_gemini().models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    usage = getattr(response, "usage_metadata", None)
    if usage:
        ai_tokens.labels(model=model, kind="prompt").inc(usage.prompt_token_count or 0)
        ai_tokens.labels(model=model, kind="output").inc(usage.candidates_token_count or 0)
    return response


def call_llm(prompt: str) -> str:
    try:
        response = generate(settings.gemini_chat_model, prompt)
    except ClientError as exc:
        if "not found" not in str(exc).lower() and "unsupported" not in str(exc).lower():
            raise
        response = generate("gemini-1.5-flash", prompt)
    return response.text


def _parse_json_list(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, list):
                return [str(item) for item in loaded if item]
        except Exception:
            return [raw]
    return []


def _payload_text(payload: dict) -> str:
    parts: list[str] = [
        payload.get("name", ""),
        payload.get("district", ""),
        payload.get("mrt_station", ""),
        payload.get("category", ""),
        payload.get("ai_summary", ""),
        payload.get("booking_difficulty", ""),
        payload.get("price_per_person", ""),
    ]
    parts.extend(_parse_json_list(payload.get("signature_dishes")))
    parts.extend(_parse_json_list(payload.get("atmosphere_tags")))
    return " ".join(str(part) for part in parts if part).lower()


def _extract_query_constraints(query: str) -> dict:
    query_lower = query.lower()
    stations = []
    for canonical, keywords in STATION_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            station = canonical.replace("站", "")
            if station not in stations:
                stations.append(station)
    # Longer station names should dominate shorter substring matches.
    # Example: "中山國小" must not also become the broader "中山" station.
    for station in list(stations):
        if any(station != other and station in other for other in stations):
            stations.remove(station)

    districts = []
    for canonical, keywords in DISTRICT_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            districts.append(canonical)

    categories = []
    for category, keywords in CATEGORY_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            canonical_category = _canonical_category_slug(category)
            if canonical_category not in categories:
                categories.append(canonical_category)

    wants_hot_seat = any(keyword in query_lower for keyword in ("hot seat", "熱座", "搶位", "限量", "秒殺"))
    wants_nearby = any(keyword in query_lower for keyword in ("附近", "nearby"))
    wants_luxury = any(keyword in query_lower for keyword in LUXURY_HINTS)

    has_primary_food_category = any(category != "fine-dining" for category in categories)
    if wants_luxury and has_primary_food_category:
        categories = [category for category in categories if category != "fine-dining"]
    elif wants_luxury and not categories:
        categories.append("fine-dining")

    return {
        "stations": stations,
        "districts": districts,
        "categories": categories,
        "wants_hot_seat": wants_hot_seat,
        "wants_nearby": wants_nearby,
        "wants_luxury": wants_luxury,
    }


def _authoritative_category_slug(payload: dict) -> str:
    explicit_slug = _canonical_category_slug(payload.get("category_slug"))
    if explicit_slug:
        return explicit_slug

    category = str(payload.get("category") or "").lower()
    if "火鍋" in category:
        return "hotpot"
    if "燒肉" in category:
        return "yakiniku"
    if "居酒屋" in category:
        return "izakaya"
    if "日式料理" in category:
        return "japanese"
    if "無菜單" in category:
        return "omakase"
    if "牛排" in category:
        return "american"
    if "義法" in category:
        return "euro"
    if "中式" in category:
        return "chinese"
    if "韓式" in category:
        return "korean"
    if "素食" in category or "蔬食" in category:
        return "vegetarian"
    if "brunch" in category or "美式" in category:
        return "american"
    if "高級" in category:
        return "fine-dining"
    if "咖啡" in category:
        return "cafe"
    return ""


def _category_slug_from_payload(payload: dict) -> str:
    authoritative_slug = _authoritative_category_slug(payload)
    if authoritative_slug:
        return authoritative_slug

    text = _payload_text(payload)
    if any(keyword.lower() in text for keyword in {"鐵板燒", "fine dining", "高級餐廳", "高檔餐廳"}):
        return "fine-dining"
    if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["hotpot"]):
        return "hotpot"
    if any(keyword.lower() in text for keyword in {"拉麵", "壽司", "生魚片", "鰻魚飯", "天婦羅"}):
        return "japanese"
    if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["yakiniku"]):
        return "yakiniku"
    if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["izakaya"]):
        return "izakaya"
    return ""


def _semantic_category_slug(payload: dict) -> str:
    authoritative_slug = _authoritative_category_slug(payload)
    if authoritative_slug:
        return authoritative_slug

    text = _payload_text(payload)
    if any(keyword.lower() in text for keyword in {"鐵板燒", "fine dining", "高級餐廳", "高檔餐廳"}):
        return "fine-dining"
    if _has_hotpot_semantics(payload):
        return "hotpot"
    if any(keyword.lower() in text for keyword in {"拉麵", "壽司", "生魚片", "鰻魚飯", "天婦羅"}):
        return "japanese"
    if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["yakiniku"]):
        return "yakiniku"
    if any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["izakaya"]):
        return "izakaya"
    return _category_slug_from_payload(payload)


def _station_proximity_score(constraints: dict, payload: dict) -> float:
    mrt_station = str(payload.get("mrt_station") or "")
    if not constraints["stations"] or not mrt_station:
        return 0.0

    score = 0.0
    for target in constraints["stations"]:
        score = max(score, STATION_NEIGHBORHOODS.get(target, {}).get(mrt_station, 0.0))
    return score


def _normalize_district_name(value: str | None) -> str:
    return str(value or "").strip().lower().removesuffix("區")


def _district_matches(constraints: dict, payload: dict) -> bool:
    district = _normalize_district_name(payload.get("district"))
    return bool(district) and any(
        _normalize_district_name(target) == district
        for target in constraints["districts"]
    )


def _has_hotpot_semantics(payload: dict) -> bool:
    text = _payload_text(payload)
    has_strong_hint = any(keyword.lower() in text for keyword in HOTPOT_STRONG_HINTS)
    has_block_hint = any(keyword.lower() in text for keyword in HOTPOT_BLOCK_HINTS)
    if has_strong_hint:
        return True
    if has_block_hint:
        return False
    return any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["hotpot"])


def _premium_hotpot_key(constraints: dict, hit: dict) -> tuple[int, int, int, float, int, int, int, float]:
    avg_price = hit.get("avg_price") or 0
    tags = set(hit.get("atmosphere_tags") or [])
    text = _payload_text(hit)
    station_score = _station_proximity_score(constraints, hit)
    district_match = 1 if _district_matches(constraints, hit) else 0
    has_premium_cues = 1 if any(
        keyword in text
        for keyword in (
            "和牛",
            "a5",
            "套餐",
            "無菜單",
            "松葉蟹",
            "龍蝦",
            "精緻",
            "頂級",
            "高品質",
            "涮涮屋",
            "杏仁豆腐",
            "海鮮套餐",
        )
    ) else 0
    premium_price = 1 if avg_price >= 1000 else 0
    mid_price = 1 if avg_price >= 800 else 0
    date_night = 1 if ({"約會", "商務"} & tags) else 0
    nearby_bucket = 0
    if constraints["wants_nearby"] or constraints["stations"]:
        if station_score >= 1.0:
            nearby_bucket = 3
        elif station_score >= 0.7:
            nearby_bucket = 2
        elif district_match:
            nearby_bucket = 1
    return (
        1 if _semantic_category_slug(hit) == "hotpot" else 0,
        nearby_bucket,
        premium_price,
        station_score,
        district_match,
        has_premium_cues,
        date_night or mid_price,
        hit["rerank_score"],
    )


def _metadata_bonus(query: str, payload: dict) -> float:
    query_lower = query.lower()
    constraints = _extract_query_constraints(query)
    bonus = 0.0
    district = str(payload.get("district") or "").lower()
    mrt_station = str(payload.get("mrt_station") or "").lower()
    category = str(payload.get("category") or "").lower()
    category_slug = _semantic_category_slug(payload)
    booking_difficulty = str(payload.get("booking_difficulty") or "").lower()
    price_per_person = str(payload.get("price_per_person") or "").lower()
    avg_price = payload.get("avg_price") or 0
    tags = [tag.lower() for tag in _parse_json_list(payload.get("atmosphere_tags"))]
    dishes = [dish.lower() for dish in _parse_json_list(payload.get("signature_dishes"))]
    text = _payload_text(payload)
    fallback_keywords = CATEGORY_FALLBACK_KEYWORDS.get(category_slug, set())
    category_semantic_match = bool(
        category_slug in constraints["categories"]
        or any(keyword.lower() in text for keyword in fallback_keywords)
    )

    if district and district in query_lower:
        bonus += 0.18
    if mrt_station and mrt_station in query_lower:
        bonus += 0.18
    if category and category in query_lower:
        bonus += 0.14

    if constraints["districts"]:
        if _district_matches(constraints, payload):
            bonus += 0.42
        else:
            bonus -= 0.18

    if constraints["stations"]:
        best_station_score = 0.0
        for target in constraints["stations"]:
            neighborhood = STATION_NEIGHBORHOODS.get(target, {})
            best_station_score = max(best_station_score, neighborhood.get(mrt_station, 0.0))

        if best_station_score >= 1.0:
            bonus += 0.5
        elif best_station_score >= 0.7:
            bonus += 0.28 * best_station_score
        elif best_station_score > 0:
            bonus += 0.12 * best_station_score
        elif constraints["wants_nearby"] and mrt_station:
            bonus -= 0.32
        elif constraints["wants_nearby"]:
            bonus -= 0.18

    if constraints["categories"]:
        if category_slug in constraints["categories"]:
            bonus += 0.5
        elif any(
            keyword.lower() in text
            for requested in constraints["categories"]
            for keyword in CATEGORY_FALLBACK_KEYWORDS.get(requested, set())
        ):
            bonus += 0.2
        else:
            bonus -= 0.55

    for canonical, keywords in INTENT_HINTS.items():
        if any(keyword in query_lower for keyword in keywords):
            if canonical.lower() in tags or canonical.lower() in text:
                bonus += 0.18

    if any(keyword in query_lower for keyword in ("便宜", "平價", "cp值", "學生")):
        if avg_price and avg_price <= 300:
            bonus += 0.15
    if any(keyword in query_lower for keyword in LUXURY_HINTS):
        if avg_price and avg_price >= 800:
            bonus += 0.15
        if category_slug == "fine-dining":
            bonus += 0.18
        if "困難" in booking_difficulty or "提前" in booking_difficulty:
            bonus += 0.1
        if "約會" in tags or "商務" in tags:
            bonus += 0.12
        if avg_price and avg_price < 500:
            bonus -= 0.3
        elif avg_price and avg_price < 800:
            bonus -= 0.12
        elif not avg_price and "未提及" in price_per_person:
            bonus -= 0.08
    if any(keyword in query_lower for keyword in ("難訂", "熱門", "搶位")):
        if "困難" in booking_difficulty:
            bonus += 0.12
    if any(keyword in query_lower for keyword in ("套餐", "折扣", "優惠", "hot seat", "熱座", "搶位")):
        if payload.get("hot_seat_vouchers"):
            bonus += 0.35
        elif constraints["wants_hot_seat"]:
            bonus -= 0.25

    for dish in dishes[:5]:
        if dish and dish in query_lower:
            bonus += 0.12
    if price_per_person and any(token in query_lower for token in ("價位", "預算", "人均")):
        bonus += 0.08

    return bonus


def _fallback_keyword_score(query: str, payload: dict) -> float:
    query_lower = query.lower()
    text = _payload_text(payload)
    score = 0.0

    for category, keywords in CATEGORY_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            if _semantic_category_slug(payload) == category:
                score += 0.35
            elif any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS.get(category, set())):
                score += 0.18

    for keywords in INTENT_HINTS.values():
        if any(keyword in query_lower for keyword in keywords):
            if any(keyword.lower() in text for keyword in keywords):
                score += 0.12

    for canonical, keywords in STATION_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            if canonical.replace("站", "").lower() == str(payload.get("mrt_station") or "").lower():
                score += 0.35

    for canonical, keywords in DISTRICT_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            if canonical.lower() == str(payload.get("district") or "").lower():
                score += 0.28

    if any(keyword in query_lower for keyword in ("hot seat", "熱座", "搶位", "限量", "秒殺")) and payload.get("hot_seat_vouchers"):
        score += 0.25

    return score


async def _fetch_all_shops_fallback() -> list[dict]:
    shops = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        category_resp = await client.get(f"{settings.java_backend_url}/api/category/list")
        categories = category_resp.json().get("data", []) if category_resp.status_code == 200 else []

        for category in categories:
            slug = category.get("slug")
            if not slug:
                continue
            resp = await client.get(
                f"{settings.java_backend_url}/api/category/{slug}/shops",
                params={"page": 1, "size": 50},
            )
            if resp.status_code == 200:
                shops.extend(resp.json().get("data", []))

        deduped: dict[int, dict] = {}
        for shop in shops:
            deduped[shop["id"]] = shop

        enriched = []
        for shop in deduped.values():
            try:
                meta_resp = await client.get(f"{settings.java_backend_url}/api/shop/{shop['id']}/ai-metadata")
                metadata = meta_resp.json().get("data") if meta_resp.status_code == 200 else None
            except Exception:
                metadata = None

            enriched.append(
                {
                    "shop_id": shop["id"],
                    "name": shop.get("name"),
                    "district": shop.get("district"),
                    "mrt_station": shop.get("mrtStation"),
                    "score": 0.0,
                    "category": TYPE_ID_TO_CATEGORY.get(shop.get("typeId")),
                    "category_slug": TYPE_ID_TO_CATEGORY.get(shop.get("typeId")),
                    "avg_price": shop.get("avgPrice"),
                    "ai_summary": metadata.get("aiSummary") if metadata else None,
                    "signature_dishes": _parse_json_list(metadata.get("signatureDishes")) if metadata else [],
                    "atmosphere_tags": _parse_json_list(metadata.get("atmosphereTags")) if metadata else [],
                    "booking_difficulty": metadata.get("bookingDifficulty") if metadata else None,
                    "price_per_person": metadata.get("pricePerPerson") if metadata else None,
                }
            )
    return enriched


def _java_shop_to_search_hit(shop: dict, metadata: dict | None = None) -> dict:
    metadata = metadata or {}
    type_id = shop.get("typeId")
    payload = {
        "shop_id": shop.get("id"),
        "name": shop.get("name"),
        "district": shop.get("district") or shop.get("area"),
        "mrt_station": shop.get("mrtStation"),
        "score": 0.0,
        "category": TYPE_ID_TO_CATEGORY.get(type_id),
        "category_slug": TYPE_ID_TO_CATEGORY.get(type_id),
        "avg_price": shop.get("avgPrice"),
        "ai_summary": metadata.get("aiSummary"),
        "signature_dishes": _parse_json_list(metadata.get("signatureDishes")),
        "atmosphere_tags": _parse_json_list(metadata.get("atmosphereTags")),
        "booking_difficulty": metadata.get("bookingDifficulty"),
        "price_per_person": metadata.get("pricePerPerson"),
        "hot_seat_vouchers": [],
    }
    if not payload["category_slug"]:
        inferred = _category_slug_from_payload(payload)
        payload["category"] = inferred
        payload["category_slug"] = inferred
    return payload


async def _premium_hotpot_supplements(constraints: dict, existing_ids: set[int]) -> list[dict]:
    if "hotpot" not in constraints["categories"] or not constraints.get("wants_luxury"):
        return []

    supplements: list[dict] = []
    for shop_id in PREMIUM_HOTPOT_SUPPLEMENT_IDS:
        if shop_id in existing_ids:
            continue
        shop = await _fetch_java_shop(shop_id)
        if not shop:
            continue
        hit = _java_shop_to_search_hit(shop, await _fetch_java_ai_metadata(shop_id))
        if not _has_hotpot_semantics(hit):
            continue
        if constraints["districts"] and not _district_matches(constraints, hit):
            continue
        hit["ai_summary"] = hit.get("ai_summary") or "精緻涮涮屋路線，主打高品質食材、細緻服務與較正式的聚餐氛圍。"
        hit["signature_dishes"] = hit.get("signature_dishes") or ["頂級肉品", "海鮮套餐", "杏仁豆腐"]
        hit["atmosphere_tags"] = hit.get("atmosphere_tags") or ["精緻", "商務", "約會"]
        hit["price_per_person"] = hit.get("price_per_person") or f"NT$ {hit.get('avg_price')}"
        supplements.append(hit)
    return supplements


async def _semantic_hits(query: str, top_k: int) -> list[dict]:
    gemini = get_gemini()
    emb_resp = gemini.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    raw_hits = []
    try:
        qdrant = get_qdrant()
        results = qdrant.query_points(
            collection_name=settings.qdrant_collection,
            query=emb_resp.embeddings[0].values,
            limit=max(top_k * 12, 60),
        ).points

        for result in results:
            payload = result.payload
            raw_hits.append(
                {
                    "shop_id": payload.get("shop_id"),
                    "name": payload.get("name"),
                    "district": payload.get("district"),
                    "mrt_station": payload.get("mrt_station"),
                    "score": float(result.score),
                    "category": payload.get("category"),
                    "category_slug": payload.get("category_slug"),
                    "type_id": payload.get("type_id"),
                    "avg_price": payload.get("avg_price"),
                    "ai_summary": payload.get("ai_summary"),
                    "signature_dishes": _parse_json_list(payload.get("signature_dishes")),
                    "atmosphere_tags": _parse_json_list(payload.get("atmosphere_tags")),
                    "booking_difficulty": payload.get("booking_difficulty"),
                    "price_per_person": payload.get("price_per_person"),
                }
            )
    except Exception as exc:
        logger.warning("qdrant_unavailable_fallback query=%r error=%s", query, exc)
        raw_hits = await _fetch_all_shops_fallback()

    constraints = _extract_query_constraints(query)
    supplement_hits = await _premium_hotpot_supplements(
        constraints,
        {int(hit["shop_id"]) for hit in raw_hits if hit.get("shop_id")},
    )
    if supplement_hits:
        raw_hits.extend(supplement_hits)

    shop_ids = [hit["shop_id"] for hit in raw_hits if hit["shop_id"]]
    voucher_map = await _fetch_hot_seat_vouchers(shop_ids)
    for hit in raw_hits:
        hit["hot_seat_vouchers"] = voucher_map.get(hit["shop_id"], [])
        hit["rerank_score"] = hit["score"] + _metadata_bonus(query, hit) + _fallback_keyword_score(query, hit)

    if constraints["categories"] or constraints["stations"] or constraints["districts"] or constraints["wants_hot_seat"]:
        logger.warning(
            "search_constraints query=%r constraints=%s",
            query,
            constraints,
        )
        for hit in raw_hits[:8]:
            logger.warning(
                "search_candidate_pre_sort name=%r category=%r mrt=%r district=%r base=%.4f rerank=%.4f hot_seat=%s",
                hit.get("name"),
                _category_slug_from_payload(hit),
                hit.get("mrt_station"),
                hit.get("district"),
                hit.get("score"),
                hit.get("rerank_score"),
                bool(hit.get("hot_seat_vouchers")),
            )
    raw_hits.sort(key=lambda hit: hit["rerank_score"], reverse=True)

    if constraints["categories"]:
        def category_match(hit: dict) -> bool:
            slug = _semantic_category_slug(hit)
            if slug in constraints["categories"]:
                return True
            text = _payload_text(hit)
            return any(
                keyword.lower() in text
                for requested in constraints["categories"]
                for keyword in CATEGORY_FALLBACK_KEYWORDS.get(requested, set())
            )

        matching = [
            hit for hit in raw_hits
            if category_match(hit)
        ]
        non_matching = [
            hit for hit in raw_hits
            if not category_match(hit)
        ]
        if matching:
            raw_hits = matching + non_matching
            logger.warning(
                "search_category_partition query=%r matching=%s",
                query,
                [hit.get("name") for hit in matching[:8]],
            )

    # Explicit business rule:
    # For queries like "高級火鍋", "火鍋" is the primary constraint.
    # Only compare luxury signals after the candidate is already a hotpot-like shop.
    requested_hotpot = "hotpot" in constraints["categories"]
    requested_luxury = constraints.get("wants_luxury", False)
    if requested_hotpot and requested_luxury:
        def is_hotpot_candidate(hit: dict) -> bool:
            category_slug = _semantic_category_slug(hit)
            text = _payload_text(hit)
            if category_slug == "hotpot" and not any(keyword.lower() in text for keyword in HOTPOT_BLOCK_HINTS):
                return True
            return _has_hotpot_semantics(hit)

        hotpot_hits = [hit for hit in raw_hits if is_hotpot_candidate(hit)]
        other_hits = [hit for hit in raw_hits if not is_hotpot_candidate(hit)]
        if hotpot_hits:
            hotpot_hits.sort(key=lambda hit: _premium_hotpot_key(constraints, hit), reverse=True)
            other_hits.sort(key=lambda hit: hit["rerank_score"], reverse=True)
            raw_hits = hotpot_hits + other_hits
            logger.warning(
                "search_hotpot_partition query=%r hotpot=%s others=%s",
                query,
                [hit.get("name") for hit in hotpot_hits[:8]],
                [hit.get("name") for hit in other_hits[:8]],
            )

    if any(keyword in query.lower() for keyword in LUXURY_HINTS):
        def luxury_score(hit: dict) -> tuple[int, int, int, float, int, int, int, float]:
            if requested_hotpot:
                return _premium_hotpot_key(constraints, hit)

            avg_price = hit.get("avg_price") or 0
            tags = set(hit.get("atmosphere_tags") or [])
            station_score = _station_proximity_score(constraints, hit)
            district_match = 1 if _district_matches(constraints, hit) else 0
            return (
                0,
                1 if avg_price >= 1000 else 0,
                0,
                station_score,
                district_match,
                1 if ({"約會", "商務"} & tags) else 0,
                1 if avg_price >= 800 else 0,
                hit["rerank_score"],
            )

        raw_hits.sort(
            key=lambda hit: (luxury_score(hit), hit["rerank_score"]),
            reverse=True,
        )
        logger.warning(
            "search_luxury_sorted query=%r ranked=%s",
            query,
            [
                {
                    "name": hit.get("name"),
                    "category": _semantic_category_slug(hit),
                    "luxury": luxury_score(hit),
                    "rerank": round(hit.get("rerank_score", 0.0), 4),
                }
                for hit in raw_hits[:8]
            ],
        )

    if requested_hotpot and constraints["wants_nearby"]:
        def is_hotpot_like(hit: dict) -> bool:
            return _semantic_category_slug(hit) == "hotpot" or _has_hotpot_semantics(hit)

        def is_nearby_hit(hit: dict) -> bool:
            return _station_proximity_score(constraints, hit) > 0 or _district_matches(constraints, hit)

        near_hotpot_hits = [hit for hit in raw_hits if is_hotpot_like(hit) and is_nearby_hit(hit)]
        far_hotpot_hits = [hit for hit in raw_hits if is_hotpot_like(hit) and not is_nearby_hit(hit)]
        other_hits = [hit for hit in raw_hits if not is_hotpot_like(hit)]
        if near_hotpot_hits:
            raw_hits = near_hotpot_hits + far_hotpot_hits + other_hits
            logger.warning(
                "search_nearby_partition query=%r near_hotpot=%s far_hotpot=%s others=%s",
                query,
                [hit.get("name") for hit in near_hotpot_hits[:8]],
                [hit.get("name") for hit in far_hotpot_hits[:8]],
                [hit.get("name") for hit in other_hits[:8]],
            )

    if constraints["wants_hot_seat"]:
        hot_hits = [hit for hit in raw_hits if hit.get("hot_seat_vouchers")]
        cold_hits = [hit for hit in raw_hits if not hit.get("hot_seat_vouchers")]
        raw_hits = hot_hits + cold_hits
        logger.warning(
            "search_hot_seat_sorted query=%r hot=%s cold=%s",
            query,
            [hit.get("name") for hit in hot_hits[:8]],
            [hit.get("name") for hit in cold_hits[:8]],
        )

    if constraints["categories"] or constraints["stations"] or constraints["districts"] or constraints["wants_hot_seat"]:
        logger.warning(
            "search_final_rank query=%r ranked=%s",
            query,
            [
                {
                    "name": hit.get("name"),
                    "category": _semantic_category_slug(hit),
                    "mrt": hit.get("mrt_station"),
                    "rerank": round(hit.get("rerank_score", 0.0), 4),
                }
                for hit in raw_hits[:8]
            ],
        )

    # Hard nearby filter: when query has "附近/nearby" + explicit station or district,
    # force candidates from that area into top slots.  Only fill from outside the area
    # if strict matches are fewer than 5.
    if constraints["wants_nearby"] and (constraints["stations"] or constraints["districts"]):
        def _is_strict_nearby(hit: dict) -> bool:
            mrt = str(hit.get("mrt_station") or "").lower()
            station_match = _station_proximity_score(constraints, hit) > 0 or any(
                s.lower() in mrt for s in constraints["stations"]
            )
            district_match = _district_matches(constraints, hit)
            return station_match or district_match

        strict_nearby = [h for h in raw_hits if _is_strict_nearby(h)]
        loose_nearby  = [h for h in raw_hits if not _is_strict_nearby(h)]

        MIN_STRICT = 5
        if len(strict_nearby) >= MIN_STRICT:
            raw_hits = strict_nearby
        else:
            raw_hits = strict_nearby + loose_nearby[: max(0, MIN_STRICT + 3 - len(strict_nearby))]

        logger.warning(
            "search_strict_nearby_filter query=%r strict=%s loose_added=%s",
            query,
            [h.get("name") for h in strict_nearby[:8]],
            [h.get("name") for h in loose_nearby[: max(0, MIN_STRICT + 3 - len(strict_nearby))]],
        )

    if constraints["categories"]:
        authoritative_category = [
            hit for hit in raw_hits
            if _authoritative_category_slug(hit) in constraints["categories"]
        ]
        legacy_semantic_category = [
            hit for hit in raw_hits
            if not _authoritative_category_slug(hit)
            and _semantic_category_slug(hit) in constraints["categories"]
        ]
        text_category = [
            hit for hit in raw_hits
            if not _authoritative_category_slug(hit)
            if any(
                keyword.lower() in _payload_text(hit)
                for requested in constraints["categories"]
                for keyword in CATEGORY_FALLBACK_KEYWORDS.get(requested, set())
            )
        ]
        # Prefer authoritative taxonomy. Text fallback only exists for legacy
        # payloads that do not yet carry category_slug.
        strict_category = authoritative_category or legacy_semantic_category or text_category
        raw_hits = strict_category
        logger.warning(
            "search_strict_category_filter query=%r categories=%s authoritative=%s legacy=%s text=%s strict=%s",
            query,
            constraints["categories"],
            [hit.get("name") for hit in authoritative_category[:8]],
            [hit.get("name") for hit in legacy_semantic_category[:8]],
            [hit.get("name") for hit in text_category[:8]],
            [hit.get("name") for hit in strict_category[:8]],
        )

    if constraints["districts"]:
        strict_district = [
            hit for hit in raw_hits
            if _district_matches(constraints, hit)
        ]
        raw_hits = strict_district
        logger.warning(
            "search_strict_district_filter query=%r districts=%s strict=%s",
            query,
            constraints["districts"],
            [hit.get("name") for hit in strict_district[:8]],
        )

    if constraints["stations"]:
        strict_station = [
            hit for hit in raw_hits
            if _station_proximity_score(constraints, hit) > 0
            or any(target.lower() in str(hit.get("mrt_station") or "").lower() for target in constraints["stations"])
        ]
        if strict_station or not constraints["districts"]:
            raw_hits = strict_station
        logger.warning(
            "search_strict_station_filter query=%r stations=%s strict=%s",
            query,
            constraints["stations"],
            [hit.get("name") for hit in strict_station[:8]],
        )

    return raw_hits[:top_k]


async def _fetch_hot_seat_vouchers(shop_ids: list[int]) -> dict[int, list]:
    """Return {shop_id: [{id, title, pay_value, actual_value, stock}]}. N+1 ok for demo."""
    out: dict[int, list] = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for sid in shop_ids:
            try:
                r = await client.get(f"{settings.java_backend_url}/api/shop/{sid}/hot-seat-vouchers")
                out[sid] = r.json().get("data", []) if r.status_code == 200 else []
            except Exception:
                out[sid] = []
    return out


async def tool_search_by_mrt(station: str, radius: int = 500) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            f"{settings.java_backend_url}/api/shop/nearby-mrt/{station}",
            params={"radius": radius},
        )
        return {"shops": response.json().get("data", [])[:5]}


async def tool_semantic_search(query: str) -> dict:
    hits = await _semantic_hits(query, top_k=5)
    return {"shops": hits}


async def tool_create_hot_seat_order(voucher_id: int) -> dict:
    """Call Java seckill endpoint with X-Demo-Mode header."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{settings.java_backend_url}/voucher-order/seckill/{voucher_id}",
            headers={"X-Demo-Mode": "true"},
        )
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}", "body": r.text[:200]}
    data = r.json()
    if not data.get("success"):
        return {"success": False, "error": data.get("errorMsg", "unknown")}
    return {
        "success": True,
        "voucher_order_id": data.get("data"),
        "message": "已為您搶到 Hot Seat 名額，可在「我的訂單」查看",
    }


async def tool_create_booking(
    shop_id: int,
    people: int,
    date: str = None,
    time: str = None,
    table_type: str = "normal",
    idempotency_key: str | None = None,
) -> dict:
    """建立訂位記錄，回 bookingCode + needsDeposit + depositTotal。"""
    today = taipei_today()
    tomorrow = (today + timedelta(days=1)).isoformat()

    if not date:
        date = tomorrow
    else:
        try:
            requested_date = date_cls.fromisoformat(date)
            if requested_date <= today:
                return {
                    "success": False,
                    "error": "今天不可訂位，最早可訂明天。請確認是否改訂明天或其他日期。",
                }
        except ValueError:
            return {"success": False, "error": "date 格式需為 YYYY-MM-DD"}
    if not time:
        time = "19:00"

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{settings.java_backend_url}/api/booking/reserve",
            headers={"X-Demo-Mode": "true"},
            json={
                "shopId": shop_id,
                "people": people,
                "date": date,
                "time": time,
                "tableType": table_type,
                **({"idempotencyKey": idempotency_key} if idempotency_key else {}),
            },
        )
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}"}
    data = r.json()
    if not data.get("success"):
        return {"success": False, "error": data.get("errorMsg", "unknown")}
    return {"success": True, **data["data"]}


async def tool_pay_booking_with_test_card(booking_code: str) -> dict:
    """用 TapPay sandbox test prime 為訂位支付訂金，回 rec_trade_id。"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{settings.java_backend_url}/api/booking/pay-test",
            headers={"X-Demo-Mode": "true"},
            json={"bookingCode": booking_code},
        )
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}"}
    data = r.json()
    if not data.get("success"):
        return {"success": False, "error": data.get("errorMsg", "unknown")}
    return {"success": True, **data["data"]}


TOOL_DISPATCH = {
    "search_shops_by_mrt": tool_search_by_mrt,
    "semantic_shop_search": tool_semantic_search,
    "create_hot_seat_order": tool_create_hot_seat_order,
    "create_booking": tool_create_booking,
    "pay_booking_with_test_card": tool_pay_booking_with_test_card,
}

TOOLS = [
    {
        "function_declarations": [
            {
                "name": "search_shops_by_mrt",
                "description": "查詢指定捷運站附近的店家。當使用者提到特定捷運站名（如「市政府」「中山國小」「中山」「信義安和」）時使用。",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "station": {
                            "type": "STRING",
                            "description": "捷運站名，例如「市政府」「中山國小」「中山」",
                        },
                        "radius": {
                            "type": "INTEGER",
                            "description": "搜尋半徑（公尺），預設 500",
                        },
                    },
                    "required": ["station"],
                },
            },
            {
                "name": "semantic_shop_search",
                "description": "語意搜尋店家。當使用者描述抽象需求（如「想吃手搖飲」「適合約會」「有沒有 Hot Seat 限時搶位」），用此 tool。回應含 hot_seat_vouchers 欄位。",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "create_hot_seat_order",
                "description": """為用戶搶 Hot Seat 限時名額。當用戶明確說想訂位、想搶位、想下訂某個 Hot Seat 時呼叫。
回應含 voucher_order_id。僅支援已啟動 Hot Seat 的方案。
若用戶尚未指定 voucher_id，應先呼叫 semantic_shop_search 找店，再從回應的 hot_seat_vouchers 挑一個。""",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "voucher_id": {
                            "type": "INTEGER",
                            "description": "Hot Seat 方案 ID（從 search 結果 hot_seat_vouchers 取得，不要瞎猜）",
                        },
                    },
                    "required": ["voucher_id"],
                },
            },
            {
                "name": "create_booking",
                "description": """為用戶建立餐廳訂位。當用戶說「幫我訂位」「我要訂」「訂明天晚上」時呼叫。
回應含 bookingCode、needsDeposit、depositTotal。
若用戶沒指定日期預設明天；沒指定時間預設 19:00。
若尚未取得 shop_id，應先 semantic_shop_search 找到店家再呼叫本 tool。""",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "shop_id":    {"type": "INTEGER", "description": "店家 ID"},
                        "people":     {"type": "INTEGER", "description": "人數 1-12"},
                        "date":       {"type": "STRING",  "description": "日期 YYYY-MM-DD，預設明天"},
                        "time":       {"type": "STRING",  "description": "時間 HH:MM，預設 19:00"},
                        "table_type": {"type": "STRING",  "description": "normal/bar/private，預設 normal"},
                    },
                    "required": ["shop_id", "people"],
                },
            },
            {
                "name": "pay_booking_with_test_card",
                "description": """用 TapPay sandbox 測試卡為訂位支付訂金。
僅在使用者明確要求支付某個 bookingCode 時呼叫；不要在建立訂位後自動付款。
回應含 rec_trade_id（TapPay 交易編號）。""",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "booking_code": {
                            "type": "STRING",
                            "description": "create_booking 回應的 bookingCode",
                        },
                    },
                    "required": ["booking_code"],
                },
            },
        ]
    }
]

AGENT_SYSTEM_PROMPT = """你是台灣店家推薦助手。根據使用者的問題，選擇合適的 tool 查詢資料，然後用繁體中文簡潔回答。

==== 對話決策策略（像真人 concierge，不是搜尋框）====
- 先判斷需求完整度，再決定追問、查店家、比較或訂位。
- 明確推薦需求：已有地點、料理類型、用途、人數、日期/時段中的至少 2 個，或指定店名 → 可以查 tool 並推薦。
- 模糊需求：只有「想聚餐」「7 個人能聚餐」「適合聊天」「附近好吃」「推薦餐廳」但缺少區域、日期/時段或料理偏好 → 不要硬推薦；先用 2-3 個短問題收斂需求（區域、日期/時段、料理/氣氛）。
- 若使用者問「比較」「哪個適合」「幫我挑」「適合安靜聊天/家庭/約會」→ 回答必須有判斷依據，不只列店名。
- 查到多家候選時，用短段落或條列比較，不要輸出 markdown table；LINE 內表格會跑版。
- 若是口味真實性問題（如「正宗川菜」「香麻辣」「像日本當地」），先說明判斷維度，再推薦符合的店。
- 需要追問時不要道歉；用「我先幫你收斂方向」的語氣，讓使用者知道下一步怎麼回答。
- 不要把不確定資訊寫成事實；資料未標示時寫「目前資料未標示」。

==== 地點與捷運 ====
- 使用者提到明確捷運站名（例如信義安和、中山國小、象山、雙連、市政府）時，優先使用 search_shops_by_mrt。
- 若同時指定捷運站與料理類型，先查捷運站附近，再用分類、評論摘要與可訂狀態篩選。
- 使用者說「附近」但沒有目前位置時，先追問區域或捷運站，不要假設位置。

==== 回答風格 ====
- 開頭先給一句處理方向，例如「我先幫你用區域、口味與可訂狀態篩選。」
- 推薦時要說「為什麼是這家」，不是只列清單。
- 複雜需求可以先給短框架，再給表格；避免長篇散文。
- 少用 emoji；若使用，最多 1 個，避免像社群文。
- 對標高品質 concierge：先判斷使用者真正想解決的問題，再給選項，不要像資料庫搜尋結果。
- 推薦型回答固定結構：
  1. 一句「我先用什麼條件篩選」的方向判斷。
  2. 一句「我會優先推哪幾間／為什麼」的結論。
  3. 若有 2 家以上，用 1-3 行短條列比較，不要輸出 markdown table。
  4. 結尾給下一步 CTA，例如「如果你告訴我日期與人數，我可以直接幫你查可訂時段。」
- 模糊需求不要硬推薦。先用 2-3 個問題收斂：區域/捷運、日期時段、人數、料理或氣氛偏好。
- 多人聚餐、安靜聊天、正宗口味、約會、家庭聚餐這類需求，回答要先說判斷維度，例如包廂/座位寬鬆、評論提到的環境、是否可線上訂位。

==== 推薦分類限制（最重要）====
- 推薦必須符合使用者的主要分類意圖：
  - 用戶說「火鍋」→ 只推薦火鍋店，不推薦拉麵、牛排等（即使也是熱食）
  - 用戶說「日式料理」→ 只推薦日式餐廳，不推薦其他亞洲料理
- 候選資料中的 category/category_slug 是分類依據；若 category 已符合主要意圖，不要因店名或特色菜自行改判為不符合
- 若符合條件的店家有限，誠實告知：「信義區火鍋目前找到 X 家，以下整理」
- 寧可推薦少（1-3 家）也不要補充非相關分類的店家
- 禁止使用「特別加碼」「也可以試試」等方式推薦非主類別店家
- 低數量推薦要像精選，不要像不足：
  - 推薦 3 家：用「為您推薦以下三間熱門選擇:」
  - 推薦 2 家：用「為您整理了 2 間符合的選擇:」
  - 推薦 1 家：用「在此類別中，我為您推薦 1 家最適合的:」，結尾加「若想擴大範圍，可以嘗試詢問鄰近區域或相關類型（如美式餐廳）。」
  - 推薦 0 家：用「目前 DB 中沒有完全符合的店家，以下是相近選擇:」，並建議放寬區域或類型
- 不要為了湊數強推 3 家；品質優先

==== 一般訂位流程（create_booking）====
- 用戶說「幫我訂位」「我要訂」「訂明天晚上」→ 先 semantic_shop_search 確認 shop_id
- 找到店家後 → create_booking 建立訂位
- 若回應 needsDeposit=true → 不要自動付款；回覆訂位已保留、待支付訂金，讓前端卡片提供「立即支付」CTA
- 若 needsDeposit=false → 訂位完成、不要付款
- 一次對話最多 1 個 booking，不要重複建立
- 訂位建立後，回應要包含 bookingCode；只有使用者明確支付完成後才包含 rec_trade_id
- 若使用者只指定品牌但未指定分店，而候選中有多間同品牌分店，必須先詢問使用者選哪間分店；禁止直接替使用者挑分店下訂

==== Hot Seat 搶位流程（create_hot_seat_order）====
- 用戶說「幫我搶」「搶位」「想搶熱座」→ 呼叫 create_hot_seat_order
- 若不知道 voucher_id，先 semantic_shop_search 找到 hot_seat_vouchers，再取其中一個 id
- 訂單成功後，回應要包含 voucher_order_id，並提示用戶到「我的訂單」查看
- 一個 query 最多訂 1 個 Hot Seat 方案

==== 通用規則 ====
- 不要主動下單，除非用戶明確表示要訂
- 一個 query 最多執行 1 次訂位動作"""


def _agent_system_prompt() -> str:
    today = taipei_today()

    return (
        f"今天日期：{today.isoformat()}（Asia/Taipei）。"
        "解析「今天」「明天」「下週」等相對日期時必須以此為準。"
        "今天不可訂位，最早可訂明天；若用戶明確說今天或過去日期，不得呼叫 create_booking，"
        "必須先告知最早可訂明天並詢問是否改日期。若用戶未指定日期，才使用明天。"
        "禁止建立今天或過去日期訂位。\n\n"
        f"{AGENT_SYSTEM_PROMPT}"
    )


class AgentRecommendationDecision(BaseModel):
    recommended_shop_ids: list[int] = Field(default_factory=list)
    narrative: str = ""
    rejected_shop_ids: list[int] = Field(default_factory=list)
    rejection_summary: str | None = None


def _shop_id(shop: dict) -> int | None:
    raw_id = shop.get("shop_id") or shop.get("id")
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None


def _shop_brand_key(shop: dict) -> str:
    name = str(shop.get("name") or "").strip()
    for sep in ("｜", "|", " ", "　", "-", "－", "("):
        if sep in name:
            prefix = name.split(sep, 1)[0].strip()
            if prefix and prefix not in {"店家", "餐廳"}:
                name = prefix
            break
    return name.strip()


def _dedupe_shops_by_brand(shops: list[dict]) -> list[dict]:
    selected: list[dict] = []
    seen: set[str] = set()
    for shop in shops:
        key = _shop_brand_key(shop).lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        selected.append(shop)
    return selected


def _shop_branch_label(shop: dict, brand: str) -> str:
    name = str(shop.get("name") or "").strip()
    label = name
    if brand and label.startswith(brand):
        label = label[len(brand) :]
    label = label.strip(" ｜|　")
    if label:
        return label
    district = str(shop.get("district") or "").strip()
    mrt = str(shop.get("mrt_station") or "").strip()
    return " / ".join(part for part in (district, mrt) if part)


def _query_mentions_unique_branch(query: str, same_brand_shops: list[dict], brand: str) -> bool:
    normalized_query = query.replace(" ", "").replace("　", "")
    matches = 0
    for shop in same_brand_shops:
        name = str(shop.get("name") or "").replace(" ", "").replace("　", "")
        branch = _shop_branch_label(shop, brand).replace(" ", "").replace("　", "")
        branch_core = branch.removesuffix("店")
        if name and name in normalized_query:
            matches += 1
        elif branch and branch in normalized_query:
            matches += 1
        elif branch_core and len(branch_core) >= 3 and branch_core in normalized_query:
            matches += 1
    return matches == 1


def _booking_intent(query: str) -> bool:
    return any(token in query for token in ("訂", "訂位", "預約", "幫我訂", "我要訂"))


def _explicit_same_day_booking_request(query: str) -> bool:
    if not _booking_intent(query):
        return False
    normalized = query.replace(" ", "").replace("　", "")
    if "明天" in normalized:
        return False
    return any(token in normalized for token in ("今天", "今日", "今晚", "今夜"))


def _same_day_booking_policy_answer() -> str:
    tomorrow = taipei_today() + timedelta(days=1)
    return (
        "很抱歉，系統規定不可預訂今天的位子。"
        f"最早可預訂明天（{tomorrow.isoformat()}）。"
        "請問您需要改訂明天同一時間嗎？"
    )


def _payment_intent(query: str) -> bool:
    return any(token in query for token in ("付款", "支付", "付訂金", "刷卡", "pay", "付款訂金"))


def _brand_matches_query(query: str, brand: str) -> bool:
    normalized_query = query.replace(" ", "").replace("　", "")
    normalized_brand = brand.replace(" ", "").replace("　", "")
    aliases = [normalized_brand]
    if "-" in normalized_brand:
        aliases.append(normalized_brand.split("-", 1)[0])
    return any(alias and len(alias) >= 2 and alias in normalized_query for alias in aliases)


def _branch_clarification_text(brand: str, same_brand_shops: list[dict]) -> str:
    lines = [f"我找到多間「{brand}」分店。為避免訂錯店，請先選擇要訂哪一間："]
    for index, shop in enumerate(same_brand_shops[:5], start=1):
        name = shop.get("name") or f"店家 ID {_shop_id(shop)}"
        district = shop.get("district") or "未標示區域"
        mrt = shop.get("mrt_station") or "未標示捷運"
        lines.append(f"{index}. {name}（{district}，捷運{mrt}）")
    lines.append("請回覆分店名稱或編號，我再幫您建立訂位。")
    return "\n".join(lines)


def _booking_branch_clarification_from_tool_call(query: str, tool_args: dict, search_result: dict) -> str | None:
    shops = search_result.get("shops", []) if isinstance(search_result, dict) else []
    if not shops:
        return None
    try:
        target_shop_id = int(tool_args.get("shop_id"))
    except (TypeError, ValueError):
        return None

    selected = next((shop for shop in shops if _shop_id(shop) == target_shop_id), None)
    if not selected:
        return None
    brand = _shop_brand_key(selected)
    if not brand:
        return None

    same_brand_shops = [
        shop for shop in shops if _shop_brand_key(shop) == brand and _shop_id(shop) is not None
    ]
    if len(same_brand_shops) <= 1:
        return None
    if _query_mentions_unique_branch(query, same_brand_shops, brand):
        return None
    return _branch_clarification_text(brand, same_brand_shops)


def _booking_branch_clarification_from_search(query: str, search_result: dict) -> str | None:
    if not _booking_intent(query):
        return None
    shops = search_result.get("shops", []) if isinstance(search_result, dict) else []
    by_brand: dict[str, list[dict]] = {}
    for shop in shops:
        brand = _shop_brand_key(shop)
        if brand and _shop_id(shop) is not None:
            by_brand.setdefault(brand, []).append(shop)

    for brand, same_brand_shops in by_brand.items():
        if len(same_brand_shops) <= 1:
            continue
        if not _brand_matches_query(query, brand):
            continue
        if _query_mentions_unique_branch(query, same_brand_shops, brand):
            continue
        return _branch_clarification_text(brand, same_brand_shops)
    return None


def _parse_agent_decision(raw: str) -> AgentRecommendationDecision | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    return AgentRecommendationDecision(
        recommended_shop_ids=[
            int(item) for item in data.get("recommended_shop_ids", []) if str(item).isdigit()
        ],
        narrative=str(data.get("narrative") or ""),
        rejected_shop_ids=[
            int(item) for item in data.get("rejected_shop_ids", []) if str(item).isdigit()
        ],
        rejection_summary=(
            str(data["rejection_summary"])
            if data.get("rejection_summary")
            else None
        ),
    )


def _fallback_agent_decision(answer: str, tool_result: dict) -> AgentRecommendationDecision:
    shops = tool_result.get("shops", []) if isinstance(tool_result, dict) else []
    mentioned_ids: list[int] = []
    for shop in shops:
        sid = _shop_id(shop)
        name = str(shop.get("name") or "")
        if sid is not None and name and name in answer:
            mentioned_ids.append(sid)
    return AgentRecommendationDecision(
        recommended_shop_ids=mentioned_ids,
        narrative=answer,
        rejected_shop_ids=[
            sid for shop in shops if (sid := _shop_id(shop)) is not None and sid not in mentioned_ids
        ],
    )


def _validate_agent_decision(
    decision: AgentRecommendationDecision,
    tool_result: dict,
) -> AgentRecommendationDecision:
    shops = tool_result.get("shops", []) if isinstance(tool_result, dict) else []
    available_ids = [_shop_id(shop) for shop in shops]
    valid_ids = {sid for sid in available_ids if sid is not None}
    recommended: list[int] = []
    for sid in decision.recommended_shop_ids:
        if sid in valid_ids and sid not in recommended:
            recommended.append(sid)

    rejected: list[int] = []
    for sid in decision.rejected_shop_ids:
        if sid in valid_ids and sid not in recommended and sid not in rejected:
            rejected.append(sid)
    for sid in available_ids:
        if sid is not None and sid not in recommended and sid not in rejected:
            rejected.append(sid)

    return AgentRecommendationDecision(
        recommended_shop_ids=recommended,
        narrative=filter_output(decision.narrative),
        rejected_shop_ids=rejected,
        rejection_summary=decision.rejection_summary,
    )


def _decision_payload(decision: AgentRecommendationDecision) -> dict:
    return {
        "recommended_shop_ids": decision.recommended_shop_ids,
        "narrative": decision.narrative,
        "rejected_shop_ids": decision.rejected_shop_ids,
        "rejection_summary": decision.rejection_summary,
    }


def _find_shop_from_tool_result(tool_result: dict, shop_id: int | None) -> dict | None:
    if shop_id is None:
        return None
    shops = tool_result.get("shops", []) if isinstance(tool_result, dict) else []
    for shop in shops:
        if _shop_id(shop) == shop_id:
            return shop
    return None


def _build_booking_transaction(
    booking_result: dict,
    payment_result: dict | None,
    search_result: dict,
) -> dict:
    """Merge reserve + optional pay-test into one UI-safe transaction payload."""
    booking_success = bool(booking_result.get("success"))
    payment_success = bool(payment_result and payment_result.get("success"))
    shop_id = booking_result.get("shopId") or booking_result.get("shop_id")
    try:
        shop_id = int(shop_id) if shop_id is not None else None
    except (TypeError, ValueError):
        shop_id = None

    shop = _find_shop_from_tool_result(search_result, shop_id)
    needs_deposit = bool(booking_result.get("needsDeposit"))

    if payment_result and not payment_success:
        status = "PAYMENT_FAILED"
    elif payment_success:
        status = "PAID"
    elif booking_success and needs_deposit:
        status = "PENDING_PAYMENT"
    elif booking_success:
        status = "CONFIRMED"
    else:
        status = "FAILED"

    return {
        "kind": "booking",
        "success": booking_success and (not needs_deposit or payment_success),
        "status": status,
        "shop_id": shop_id,
        "shop_name": booking_result.get("shopName") or (shop or {}).get("name"),
        "booking_code": booking_result.get("bookingCode"),
        "people": booking_result.get("people"),
        "date": booking_result.get("date"),
        "time": booking_result.get("time"),
        "table_type": booking_result.get("tableType"),
        "needs_deposit": needs_deposit,
        "deposit_total": booking_result.get("depositTotal"),
        "hold_expires_at": booking_result.get("holdExpiresAt"),
        "hold_minutes": booking_result.get("holdMinutes"),
        "rec_trade_id": (payment_result or {}).get("rec_trade_id"),
        "payment_amount": (payment_result or {}).get("amount"),
        "payment_note": (payment_result or {}).get("note"),
        "idempotent_replay": bool(booking_result.get("idempotentReplay")),
        "error": booking_result.get("error") or (payment_result or {}).get("error"),
    }


def _booking_confirmation_narrative(transaction: dict) -> str:
    if transaction.get("status") == "FAILED":
        return f"訂位建立失敗：{transaction.get('error') or '後端未回傳原因'}"
    if transaction.get("status") == "PAYMENT_FAILED":
        return (
            "已建立訂位，但訂金付款失敗。\n\n"
            f"- 訂位編號：`{transaction.get('booking_code')}`\n"
            f"- 錯誤：{transaction.get('error') or '付款流程未完成'}"
        )

    if transaction.get("needs_deposit"):
        minutes = transaction.get("hold_minutes") or 10
        status_line = f"訂位已保留，請於 {minutes} 分鐘內完成訂金付款。"
    else:
        status_line = "訂位已完成。"

    shop_name = transaction.get("shop_name") or f"店家 ID {transaction.get('shop_id')}"
    base = [
        status_line,
        "",
        f"- 店家：{shop_name}",
        f"- 人數：{transaction.get('people')} 人",
        f"- 時間：{transaction.get('date')} {transaction.get('time')}",
        f"- 訂位編號：`{transaction.get('booking_code')}`",
    ]
    if transaction.get("needs_deposit"):
        base.append(f"- 待付訂金：NT$ {transaction.get('deposit_total')}")
        if transaction.get("hold_expires_at"):
            base.append(f"- 保留期限：`{transaction.get('hold_expires_at')}`")
    else:
        base.append("- 訂金：免訂金，已直接確認")
    return "\n".join(base)


def _booking_duplicate_narrative(transaction: dict) -> str:
    shop_name = transaction.get("shop_name") or f"店家 ID {transaction.get('shop_id')}"
    return "\n".join(
        [
            "您剛才已建立相同訂位，我不會重複下訂。",
            "",
            f"- 店家：{shop_name}",
            f"- 人數：{transaction.get('people')} 人",
            f"- 時間：{transaction.get('date')} {transaction.get('time')}",
            f"- 訂位編號：`{transaction.get('booking_code')}`",
            "- 若尚未付款，請於保留期限內完成訂金付款，否則座位會釋放。",
        ]
    )


def _booking_key(shop_id: int | None, people: int | None, booking_date: str | None, booking_time: str | None) -> tuple | None:
    if shop_id is None or people is None or not booking_date or not booking_time:
        return None
    return (int(shop_id), int(people), str(booking_date), str(booking_time))


def _booking_key_from_tool_args(tool_args: dict) -> tuple | None:
    raw_shop_id = tool_args.get("shop_id")
    raw_people = tool_args.get("people")
    tomorrow = (taipei_today() + timedelta(days=1)).isoformat()
    raw_date = tool_args.get("date")
    booking_date = raw_date or tomorrow
    booking_time = tool_args.get("time") or "19:00"
    if raw_date:
        try:
            booking_date = date_cls.fromisoformat(str(raw_date)).isoformat()
        except ValueError:
            return None
    try:
        return _booking_key(int(raw_shop_id), int(raw_people), str(booking_date), str(booking_time))
    except (TypeError, ValueError):
        return None


def _agent_booking_idempotency_key(session_id: str, tool_args: dict) -> str | None:
    key = _booking_key_from_tool_args(tool_args)
    if key is None:
        return None
    shop_id, people, booking_date, booking_time = key
    table_type = str(tool_args.get("table_type") or "normal")
    session_part = session_id or "anonymous"
    raw = f"agent:{session_part}:{shop_id}:{people}:{booking_date}:{booking_time}:{table_type}"
    return raw[:120]


def _find_duplicate_booking_transaction(history: list[dict], tool_args: dict) -> dict | None:
    target_key = _booking_key_from_tool_args(tool_args)
    if target_key is None:
        return None
    for turn in reversed(history):
        tx = turn.get("transaction") if isinstance(turn, dict) else None
        if not isinstance(tx, dict) or tx.get("kind") != "booking":
            continue
        if _pending_booking_expired(tx):
            continue
        if tx.get("status") not in {"PAID", "CONFIRMED", "PENDING_PAYMENT"}:
            continue
        existing_key = _booking_key(
            tx.get("shop_id"),
            tx.get("people"),
            tx.get("date"),
            tx.get("time"),
        )
        if existing_key == target_key:
            duplicate = dict(tx)
            duplicate["duplicate"] = True
            return duplicate
    return None


def _latest_successful_booking_transaction(history: list[dict]) -> dict | None:
    for turn in reversed(history):
        tx = turn.get("transaction") if isinstance(turn, dict) else None
        if not isinstance(tx, dict) or tx.get("kind") != "booking":
            continue
        if _pending_booking_expired(tx):
            continue
        if tx.get("status") not in {"PAID", "CONFIRMED", "PENDING_PAYMENT"}:
            continue
        duplicate = dict(tx)
        duplicate["duplicate"] = True
        return duplicate
    return None


def _pending_booking_expired(tx: dict) -> bool:
    if tx.get("status") != "PENDING_PAYMENT":
        return False
    raw_expiry = tx.get("hold_expires_at")
    if not raw_expiry:
        return False
    try:
        expiry = datetime.fromisoformat(str(raw_expiry))
    except ValueError:
        return False
    return datetime.now() >= expiry


def _build_agent_recommendation_decision(query: str, tool_result: dict) -> AgentRecommendationDecision:
    shops = tool_result.get("shops", []) if isinstance(tool_result, dict) else []
    if not shops:
        return AgentRecommendationDecision(narrative="")

    tool_context = _compact_tool_context(tool_result)
    prompt = f"""使用者問：{query}

候選店家：
{tool_context}

請輸出單一 JSON object，不能輸出 markdown code fence 或其他文字。

JSON schema:
{{
  "recommended_shop_ids": [number],
  "narrative": "user-facing plain Traditional Chinese, no markdown table",
  "rejected_shop_ids": [number],
  "rejection_summary": "optional one-line reason"
}}

決策規則：
- recommended_shop_ids 必須只包含候選店家 ID，且必須是 narrative 實際介紹的店家。
- narrative 提到幾家店，recommended_shop_ids 就必須有幾個 ID；不要在 narrative 中介紹未列入 recommended_shop_ids 的店。
- 最多推薦 3 家店，且每個 numbered bullet 只能介紹 1 家店。
- 若同品牌有多個分店，只選最符合需求的 1 家；不要在同一個 bullet 合併多家分店。
- 若使用者指定分類，推薦必須符合主要分類意圖，例如「火鍋」只推火鍋，「漢堡」只推美式/漢堡相關店。
- 候選資料中的 分類/category/category_slug 是分類依據；若分類已符合使用者主要意圖，視為符合，不要因店名、招牌菜或餐點型態自行改判為不符合。
- 符合條件少於 3 家時不要硬湊；可只推薦 1-2 家。
- narrative 的開頭要根據 recommended_shop_ids 數量使用下列語氣，低數量要像精選，不要像不足：
  - 3 家：使用「為您推薦以下三間熱門選擇:」
  - 2 家：使用「為您整理了 2 間符合的選擇:」
  - 1 家：使用「在此類別中，我為您推薦 1 家最適合的:」
  - 0 家：使用「目前 DB 中沒有完全符合的店家，以下是相近選擇:」
- recommended_shop_ids 只有 1 家時，narrative 結尾必須加：「若想擴大範圍，可以嘗試詢問鄰近區域或相關類型（如美式餐廳）。」
- recommended_shop_ids 為 0 家時，narrative 要建議放寬地點或相關類型。
- rejected_shop_ids 放入候選中未推薦的店，尤其是不符分類、地點或需求的店。
- narrative 不得輸出 markdown table，不得使用 |、:---、** 這類格式符號。
- 若使用者需求帶有比較意味（例如適合安靜聊天、家庭聚餐、正宗口味、多人聚餐），narrative 用短條列呈現比較：每家 1 行，格式為「店名：特色；提醒」。
- 若使用者需求資訊不足但已查到候選，不要假裝完全確定；先給 2-3 個方向，再用一句話追問區域、時段或料理偏好。
- narrative 應該像 concierge，不像搜尋列表。建議格式：
  - 第一段：我先用「地點 / 類型 / 用途 / 可訂狀態」幫你篩。
  - 第二段：明確結論，例如「我會優先看這 2 家」。
  - 比較條列：店家：適合原因；需要留意的地方。
  - CTA：若未指定日期/人數，請使用者補；若已指定，邀請查可訂或直接訂位。
- 避免只輸出「為您推薦以下三間熱門選擇」後接三個 bullet；這看起來像搜尋結果，不像 AI concierge。
- 不要編造候選資料以外的資訊。"""

    try:
        response = generate(
            settings.gemini_agent_model,
            prompt,
            types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        decision = _parse_agent_decision(response.text)
    except Exception:
        logger.exception("agent_decision_generation_failed")
        decision = None

    if decision is not None and len(decision.recommended_shop_ids) > 3:
        try:
            repair = generate(
                settings.gemini_agent_model,
                f"""{prompt}

你剛才的輸出違反規則，recommended_shop_ids 超過 3 家或在同一 bullet 合併多家店。
請修正為最多 3 家，且每個 numbered bullet 只介紹 1 家店。

原輸出：
{json.dumps(_decision_payload(decision), ensure_ascii=False)}""",
                types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            repaired_decision = _parse_agent_decision(repair.text)
            if repaired_decision is not None:
                decision = repaired_decision
        except Exception:
            logger.exception("agent_decision_repair_failed")

    if decision is None or not decision.narrative:
        fallback_answer = ""
        try:
            response = generate(
                settings.gemini_agent_model,
                f"使用者問：{query}\n\n查詢結果：\n{tool_context}\n\n根據查詢結果，用繁體中文推薦 1-3 家最符合需求的店。",
            )
            fallback_answer = filter_output(response.text)
        except Exception:
            logger.exception("agent_decision_fallback_failed")
        decision = _fallback_agent_decision(fallback_answer, tool_result)

    return _validate_agent_decision(decision, tool_result)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchHit(BaseModel):
    shop_id: int
    name: str
    district: str | None
    mrt_station: str | None
    score: float
    category: str | None = None
    avg_price: int | None = None
    price_per_person: str | None = None
    booking_difficulty: str | None = None
    atmosphere_tags: list[str] = []
    signature_dishes: list[str] = []
    hot_seat_count: int = 0


class RecommendRequest(BaseModel):
    query: str
    top_k: int = 5


class RecommendResponse(BaseModel):
    query: str
    answer: str
    hits: list[SearchHit]


class AgentRequest(BaseModel):
    query: str
    session_id: str | None = None  # 前端帶入；None = 無狀態單輪


@dataclass
class AgentToolState:
    query: str
    session_id: str
    history: list[dict]
    contents: list
    tools_used: list[str] = field(default_factory=list)
    last_tool_result: dict = field(default_factory=dict)
    latest_search_result: dict = field(default_factory=dict)
    booking_result: dict | None = None
    payment_result: dict | None = None
    final_transaction: dict | None = None
    direct_answer: str | None = None


@dataclass
class ToolGuardResult:
    action: str
    args: dict = field(default_factory=dict)
    direct_answer: str | None = None
    final_transaction: dict | None = None
    last_tool_result: dict | None = None


def _history_to_contents(history: list[dict], query: str) -> list:
    contents: list = []
    for turn in history:
        role = turn.get("role")
        text = turn.get("content", "")
        if role in ("user", "model") and text:
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=text)],
                )
            )
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)],
        )
    )
    return contents


def _tool_result_summary(tool_result: dict) -> dict:
    if not isinstance(tool_result, dict):
        return {"kind": type(tool_result).__name__}
    if "shops" in tool_result:
        return {"shops_count": len(tool_result.get("shops") or [])}
    if "transaction" in tool_result:
        tx = tool_result.get("transaction") or {}
        return {
            "transaction_status": tx.get("status"),
            "booking_code": tx.get("booking_code"),
        }
    if "success" in tool_result:
        return {
            "success": tool_result.get("success"),
            "status": tool_result.get("status"),
            "booking_code": tool_result.get("bookingCode") or tool_result.get("booking_code"),
            "error": tool_result.get("error"),
        }
    return {"keys": sorted(tool_result.keys())[:8]}


def _before_tool_call(state: AgentToolState, tool_name: str, tool_args: dict) -> ToolGuardResult:
    guarded_args = dict(tool_args)

    if tool_name == "create_booking":
        clarification = _booking_branch_clarification_from_tool_call(
            state.query,
            guarded_args,
            state.latest_search_result,
        )
        if clarification:
            return ToolGuardResult(
                action="direct",
                direct_answer=clarification,
                last_tool_result=state.latest_search_result,
            )

        duplicate_transaction = _find_duplicate_booking_transaction(state.history, guarded_args)
        if duplicate_transaction:
            return ToolGuardResult(
                action="direct",
                direct_answer=_booking_duplicate_narrative(duplicate_transaction),
                final_transaction=duplicate_transaction,
                last_tool_result={"transaction": duplicate_transaction},
            )

        idempotency_key = _agent_booking_idempotency_key(state.session_id, guarded_args)
        if idempotency_key:
            guarded_args["idempotency_key"] = idempotency_key

    elif tool_name == "pay_booking_with_test_card" and not _payment_intent(state.query):
        # Payment requires explicit user action; never auto-pay just because a booking was created.
        return ToolGuardResult(action="stop")

    return ToolGuardResult(action="continue", args=guarded_args)


def _after_tool_call(
    state: AgentToolState,
    tool_name: str,
    tool_result: dict,
    candidate_content=None,
) -> None:
    state.tools_used.append(tool_name)
    state.last_tool_result = tool_result
    if tool_name in {"semantic_shop_search", "search_shops_by_mrt"}:
        state.latest_search_result = tool_result
    elif tool_name == "create_booking":
        state.booking_result = tool_result
    elif tool_name == "pay_booking_with_test_card":
        state.payment_result = tool_result

    if candidate_content is not None:
        state.contents.append(candidate_content)
        state.contents.append(
            types.Content(
                role="tool",
                parts=[types.Part.from_function_response(name=tool_name, response=tool_result)],
            )
        )


async def _run_agent_turn(query: str, session_id: str) -> tuple[str, list[str], dict]:
    history = session_store.load_history(session_id) if session_id else []
    contents = _history_to_contents(history, query)
    state = AgentToolState(query=query, session_id=session_id, history=history, contents=contents)
    final_answer = ""

    for _ in range(4):
        response = generate(
            settings.gemini_agent_model,
            state.contents,
            types.GenerateContentConfig(
                tools=TOOLS,
                system_instruction=_agent_system_prompt(),
            ),
        )

        candidate = response.candidates[0]
        function_call = None
        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_call = part.function_call
                break

        if not function_call:
            final_answer = filter_output(response.text)
            break

        tool_name = function_call.name
        tool_args = dict(function_call.args)

        tool_fn = TOOL_DISPATCH.get(tool_name)
        if tool_fn is None:
            raise HTTPException(500, f"unknown tool: {tool_name}")

        guard = _before_tool_call(state, tool_name, tool_args)
        if guard.action == "direct":
            final_answer = guard.direct_answer or ""
            state.final_transaction = guard.final_transaction
            state.last_tool_result = guard.last_tool_result or {}
            break
        if guard.action == "stop":
            break

        tool_result = await tool_fn(**guard.args)
        _after_tool_call(state, tool_name, tool_result, candidate.content)
    else:
        final = generate(
            settings.gemini_agent_model,
            state.contents,
            types.GenerateContentConfig(
                system_instruction="根據以上工具查詢結果，用 2-3 句繁體中文給出最終回答。",
            ),
        )
        final_answer = filter_output(final.text)

    if state.last_tool_result.get("shops"):
        decision = _build_agent_recommendation_decision(query, state.last_tool_result)
        if decision.narrative:
            final_answer = decision.narrative
            state.last_tool_result["agent_decision"] = _decision_payload(decision)

    if session_id:
        new_history = history + [
            {"role": "user", "content": query},
            {"role": "model", "content": final_answer},
        ]
        session_store.save_history(session_id, new_history)

    return final_answer, state.tools_used, state.last_tool_result


def _sse_frame(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bytebites-ai"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/ai/ping-java")
async def ping_java():
    """Verify connectivity to Java backend."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{settings.java_backend_url}/api/category/list")
            return {
                "java_backend": "reachable",
                "java_status": resp.status_code,
                "java_categories_count": len(resp.json().get("data", [])),
            }
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Java backend unreachable: {exc}") from exc


@app.post("/api/ai/search")
async def semantic_search(req: SearchRequest):
    """Semantic shop search via Gemini embedding + Qdrant."""
    try:
        check_input(req.query)
    except GuardrailViolation as exc:
        raise HTTPException(400, f"input rejected: {exc}") from exc

    ai_requests.labels(endpoint="search").inc()
    with ai_latency.labels(endpoint="search").time():
        hits = await _semantic_hits(req.query, req.top_k)

    return {
        "query": req.query,
        "hits": [
            SearchHit(
                shop_id=hit["shop_id"],
                name=hit.get("name"),
                district=hit.get("district"),
                mrt_station=hit.get("mrt_station"),
                score=float(hit["rerank_score"]),
                category=hit.get("category"),
                avg_price=hit.get("avg_price"),
                price_per_person=hit.get("price_per_person"),
                booking_difficulty=hit.get("booking_difficulty"),
                atmosphere_tags=hit.get("atmosphere_tags") or [],
                signature_dishes=hit.get("signature_dishes") or [],
                hot_seat_count=len(hit.get("hot_seat_vouchers") or []),
            )
            for hit in hits
        ],
    }


@app.post("/api/ai/recommend")
async def recommend(req: RecommendRequest):
    """Full RAG: retrieve + LLM generate recommendation."""
    try:
        check_input(req.query)
    except GuardrailViolation as exc:
        raise HTTPException(400, f"input rejected: {exc}") from exc

    ai_requests.labels(endpoint="recommend").inc()
    with ai_latency.labels(endpoint="recommend").time():
        hits = await _semantic_hits(req.query, req.top_k)

        context_lines = []
        for index, payload in enumerate(hits, 1):
            context_lines.append(
                f"{index}. {payload.get('name')} | {payload.get('district')} | "
                f"捷運{payload.get('mrt_station')}站 | 評分 {payload.get('score', 'N/A')} | "
                f"分類 {payload.get('category', 'N/A')} | "
                f"氛圍 {', '.join(payload.get('atmosphere_tags') or []) or '未提供'} | "
                f"價位 {payload.get('price_per_person') or payload.get('avg_price') or '未提供'} | "
                f"預約難度 {payload.get('booking_difficulty') or '未提供'}"
            )
        context = "\n".join(context_lines)

        prompt = f"""你是台灣在地店家推薦助手。使用者問：「{req.query}」

候選店家列表：
{context}

請用 2-3 句話自然地推薦 1-2 家最合適的店家，說明推薦理由（位置、評分等）。
不要編造資訊，只能用候選列表中的資料。用繁體中文回答。"""

        answer = call_llm(prompt)

    return RecommendResponse(
        query=req.query,
        answer=filter_output(answer),
        hits=[
            SearchHit(
                shop_id=hit["shop_id"],
                name=hit.get("name"),
                district=hit.get("district"),
                mrt_station=hit.get("mrt_station"),
                score=float(hit["rerank_score"]),
                category=hit.get("category"),
                avg_price=hit.get("avg_price"),
                price_per_person=hit.get("price_per_person"),
                booking_difficulty=hit.get("booking_difficulty"),
                atmosphere_tags=hit.get("atmosphere_tags") or [],
                signature_dishes=hit.get("signature_dishes") or [],
                hot_seat_count=len(hit.get("hot_seat_vouchers") or []),
            )
            for hit in hits
        ],
    )


@app.post("/api/ai/agent")
async def agent(req: AgentRequest):
    """Multi-turn function-calling agent with Redis session history."""
    try:
        check_input(req.query)
    except GuardrailViolation as exc:
        raise HTTPException(400, f"input rejected: {exc}") from exc

    session_id = req.session_id or ""

    ai_requests.labels(endpoint="agent").inc()
    with ai_latency.labels(endpoint="agent").time():
        final_answer, tools_used, last_tool_result = await _run_agent_turn(req.query, session_id)

    return {
        "query":      req.query,
        "answer":     final_answer,
        "tools_used": tools_used,
        "tool_result": last_tool_result,
        "session_id": session_id,
    }


def _compact_tool_context(tool_result: dict) -> str:
    shops = tool_result.get("shops", [])
    if not shops:
        return json.dumps(tool_result, ensure_ascii=False)
    lines: list[str] = []
    for s in shops:
        name = s.get("name") or ""
        shop_id = _shop_id(s)
        district = s.get("district") or ""
        mrt = s.get("mrt_station") or ""
        category = s.get("category") or s.get("category_slug") or ""
        price = s.get("price_per_person") or (f"~${s['avg_price']}/人" if s.get("avg_price") else "")
        booking = s.get("booking_difficulty") or ""
        tags = "、".join((s.get("atmosphere_tags") or [])[:3])
        dishes = "、".join((s.get("signature_dishes") or [])[:3])
        summary = (s.get("ai_summary") or "")[:100]
        parts: list[str] = [f"ID:{shop_id}", f"【{name}】{district}"]
        if category:
            parts.append(f"分類:{category}")
        if mrt:
            parts.append(f"捷運{mrt}")
        if price:
            parts.append(price)
        if booking:
            parts.append(booking)
        if tags:
            parts.append(f"氛圍:{tags}")
        if dishes:
            parts.append(f"招牌:{dishes}")
        if summary:
            parts.append(summary)
        lines.append(" | ".join(parts))
    return "\n".join(lines)


async def _run_agent_turn_stream(query: str, session_id: str) -> AsyncIterator[dict]:
    """
    Async generator yielding SSE payload dicts with true token streaming.

    Strategy:
    - Phase 1 (tool calls): sync generate() per iteration — fast, structured JSON decisions
    - Phase 2 (final synthesis): structured JSON decision, then stream its narrative
    - Zero-tool-call path: sync answer chunked at character level (fast response, streaming moot)
    """
    history = session_store.load_history(session_id) if session_id else []
    contents = _history_to_contents(history, query)
    state = AgentToolState(query=query, session_id=session_id, history=history, contents=contents)
    direct_answer: str | None = None
    yield {"type": "turn_start", "query": query, "session_id": session_id}

    if _explicit_same_day_booking_request(query):
        full_answer = _same_day_booking_policy_answer()
        chunk_size = 18
        for i in range(0, len(full_answer), chunk_size):
            chunk = full_answer[i : i + chunk_size]
            yield {"type": "message_update", "content": chunk}
            yield {"type": "chunk", "content": chunk}
        if session_id:
            session_store.save_history(
                session_id,
                history + [
                    {"role": "user", "content": query},
                    {"role": "model", "content": full_answer},
                ],
            )
        done_payload = {
            "type": "done",
            "answer": full_answer,
            "transaction": None,
            "tools_used": [],
            "tool_result": {},
            "session_id": session_id,
        }
        yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
        yield done_payload
        return

    # Phase 1: tool-calling loop (sync) — yields tool events as each fires
    for _ in range(4):
        response = generate(
            settings.gemini_agent_model,
            state.contents,
            types.GenerateContentConfig(
                tools=TOOLS,
                system_instruction=_agent_system_prompt(),
            ),
        )
        candidate = response.candidates[0]
        function_call = None
        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_call = part.function_call
                break

        if not function_call:
            if not state.tools_used:
                # Zero tool calls — answer already computed; fast path, chunk as-is
                direct_answer = filter_output(response.text)
                if _booking_intent(query):
                    duplicate_transaction = _latest_successful_booking_transaction(history)
                    if duplicate_transaction and (
                        str(duplicate_transaction.get("booking_code") or "") in direct_answer
                        or "訂過" in direct_answer
                        or "已經訂" in direct_answer
                    ):
                        state.final_transaction = duplicate_transaction
                        state.last_tool_result = {"transaction": duplicate_transaction}
            break

        tool_name = function_call.name
        tool_fn = TOOL_DISPATCH.get(tool_name)
        if tool_fn is None:
            yield {"type": "error", "message": f"unknown tool: {tool_name}"}
            return

        tool_args = dict(function_call.args)
        guard = _before_tool_call(state, tool_name, tool_args)
        if guard.action == "direct":
            direct_answer = guard.direct_answer
            state.final_transaction = guard.final_transaction
            state.last_tool_result = guard.last_tool_result or {}
            break
        if guard.action == "stop":
            break

        yield {
            "type": "tool_execution_start",
            "name": tool_name,
            "args": guard.args,
            "session_id": session_id,
        }
        tool_result = await tool_fn(**guard.args)
        _after_tool_call(state, tool_name, tool_result, candidate.content)
        yield {
            "type": "tool_execution_end",
            "name": tool_name,
            "result_summary": _tool_result_summary(tool_result),
            "session_id": session_id,
        }
        yield {"type": "tool", "name": tool_name}

    # Phase 2: generate final answer
    full_answer = ""
    if direct_answer is not None:
        # Zero-tool path: chunk the pre-computed answer (fast, no visible delay)
        chunk_size = 18
        for i in range(0, len(direct_answer), chunk_size):
            full_answer = direct_answer
            chunk = direct_answer[i : i + chunk_size]
            yield {"type": "message_update", "content": chunk}
            yield {"type": "chunk", "content": chunk}
    else:
        if state.booking_result is not None:
            transaction = _build_booking_transaction(
                state.booking_result,
                state.payment_result,
                state.latest_search_result,
            )
            full_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result["transaction"] = transaction
        else:
            clarification = _booking_branch_clarification_from_search(query, state.last_tool_result)
            if clarification:
                full_answer = clarification
            else:
                decision = _build_agent_recommendation_decision(query, state.last_tool_result)
                full_answer = decision.narrative
                state.last_tool_result["agent_decision"] = _decision_payload(decision)
        chunk_size = 18
        for i in range(0, len(full_answer), chunk_size):
            chunk = full_answer[i : i + chunk_size]
            yield {"type": "message_update", "content": chunk}
            yield {"type": "chunk", "content": chunk}

    if session_id:
        session_store.save_history(
            session_id,
            history + [
                {"role": "user", "content": query},
                {
                    "role": "model",
                    "content": full_answer,
                    **({"transaction": state.final_transaction} if state.final_transaction else {}),
                },
            ],
        )

    done_payload = {
        "type": "done",
        "answer": full_answer,
        **state.last_tool_result.get("agent_decision", {}),
        "transaction": state.last_tool_result.get("transaction"),
        "tools_used": state.tools_used,
        "tool_result": state.last_tool_result,
        "session_id": session_id,
    }
    yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
    yield done_payload


@app.post("/api/ai/agent/stream")
async def agent_stream(req: AgentRequest):
    """SSE stream for multi-turn agent. Tool calls sync; final synthesis true-streamed via Gemini."""
    try:
        check_input(req.query)
    except GuardrailViolation as exc:
        raise HTTPException(400, f"input rejected: {exc}") from exc

    session_id = req.session_id or ""
    ai_requests.labels(endpoint="agent_stream").inc()

    async def event_gen() -> AsyncIterator[bytes]:
        yield _sse_frame({"type": "agent_start", "session_id": session_id})
        yield _sse_frame({"type": "status", "message": "thinking"})
        try:
            async for payload in _run_agent_turn_stream(req.query, session_id):
                yield _sse_frame(payload)
        except Exception as exc:
            logger.exception("agent_stream_failed")
            yield _sse_frame({"type": "agent_error", "message": str(exc), "session_id": session_id})
            yield _sse_frame({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/line/webhook")
@app.get("/line/webhook")
async def line_webhook_check():
    return {
        "status": "ok",
        "service": "bytebites-line-bot",
        "reply_enabled": settings.line_reply_enabled,
    }


@app.post("/api/line/webhook")
@app.post("/line/webhook")
async def line_webhook(request: Request):
    body_bytes = await request.body()
    signature = request.headers.get("x-line-signature")
    if not verify_line_signature(
        body_bytes=body_bytes,
        signature=signature,
        channel_secret=settings.line_channel_secret,
        enabled=settings.line_signature_verify,
    ):
        raise HTTPException(status_code=400, detail="Invalid LINE signature")

    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    results: list[dict] = []
    for event in payload.get("events", []):
        reply_token = event.get("replyToken")
        messages = await _build_line_reply_messages(event)
        if reply_token and messages:
            result = await reply_messages(
                reply_token=reply_token,
                messages=messages,
                channel_access_token=settings.line_channel_access_token,
                enabled=settings.line_reply_enabled,
            )
        else:
            result = {"ok": True, "skipped": True, "reason": "No replyToken or no messages"}
        results.append(
            {
                "event_type": event.get("type"),
                "message_type": (event.get("message") or {}).get("type"),
                "reply_result": result,
            }
        )

    return {
        "status": "ok",
        "events_count": len(payload.get("events", [])),
        "results": results,
    }


@app.get("/line/photo/{shop_id}")
async def line_shop_photo(shop_id: int):
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for photo_url in _line_photo_candidates(shop_id):
            try:
                upstream = await client.get(
                    photo_url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                        "Referer": "https://www.google.com/",
                    },
                )
            except Exception:
                logger.info("line_photo_candidate_failed shop_id=%s", shop_id)
                continue
            content_type = upstream.headers.get("content-type") or "image/jpeg"
            if upstream.status_code >= 400 or not content_type.startswith("image/"):
                continue
            return Response(
                upstream.content,
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=3600"},
            )
    raise HTTPException(status_code=404, detail="photo not found")


@app.get("/line/shop/{shop_id}", response_class=HTMLResponse)
async def line_shop_detail(shop_id: int):
    shop = await _fetch_java_shop(shop_id)
    if not shop:
        return HTMLResponse(_line_html_page("找不到店家", "這間店目前無法取得資料。", []), status_code=404)
    metadata = await _fetch_java_ai_metadata(shop_id)
    policy = await _fetch_java_booking_policy(shop_id)
    manifest_shop = _line_media_shop(shop_id)
    name = _html_escape(str(shop.get("name") or f"店家 {shop_id}"))
    district = _html_escape(str(shop.get("district") or ""))
    mrt = _html_escape(str(shop.get("mrtStation") or shop.get("mrt_station") or ""))
    address = _html_escape(str(shop.get("address") or ""))
    avg_price = shop.get("avgPrice") or shop.get("avg_price")
    rating = shop.get("score") or shop.get("rating")
    comments = shop.get("comments") or shop.get("reviewCount")
    phone_raw = str(metadata.get("phone") or shop.get("phone") or "").strip()
    phone = _html_escape(phone_raw)
    tel_href = _html_escape("tel:" + "".join(ch for ch in phone_raw if ch.isdigit() or ch == "+")) if phone_raw else ""
    summary = _html_escape(_line_detail_summary(shop, metadata, manifest_shop))
    dishes = _parse_json_list(metadata.get("signatureDishes"))[:4]
    tags = _parse_json_list(metadata.get("atmosphereTags"))[:3]
    hours = _parse_json_list(metadata.get("openingHours") or shop.get("businessHours"))[:7]
    price = _html_escape(str(metadata.get("pricePerPerson") or (f"NT$ {avg_price}" if avg_price else "價位未標示")))
    booking = _html_escape(str(metadata.get("bookingDifficulty") or "可查看訂位狀態"))
    deposit = _line_deposit_summary(policy)
    review_groups = _line_review_groups(shop_id)
    image_uri = _line_public_uri(f"/line/photo/{shop_id}?v={LINE_PHOTO_VERSION}") if _line_photo_candidates(shop_id) else ""
    booking_uri = _line_public_uri(f"/line/book/{shop_id}")
    map_uri = _line_google_maps_uri(str(shop.get("name") or ""), str(shop.get("address") or ""))
    map_link = _html_escape(map_uri)
    basis_items = _line_recommendation_basis(shop, metadata, manifest_shop)
    info_bits = [
        district or "台北",
        f"捷運{mrt}" if mrt else "",
        price,
        f"Google {rating} 分" if rating else "",
        f"{comments} 則評論" if comments else "",
    ]
    hero = (
        f"""
      <div class="hero">
        <img src="{image_uri}" alt="{name}" onerror="this.parentElement.classList.add('hero-fallback');this.remove();">
        <span>ByteBites</span>
      </div>
        """
        if image_uri
        else '<div class="hero hero-fallback"><span>ByteBites</span></div>'
    )
    body = f"""
      {hero}
      <main>
        <p class="eyebrow">ByteBites 推薦餐廳</p>
        <h1>{name}</h1>
        <div class="meta">{' · '.join(bit for bit in info_bits if bit)}</div>
        <section>
          <h2>餐廳特色</h2>
          <p>{summary}</p>
          {_line_pills_html([*dishes, *tags])}
        </section>
        <section>
          <h2>推薦依據</h2>
          {_line_bullet_html(basis_items)}
        </section>
        {_line_review_html(review_groups)}
        <section>
          <h2>訂金與訂位規則</h2>
          <p>{_html_escape(deposit)}</p>
          <p>{booking}。送出訂位後，系統會回覆訂位狀態；若需訂金，會先保留座位並提示付款。</p>
        </section>
        <section>
          <h2>店家資訊</h2>
          <p>{address or "地址資料未標示"}</p>
          <p>{f'<a href="{tel_href}">{phone}</a>' if phone and tel_href else "電話資料未標示"}</p>
          {_line_hours_html(hours)}
        </section>
        <div class="actions">
          <a class="primary" href="{booking_uri}">填日期人數</a>
          <a class="secondary" href="{map_link}">Google 地圖開啟</a>
        </div>
      </main>
    """
    return HTMLResponse(_line_shell(name, body))


@app.get("/line/book/{shop_id}", response_class=HTMLResponse)
async def line_booking_entry(shop_id: int):
    shop = await _fetch_java_shop(shop_id)
    policy = await _fetch_java_booking_policy(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    district = _html_escape(str((shop or {}).get("district") or ""))
    address = _html_escape(str((shop or {}).get("address") or ""))
    tomorrow = taipei_today() + timedelta(days=1)
    deposit_summary = _html_escape(_line_deposit_summary(policy))
    detail_uri = _line_public_uri(f"/line/shop/{shop_id}")
    confirm_uri = _line_public_uri(f"/line/book/{shop_id}/confirm")
    body = f"""
      <main>
        <p class="eyebrow">ByteBites 訂位入口</p>
        <h1>{name}</h1>
        <div class="meta">{district or "台北"}{f' · {address}' if address else ''}</div>
        <section>
          <h2>訂金政策</h2>
          <p>{deposit_summary}</p>
          <p>送出後會建立訂位請求；若店家需要訂金，狀態會先保留為待付款，未付款前不視為最終完成。</p>
        </section>
        <section>
          <h2>填寫訂位資訊</h2>
          <form class="booking-form" method="get" action="{confirm_uri}">
            <label>人數
              <select name="people">
                {''.join(f'<option value="{people}"{" selected" if people == 2 else ""}>{people} 人</option>' for people in range(1, 13))}
              </select>
            </label>
            <label>日期
              <input name="date" type="date" min="{tomorrow.isoformat()}" value="{tomorrow.isoformat()}" required>
            </label>
            <label>時間
              <select name="time">
                {''.join(f'<option value="{time}"{" selected" if time == "19:00" else ""}>{time}</option>' for time in ["11:30", "12:00", "12:30", "18:00", "18:30", "19:00", "19:30", "20:00"])}
              </select>
            </label>
            <input type="hidden" name="tableType" value="normal">
            <button class="primary" type="submit">送出並查看狀態</button>
          </form>
        </section>
        <section>
          <h2>送出後狀態</h2>
          <div class="status-list">
            <p><strong>CONFIRMED</strong>：免訂金，訂位已成立。</p>
            <p><strong>PENDING_PAYMENT</strong>：需訂金，座位已先保留，請依系統提示完成付款。</p>
            <p><strong>FAILED</strong>：名額不足或資料有誤，可返回修改。</p>
          </div>
        </section>
        <a class="secondary" href="{detail_uri}">查看店家資訊</a>
      </main>
    """
    return HTMLResponse(_line_shell(f"{name} 訂位", body))


@app.get("/line/book/{shop_id}/confirm", response_class=HTMLResponse)
async def line_booking_confirm(shop_id: int, people: int = 2, date: str = "", time: str = "19:00", tableType: str = "normal"):
    shop = await _fetch_java_shop(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    error = _validate_line_booking(people, date, time, tableType)
    if error:
        return HTMLResponse(
            _line_html_page(
                "訂位資料需要修正",
                error,
                [
                    ("返回填寫", _line_public_uri(f"/line/book/{shop_id}")),
                    ("查看店家資訊", _line_public_uri(f"/line/shop/{shop_id}")),
                ],
            ),
            status_code=400,
        )

    result = await _reserve_line_booking(shop_id, people, date, time, tableType)
    if not result.get("success"):
        message = str(result.get("errorMsg") or "訂位建立失敗，請稍後再試。")
        return HTMLResponse(
            _line_html_page(
                "訂位未完成",
                message,
                [
                    ("重新填寫", _line_public_uri(f"/line/book/{shop_id}")),
                    ("查看店家資訊", _line_public_uri(f"/line/shop/{shop_id}")),
                ],
            ),
            status_code=409,
        )

    booking = result.get("data") if isinstance(result.get("data"), dict) else {}
    booking_code = _html_escape(str(booking.get("bookingCode") or ""))
    status = _html_escape(str(booking.get("status") or "CONFIRMED"))
    needs_deposit = bool(booking.get("needsDeposit"))
    deposit_total = booking.get("depositTotal") or 0
    deposit_note = (
        f"<p>需訂金：NT$ {deposit_total}。此訂位已先保留，請回到 ByteBites 後續完成付款流程。</p>"
        if needs_deposit
        else "<p>免訂金，已直接建立訂位。</p>"
    )
    detail_uri = _line_public_uri(f"/line/shop/{shop_id}")
    body = f"""
      <main>
        <p class="eyebrow">ByteBites 訂位完成</p>
        <h1>{name}</h1>
        <section>
          <h2>訂位資訊</h2>
          <p>訂位編號：<strong>{booking_code}</strong></p>
          <p>{_html_escape(date)} {_html_escape(time)} · {people} 人</p>
          <p>狀態：{status}</p>
          {deposit_note}
        </section>
        <a class="primary" href="{detail_uri}">查看店家資訊</a>
      </main>
    """
    return HTMLResponse(_line_shell(f"{name} 訂位完成", body))


async def _build_line_more_recommendations(user_text: str, user_id: str) -> list[dict] | None:
    if not _line_more_recommendation_intent(user_text):
        return None
    state = _load_line_recommendation_state(user_id)
    previous_query = str(state.get("query") or "").strip()
    if not previous_query:
        return [build_text_message("可以，請先告訴我想找的地點和類型，例如「信義區火鍋」或「中山站聚餐」。")]

    seen_ids = {
        int(shop_id)
        for shop_id in state.get("shown_shop_ids", [])
        if str(shop_id).isdigit()
    }
    try:
        shops = await _semantic_hits(previous_query, top_k=30)
    except Exception:
        logger.exception("line_more_search_failed user_id=%s query=%s", user_id, previous_query)
        return [build_text_message("我暫時無法取得更多餐廳，請稍後再試一次。")]

    remaining = [
        shop
        for shop in shops
        if (sid := _shop_id(shop)) is not None and sid not in seen_ids
    ]
    seen_brands = {
        _shop_brand_key(shop).lower()
        for shop in shops
        if (sid := _shop_id(shop)) is not None and sid in seen_ids
    }
    remaining = [
        shop
        for shop in remaining
        if not (brand := _shop_brand_key(shop).lower()) or brand not in seen_brands
    ]
    remaining = _dedupe_shops_by_brand(remaining)
    if not remaining:
        return [build_text_message("目前同一個條件下沒有更多明顯符合的餐廳了。你可以放寬地區或換一個類型，我再幫你找。")]

    selected_ids = [
        int(sid)
        for shop in remaining[:3]
        if (sid := _shop_id(shop)) is not None
    ]
    _save_line_recommendation_state(
        user_id,
        query=previous_query,
        shown_shop_ids=[*seen_ids, *selected_ids],
    )
    flex_or_bundle = build_line_flex_message(
        shops=remaining,
        recommended_shop_ids=selected_ids,
        answer="",
        public_web_url=settings.line_public_web_url,
    )
    messages = flex_or_bundle.get("messages") if flex_or_bundle.get("type") == "_bundle" else [flex_or_bundle]
    return messages or [build_text_message("我找到更多候選，但 LINE 卡片暫時無法產生，請再試一次。")]


def _line_more_recommendation_intent(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    return any(
        phrase in normalized
        for phrase in (
            "還有嗎",
            "還有沒有",
            "還有其他",
            "更多",
            "別家",
            "其他家",
            "不要這",
            "不想要這",
            "換一家",
            "換幾家",
            "只有",
            "才1家",
            "才2家",
            "才3家",
            "才 1 家",
            "才 2 家",
            "才 3 家",
            "重複",
            "不要重複",
        )
    )


def _line_should_force_recommendation_cards(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    if _booking_intent(normalized) or _payment_intent(normalized):
        return False
    if not any(
        phrase in normalized
        for phrase in ("推薦", "找", "想吃", "想找", "哪間", "哪家", "餐廳")
    ):
        return False

    constraints = _extract_query_constraints(normalized)
    has_food_or_place = bool(
        constraints["categories"]
        or constraints["districts"]
        or constraints["stations"]
        or constraints["wants_luxury"]
        or constraints["wants_hot_seat"]
    )
    return has_food_or_place


async def _build_line_fallback_recommendation_cards(user_text: str, user_id: str) -> list[dict] | None:
    if not _line_should_force_recommendation_cards(user_text):
        return None
    try:
        shops = await _semantic_hits(user_text, top_k=30)
    except Exception:
        logger.exception("line_fallback_search_failed user_id=%s query=%s", user_id, user_text)
        return None
    if not shops:
        return None

    selected_ids = [
        int(sid)
        for shop in _dedupe_shops_by_brand(shops)[:3]
        if (sid := _shop_id(shop)) is not None
    ]
    if not selected_ids:
        return None

    _save_line_recommendation_state(user_id, query=user_text, shown_shop_ids=selected_ids)
    flex_or_bundle = build_line_flex_message(
        shops=shops,
        recommended_shop_ids=selected_ids,
        answer="",
        public_web_url=settings.line_public_web_url,
    )
    messages = flex_or_bundle.get("messages") if flex_or_bundle.get("type") == "_bundle" else [flex_or_bundle]
    return messages or None


def _line_plain_text(text: str) -> str:
    kept: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "|" in line or ":---" in line:
            continue
        kept.append(line)
    cleaned = " ".join(kept).replace("**", "").replace("__", "")
    cleaned = " ".join(cleaned.split())
    return cleaned or "我先幫你整理符合需求的餐廳，請看下方卡片。"


def _line_recommendation_state_key(user_id: str) -> str:
    return f"line:recommendation:{user_id}"


def _load_line_recommendation_state(user_id: str) -> dict:
    try:
        raw = session_store.client().get(_line_recommendation_state_key(user_id))
    except Exception:
        logger.exception("line_recommendation_state_load_failed user_id=%s", user_id)
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _clear_line_recommendation_state(user_id: str) -> None:
    try:
        session_store.client().delete(_line_recommendation_state_key(user_id))
    except Exception:
        logger.exception("line_recommendation_state_clear_failed user_id=%s", user_id)


def _save_line_recommendation_state(user_id: str, query: str, shown_shop_ids: list[int]) -> None:
    deduped: list[int] = []
    for shop_id in shown_shop_ids:
        try:
            sid = int(shop_id)
        except (TypeError, ValueError):
            continue
        if sid not in deduped:
            deduped.append(sid)
    try:
        session_store.client().setex(
            _line_recommendation_state_key(user_id),
            LINE_RECOMMENDATION_TTL_SECONDS,
            json.dumps(
                {"query": query, "shown_shop_ids": deduped[-60:]},
                ensure_ascii=False,
            ),
        )
    except Exception:
        logger.exception("line_recommendation_state_save_failed user_id=%s", user_id)


def _line_location_state_key(user_id: str) -> str:
    return f"line:location:{user_id}"


def _load_line_location_state(user_id: str) -> dict:
    try:
        raw = session_store.client().get(_line_location_state_key(user_id))
    except Exception:
        logger.exception("line_location_state_load_failed user_id=%s", user_id)
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_line_location_state(user_id: str, message: dict) -> dict:
    state = {
        "title": str(message.get("title") or "").strip(),
        "address": str(message.get("address") or "").strip(),
        "latitude": message.get("latitude"),
        "longitude": message.get("longitude"),
    }
    try:
        session_store.client().setex(
            _line_location_state_key(user_id),
            LINE_LOCATION_TTL_SECONDS,
            json.dumps(state, ensure_ascii=False),
        )
    except Exception:
        logger.exception("line_location_state_save_failed user_id=%s", user_id)
    return state


def _line_effective_text_with_location(user_text: str, location_state: dict) -> str:
    location_text = _line_location_text(location_state)
    if not location_text:
        return user_text
    if _line_text_has_explicit_location(user_text):
        return user_text
    return f"{location_text}附近，{user_text}"


def _line_location_text(location_state: dict) -> str:
    address = str(location_state.get("address") or "").strip()
    title = str(location_state.get("title") or "").strip()
    if address:
        return address
    if title and title != "你分享的位置":
        return title
    return ""


def _line_text_has_explicit_location(text: str) -> bool:
    return bool(
        re.search(
            r"(台北|新北|基隆|桃園|新竹|台中|台南|高雄|宜蘭|花蓮|台東|澎湖|金門|馬祖|"
            r"[^\s，,。；;]{1,8}(區|市|縣|站|路|街|巷|商圈|夜市|百貨|附近))",
            text,
        )
    )


async def _build_line_contextual_followup(user_text: str, user_id: str) -> list[dict] | None:
    state = _load_line_recommendation_state(user_id)
    previous_query = str(state.get("query") or "").strip()
    if _line_cancel_context_intent(user_text):
        _clear_line_recommendation_state(user_id)
        return [build_text_message("好，我先清掉剛剛的推薦條件。你可以重新告訴我想找什麼餐廳。")]
    if _line_status_intent(user_text):
        if previous_query:
            return [build_text_message("剛剛的推薦已經整理完成。你可以回「還有嗎」看更多，或直接說想調整的條件。")]
        return [build_text_message("目前沒有正在整理的推薦。你可以直接告訴我地點和想吃的類型。")]
    if not previous_query or not _line_adjustment_intent(user_text):
        return None

    adjusted_query = _line_merge_followup_query(previous_query, user_text)
    try:
        shops = await _semantic_hits(adjusted_query, top_k=30)
    except Exception:
        logger.exception("line_contextual_followup_search_failed user_id=%s query=%s", user_id, adjusted_query)
        return [build_text_message("我暫時無法依新條件重新整理，請稍後再試一次。")]
    if not shops:
        return [build_text_message("這個調整後暫時找不到明顯符合的餐廳。可以再放寬地點、價位或料理類型。")]

    seen_ids = {
        int(shop_id)
        for shop_id in state.get("shown_shop_ids", [])
        if str(shop_id).isdigit()
    }
    deduped = _dedupe_shops_by_brand(shops)
    selected_ids = [
        int(sid)
        for shop in deduped[:3]
        if (sid := _shop_id(shop)) is not None
    ]
    if not selected_ids:
        return [build_text_message("我有找到候選，但暫時無法整理成 LINE 卡片，請再換個條件試試。")]

    _save_line_recommendation_state(
        user_id,
        query=adjusted_query,
        shown_shop_ids=[*seen_ids, *selected_ids],
    )
    flex_or_bundle = build_line_flex_message(
        shops=shops,
        recommended_shop_ids=selected_ids,
        answer="",
        public_web_url=settings.line_public_web_url,
    )
    messages = flex_or_bundle.get("messages") if flex_or_bundle.get("type") == "_bundle" else [flex_or_bundle]
    return messages or [build_text_message("我已依新條件重新整理，但 LINE 卡片暫時無法產生，請再試一次。")]


async def _build_line_agent_recommendation_messages(
    user_text: str,
    user_id: str,
) -> list[dict]:
    try:
        check_input(user_text)
        answer, _tools_used, tool_result = await _run_agent_turn(user_text, f"line:{user_id}")
    except GuardrailViolation:
        return [build_text_message("這個內容我不能協助處理。可以換一個餐廳或訂位相關的問法。")]
    except Exception:
        logger.exception("line_agent_failed user_id=%s text=%s", user_id, user_text)
        return [build_text_message("AI 目前暫時無法完成推薦，請稍後再試一次，或換個地點 / 條件重新輸入。")]

    shops = tool_result.get("shops") if isinstance(tool_result, dict) else None
    if isinstance(shops, list) and shops:
        recommended_ids = tool_result.get("agent_decision", {}).get("recommended_shop_ids")
        flex_or_bundle = build_line_flex_message(
            shops=shops,
            recommended_shop_ids=recommended_ids if isinstance(recommended_ids, list) else None,
            answer=answer,
            public_web_url=settings.line_public_web_url,
        )
        if flex_or_bundle.get("type") == "_bundle":
            messages = flex_or_bundle.get("messages") or []
        else:
            messages = [flex_or_bundle]
        shown_ids = (
            [int(shop_id) for shop_id in recommended_ids if str(shop_id).isdigit()]
            if isinstance(recommended_ids, list)
            else [
                int(sid)
                for shop in shops[:3]
                if (sid := _shop_id(shop)) is not None
            ]
        )
        _save_line_recommendation_state(user_id, query=user_text, shown_shop_ids=shown_ids)
        if messages:
            return messages

    fallback_messages = await _build_line_fallback_recommendation_cards(user_text, user_id)
    if fallback_messages:
        return fallback_messages

    return [build_text_message(_line_plain_text(answer or "我需要再多一點條件，才能幫你推薦餐廳。"))]


def _line_should_start_background_recommendation(source: dict, user_text: str) -> bool:
    if not settings.line_background_push_enabled:
        return False
    if source.get("type") != "user":
        return False
    if _booking_intent(user_text) or _payment_intent(user_text):
        return False
    return _line_should_force_recommendation_cards(user_text)


def _start_line_background_recommendation(user_id: str, user_text: str) -> None:
    asyncio.create_task(_run_line_background_recommendation(user_id=user_id, user_text=user_text))


async def _run_line_background_recommendation(user_id: str, user_text: str) -> None:
    await show_loading_animation(
        user_id=user_id,
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled,
        loading_seconds=60,
    )
    messages = await _build_line_agent_recommendation_messages(user_text, user_id)
    result = await push_messages(
        user_id=user_id,
        messages=messages,
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled,
    )
    logger.info(
        "line_background_recommendation_pushed user_id=%s ok=%s status_code=%s",
        user_id,
        result.get("ok"),
        result.get("status_code"),
    )


def _line_cancel_context_intent(text: str) -> bool:
    normalized = str(text or "").strip()
    return normalized in {"取消", "不用了", "先不用", "算了", "不要找了", "停止", "先不要"}


def _line_status_intent(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(phrase in normalized for phrase in ("好了嗎", "還在找嗎", "有結果了嗎", "推薦好了嗎", "怎麼還沒好"))


def _line_adjustment_intent(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if _line_more_recommendation_intent(normalized):
        return False
    return any(
        phrase in normalized
        for phrase in (
            "改成",
            "改吃",
            "換成",
            "不要吃",
            "不吃",
            "不要太",
            "不要有",
            "高級一點",
            "精緻一點",
            "便宜一點",
            "平價一點",
            "近一點",
            "安靜一點",
            "適合聊天",
            "適合約會",
            "適合聚餐",
            "有包廂",
            "不要吃到飽",
        )
    ) or bool(re.match(r"^(改|換)(到|去)?[^\s，,。；;]{1,12}(區|站|路|街|商圈|附近)", normalized))


def _line_merge_followup_query(previous_query: str, user_text: str) -> str:
    normalized = str(user_text or "").strip()
    if not normalized:
        return previous_query
    if re.match(r"^(改成|換成|改吃|換吃)", normalized):
        return f"{previous_query}，調整需求：{normalized}"
    if normalized.startswith(("不要", "不吃")):
        return f"{previous_query}，排除條件：{normalized}"
    return f"{previous_query}，補充條件：{normalized}"


async def _build_line_reply_messages(event: dict) -> list[dict]:
    event_type = event.get("type")
    source = event.get("source") or {}
    user_id = str(source.get("userId") or "anonymous-line-user")

    if event_type == "follow":
        return [
            build_text_message(
                "嗨，我是 ByteBites AI。你可以直接傳「信義區想吃火鍋」「中山站適合聚餐」這類需求，我會回你 3 張餐廳推薦卡。"
            )
        ]

    if event_type != "message":
        return []

    message = event.get("message") or {}
    message_type = message.get("type")
    if message_type == "location":
        state = _save_line_location_state(user_id, message)
        title = state.get("title") or "你分享的位置"
        address = state.get("address") or ""
        return [
            build_text_message(
                f"我收到位置了：{title} {address}\n接著告訴我想吃什麼或用餐情境，我會用這個位置附近幫你找。"
            )
        ]
    if message_type != "text":
        return [build_text_message("目前先支援文字與位置訊息。你可以直接告訴我想吃什麼、在哪裡、幾個人。")]

    user_text = str(message.get("text") or "").strip()
    if not user_text:
        return [build_text_message("我沒看到文字內容，可以再傳一次餐廳需求嗎？")]
    effective_user_text = _line_effective_text_with_location(
        user_text,
        _load_line_location_state(user_id),
    )

    contextual_messages = await _build_line_contextual_followup(user_text, user_id)
    if contextual_messages is not None:
        return contextual_messages

    more_messages = await _build_line_more_recommendations(user_text, user_id)
    if more_messages is not None:
        return more_messages

    if _line_should_start_background_recommendation(source, effective_user_text):
        _start_line_background_recommendation(user_id, effective_user_text)
        return [
            build_text_message(
                "收到，我正在幫你整理符合條件的餐廳。完成後會直接把推薦卡片傳給你。"
            )
        ]

    if source.get("type") == "user":
        await show_loading_animation(
            user_id=user_id,
            channel_access_token=settings.line_channel_access_token,
            enabled=settings.line_reply_enabled,
            loading_seconds=20,
        )

    return await _build_line_agent_recommendation_messages(effective_user_text, user_id)


async def _fetch_java_shop(shop_id: int) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.java_backend_url}/api/shop/{shop_id}")
        if response.status_code != 200:
            return None
        payload = response.json()
        data = payload.get("data")
        return data if isinstance(data, dict) else None
    except Exception:
        logger.exception("line_shop_fetch_failed shop_id=%s", shop_id)
        return None


async def _fetch_java_ai_metadata(shop_id: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.java_backend_url}/api/shop/{shop_id}/ai-metadata")
        if response.status_code != 200:
            return {}
        payload = response.json()
        data = payload.get("data")
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("line_shop_metadata_fetch_failed shop_id=%s", shop_id)
        return {}


async def _fetch_java_booking_policy(shop_id: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.java_backend_url}/api/shop/{shop_id}/booking-policy")
        if response.status_code != 200:
            return {}
        payload = response.json()
        data = payload.get("data")
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("line_booking_policy_fetch_failed shop_id=%s", shop_id)
        return {}


def _validate_line_booking(people: int, booking_date: str, booking_time: str, table_type: str) -> str | None:
    if people < 1 or people > 12:
        return "訂位人數需介於 1 到 12 人。"
    try:
        parsed_date = date_cls.fromisoformat(str(booking_date))
    except ValueError:
        return "日期格式不正確，請重新選擇。"
    if parsed_date <= taipei_today():
        return "今天不可訂位，最早可訂明天。"
    try:
        datetime.strptime(str(booking_time), "%H:%M")
    except ValueError:
        return "時間格式不正確，請重新選擇。"
    if table_type not in {"normal", "bar", "private"}:
        return "座位類型不正確，請重新選擇。"
    return None


async def _reserve_line_booking(shop_id: int, people: int, booking_date: str, booking_time: str, table_type: str) -> dict:
    idempotency_key = f"line-form:{shop_id}:{people}:{booking_date}:{booking_time}:{table_type}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{settings.java_backend_url}/api/booking/reserve",
                headers={"X-Demo-Mode": "true"},
                json={
                    "shopId": shop_id,
                    "people": people,
                    "date": booking_date,
                    "time": booking_time,
                    "tableType": table_type,
                    "idempotencyKey": idempotency_key,
                },
            )
    except Exception:
        logger.exception("line_booking_reserve_failed shop_id=%s", shop_id)
        return {"success": False, "errorMsg": "後端訂位服務暫時無法連線，請稍後再試。"}
    try:
        payload = response.json()
    except Exception:
        return {"success": False, "errorMsg": "後端訂位服務回傳格式異常。"}
    if response.status_code >= 400:
        return {"success": False, "errorMsg": payload.get("errorMsg") or "後端訂位服務暫時無法完成。"}
    return payload


def _line_deposit_summary(policy: dict) -> str:
    if not policy:
        return "目前無法取得訂金政策，送出訂位後會以系統回覆為準。"
    if policy.get("needsDeposit"):
        per_person = policy.get("depositPerPerson") or 0
        reason = str(policy.get("reason") or "此店需保留訂金")
        return f"需訂金：NT$ {per_person} / 人。原因：{reason}。"
    reason = str(policy.get("reason") or "免訂金")
    return f"免訂金。原因：{reason}。"


def _line_media_payload() -> dict:
    global _LINE_MEDIA_CACHE
    if _LINE_MEDIA_CACHE is not None:
        return _LINE_MEDIA_CACHE
    path = Path(__file__).resolve().parents[2] / "web" / "data" / "shop-media.json"
    try:
        _LINE_MEDIA_CACHE = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _LINE_MEDIA_CACHE = {}
    return _LINE_MEDIA_CACHE


def _line_media_shop(shop_id: int) -> dict:
    shop = (_line_media_payload().get("shops") or {}).get(str(shop_id))
    return shop if isinstance(shop, dict) else {}


def _line_photo_candidates(shop_id: int) -> list[str]:
    candidates: list[str] = []
    best = best_shop_photo_url(shop_id)
    if best:
        candidates.append(best)
    shop = _line_media_shop(shop_id)
    for key in ("galleryUrls", "photoUrls"):
        urls = shop.get(key)
        if isinstance(urls, list):
            candidates.extend(str(url) for url in urls if url)
    return _dedupe_text(candidates)


def _line_detail_summary(shop: dict, metadata: dict, manifest_shop: dict) -> str:
    explicit = str(metadata.get("aiSummary") or metadata.get("highlightReview") or "").strip()
    if explicit:
        return explicit
    positive = _line_review_groups(int(shop.get("id") or shop.get("shop_id") or 0)).get("positive") or []
    if positive:
        return _truncate_words(str(positive[0].get("text") or ""), 150)
    overview = manifest_shop.get("overview") if isinstance(manifest_shop, dict) else {}
    price_overview = str((overview or {}).get("price_overview") or "").strip()
    if price_overview:
        return f"依據 Google 資訊與評論整理，這間店的價位輪廓為：{price_overview}。"
    category = _category_from_shop(shop)
    district = str(shop.get("district") or "台北").strip()
    return f"{district}{category or '餐廳'}候選店。建議先比較評論重點、營業時間與訂位規則，再決定是否訂位。"


def _line_recommendation_basis(shop: dict, metadata: dict, manifest_shop: dict) -> list[str]:
    basis: list[str] = []
    dishes = _parse_json_list(metadata.get("signatureDishes"))[:3]
    tags = _parse_json_list(metadata.get("atmosphereTags"))[:3]
    if dishes:
        basis.append("招牌與評論常見菜色：" + "、".join(dishes))
    if tags:
        basis.append("用餐情境標籤：" + "、".join(tags))
    rating = shop.get("score") or shop.get("rating")
    comments = shop.get("comments") or shop.get("reviewCount")
    if rating and comments:
        basis.append(f"Google 評分 {rating}，累積 {comments} 則評論，可作為穩定度參考。")
    overview = manifest_shop.get("overview") if isinstance(manifest_shop, dict) else {}
    buckets = (overview or {}).get("price_buckets")
    if isinstance(buckets, list) and buckets:
        basis.append("評論價位落點：" + "、".join(str(item) for item in buckets[:3]))
    if not basis:
        basis.append("依照店家地點、類型與可取得評論資料整理為本次候選。")
    return basis


def _line_review_groups(shop_id: int) -> dict[str, list[dict]]:
    shop = _line_media_shop(shop_id)
    reviews = shop.get("reviews") if isinstance(shop, dict) else []
    if not isinstance(reviews, list):
        return {"positive": [], "critical": []}
    critical = [r for r in reviews if 0 < _line_review_rating(r) <= 3 and r.get("text")]
    positive = [r for r in reviews if _line_review_rating(r) >= 4 and r.get("text")]
    if not critical:
        critical = [r for r in reviews if _line_review_rating(r) == 4 and r.get("text")]
    return {"positive": positive[:2], "critical": critical[:2]}


def _line_review_rating(review: dict) -> float:
    try:
        return float(review.get("rating") or 0)
    except (TypeError, ValueError):
        return 0.0


def _line_review_html(review_groups: dict[str, list[dict]]) -> str:
    positive = review_groups.get("positive") or []
    critical = review_groups.get("critical") or []
    if not positive and not critical:
        return "<section><h2>精選正負評</h2><p>目前沒有足夠評論可整理，建議先查看 Google 地圖評論再決定。</p></section>"
    cards = []
    for label, reviews in (("正面摘要", positive), ("需要留意", critical)):
        for review in reviews:
            cards.append(_line_review_card_html(label, review))
    return f"<section><h2>精選正負評</h2>{''.join(cards)}</section>"


def _line_review_card_html(label: str, review: dict) -> str:
    rating = int(_line_review_rating(review))
    text = _html_escape(_truncate_words(str(review.get("text") or ""), 90))
    author = _html_escape(str(review.get("author") or "Google 評論"))
    return f'<div class="review"><div><strong>{label}</strong> · {author} · {"★" * rating}</div><p>{text}</p></div>'


def _line_bullet_html(items: list[str]) -> str:
    clean = [_html_escape(str(item)) for item in items if str(item).strip()]
    if not clean:
        return "<p>目前資料不足，建議先查看評論與店家資訊。</p>"
    return '<ul class="bullets">' + "".join(f"<li>{item}</li>" for item in clean[:5]) + "</ul>"


def _line_pills_html(items: list[str]) -> str:
    clean = [_html_escape(str(item)) for item in items if str(item).strip()]
    if not clean:
        return ""
    return '<div class="pills">' + "".join(f"<span>{item}</span>" for item in clean[:6]) + "</div>"


def _line_hours_html(hours: list[str]) -> str:
    clean = [_html_escape(str(item)) for item in hours if str(item).strip()]
    if not clean:
        return '<div class="hours"><p>營業時間資料未標示</p></div>'
    return '<div class="hours">' + "".join(f"<p>{item}</p>" for item in clean[:7]) + "</div>"


def _line_public_uri(path: str) -> str:
    base = settings.line_public_web_url.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def _line_google_maps_uri(name: str, address: str) -> str:
    query = " ".join(part for part in [name.strip(), address.strip()] if part)
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query or name or address or '台北餐廳')}"


def _category_from_shop(shop: dict) -> str:
    type_id = shop.get("typeId") or shop.get("type_id")
    try:
        slug = TYPE_ID_TO_CATEGORY.get(int(type_id))
    except (TypeError, ValueError):
        slug = None
    return {
        "hotpot": "火鍋",
        "yakiniku": "燒肉",
        "izakaya": "居酒屋",
        "japanese": "日式料理",
        "american": "美式料理",
        "euro": "義法料理",
        "chinese": "中式料理",
        "korean": "韓式料理",
        "vegetarian": "蔬食",
        "cafe": "咖啡甜點",
    }.get(slug or "", "")


def _dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _truncate_words(text: str, max_length: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_length:
        return clean
    return clean[: max_length - 1].rstrip() + "…"


def _line_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Cache-Control" content="no-store">
  <meta http-equiv="Pragma" content="no-cache">
  <title>{_html_escape(title)}</title>
  <style>
    body {{ margin:0; background:#f7f3ec; color:#171512; font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif; }}
    .hero {{ position:relative; width:100%; aspect-ratio:16/10; overflow:hidden; background:#e8e1d5; }}
    .hero img {{ width:100%; height:100%; object-fit:cover; display:block; }}
    .hero span {{ display:none; }}
    .hero-fallback {{ display:flex; align-items:center; justify-content:center; color:#16833a; font-size:18px; font-weight:900; letter-spacing:0; }}
    .hero-fallback span {{ display:block; }}
    main {{ padding:24px 20px 36px; }}
    .eyebrow {{ margin:0 0 8px; color:#16833a; font-size:12px; font-weight:800; letter-spacing:0; }}
    h1 {{ margin:0; font-size:30px; line-height:1.18; letter-spacing:0; }}
    h2 {{ margin:0 0 8px; font-size:16px; }}
    .meta {{ margin-top:10px; color:#6f6a62; font-weight:700; }}
    section {{ margin-top:22px; padding:16px; border:1px solid rgba(0,0,0,.08); border-radius:8px; background:rgba(255,255,255,.72); }}
    p {{ line-height:1.7; }}
    a {{ color:#16833a; font-weight:800; text-decoration:none; }}
    .pills {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
    .pills span {{ border-radius:999px; background:#eaf4ec; color:#16833a; font-size:12px; font-weight:900; padding:6px 10px; }}
    .bullets {{ margin:10px 0 0; padding-left:18px; line-height:1.65; }}
    .bullets li + li {{ margin-top:6px; }}
    .review {{ margin-top:12px; padding-left:12px; border-left:3px solid #f1c45c; }}
    .review p {{ margin:6px 0 0; color:#514d47; }}
    .hours p {{ margin:4px 0; }}
    .status-list p {{ margin:6px 0; }}
    .booking-form {{ display:grid; gap:14px; margin-top:12px; }}
    label {{ display:grid; gap:6px; color:#514d47; font-size:13px; font-weight:800; }}
    input, select {{ min-height:48px; border:1px solid rgba(0,0,0,.14); border-radius:8px; background:#fff; color:#171512; font:inherit; font-size:16px; padding:0 12px; }}
    button {{ border:0; font:inherit; cursor:pointer; }}
    .actions {{ display:grid; gap:10px; margin-top:22px; }}
    .primary, .secondary {{ display:flex; align-items:center; justify-content:center; min-height:52px; border-radius:8px; font-weight:900; text-decoration:none; width:100%; box-sizing:border-box; }}
    main > .primary, main > .secondary {{ margin-top:22px; }}
    .primary {{ background:#16833a; color:#fff; }}
    .secondary {{ background:#e3e5e9; color:#171512; }}
    strong {{ font-weight:900; }}
  </style>
</head>
<body>{body}</body>
</html>"""


def _line_html_page(title: str, message: str, links: list[tuple[str, str]]) -> str:
    link_html = "".join(f'<a class="primary" href="{_html_escape(href)}">{_html_escape(label)}</a>' for label, href in links)
    return _line_shell(title, f"<main><h1>{_html_escape(title)}</h1><p>{_html_escape(message)}</p>{link_html}</main>")


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


@app.delete("/api/ai/session/{session_id}")
async def clear_chat_session(session_id: str):
    """清除 Redis 對話歷史。"""
    session_store.clear_session(session_id)
    return {"success": True, "session_id": session_id}
