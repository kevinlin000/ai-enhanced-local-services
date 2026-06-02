import json
import logging
import httpx
from typing import AsyncIterator
from app import session_store
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from app.guardrail import GuardrailViolation, check_input, filter_output
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
    "izakaya": {"居酒屋", "串燒", "宵夜", "下酒"},
    "japanese": {"日料", "日本料理", "壽司", "拉麵", "懷石"},
    "omakase": {"無菜單", "omakase"},
    "steakhouse": {"牛排", "排餐", "steak"},
    "european": {"義式", "法式", "義法", "歐陸", "義大利麵"},
    "chinese": {"中菜", "中式", "台菜", "熱炒", "烤鴨", "港式", "粵菜"},
    "korean": {"韓式", "韓國料理", "豆腐鍋"},
    "brunch": {"brunch", "早午餐", "美式", "漢堡"},
    "fine-dining": {"高級餐廳", "高檔餐廳", "fine dining", "精緻料理", "鐵板燒"},
    "cafe-premium": {"咖啡", "咖啡廳", "下午茶", "甜點"},
}

CATEGORY_FALLBACK_KEYWORDS = {
    "hotpot": {"火鍋", "鍋物", "麻辣鍋", "酸菜白肉鍋", "涮涮屋", "涮涮鍋", "壽喜燒", "羊肉爐", "湯頭", "鴛鴦鍋", "鍋底"},
    "yakiniku": {"燒肉", "烤肉", "牛舌", "和牛燒肉"},
    "izakaya": {"居酒屋", "串燒", "烤串", "酒場"},
    "japanese": {"壽司", "生魚片", "拉麵", "天婦羅", "鰻魚飯"},
    "omakase": {"無菜單", "板前", "omakase"},
    "steakhouse": {"牛排", "肋眼", "菲力", "排餐"},
    "european": {"義大利麵", "燉飯", "牛小排燉飯", "法式", "歐陸"},
    "chinese": {"台菜", "熱炒", "烤鴨", "粵菜", "港點", "中菜"},
    "korean": {"韓式", "豆腐鍋", "炸雞", "石鍋拌飯"},
    "brunch": {"早午餐", "brunch", "漢堡", "班尼迪克蛋"},
    "fine-dining": {"fine dining", "高級餐廳", "高檔餐廳", "套餐", "品酒", "鐵板燒"},
    "cafe-premium": {"咖啡", "拿鐵", "手沖", "甜點"},
}

STATION_HINTS = {
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
}

STATION_NEIGHBORHOODS = {
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
            stations.append(canonical.replace("站", ""))

    districts = []
    for canonical, keywords in DISTRICT_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            districts.append(canonical)

    categories = []
    for category, keywords in CATEGORY_HINTS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            categories.append(category)

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


def _category_slug_from_payload(payload: dict) -> str:
    explicit_slug = str(payload.get("category_slug") or "").lower()
    if explicit_slug:
        return explicit_slug

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
        return "steakhouse"
    if "義法" in category:
        return "european"
    if "中式" in category:
        return "chinese"
    if "韓式" in category:
        return "korean"
    if "brunch" in category or "美式" in category:
        return "brunch"
    if "高級" in category:
        return "fine-dining"
    if "咖啡" in category:
        return "cafe-premium"
    return ""


def _semantic_category_slug(payload: dict) -> str:
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


def _has_hotpot_semantics(payload: dict) -> bool:
    text = _payload_text(payload)
    has_strong_hint = any(keyword.lower() in text for keyword in HOTPOT_STRONG_HINTS)
    has_block_hint = any(keyword.lower() in text for keyword in HOTPOT_BLOCK_HINTS)
    if has_strong_hint:
        return True
    if has_block_hint:
        return False
    return any(keyword.lower() in text for keyword in CATEGORY_FALLBACK_KEYWORDS["hotpot"])


def _premium_hotpot_key(constraints: dict, hit: dict) -> tuple[int, int, float, int, int, int, int, float]:
    avg_price = hit.get("avg_price") or 0
    booking = str(hit.get("booking_difficulty") or "")
    tags = set(hit.get("atmosphere_tags") or [])
    text = _payload_text(hit)
    station_score = _station_proximity_score(constraints, hit)
    district_match = 1 if any(
        target.lower() == str(hit.get("district") or "").lower()
        for target in constraints["districts"]
    ) else 0
    has_premium_cues = 1 if any(
        keyword in text for keyword in ("和牛", "a5", "套餐", "預約困難", "提前訂位", "無菜單", "松葉蟹", "龍蝦")
    ) else 0
    premium_price = 1 if avg_price >= 1000 else 0
    mid_price = 1 if avg_price >= 800 else 0
    hard_to_book = 1 if ("困難" in booking or "提前" in booking) else 0
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
        hard_to_book,
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
        if any(target.lower() == district for target in constraints["districts"]):
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
            limit=max(top_k * 4, 12),
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

    shop_ids = [hit["shop_id"] for hit in raw_hits if hit["shop_id"]]
    voucher_map = await _fetch_hot_seat_vouchers(shop_ids)
    for hit in raw_hits:
        hit["hot_seat_vouchers"] = voucher_map.get(hit["shop_id"], [])
        hit["rerank_score"] = hit["score"] + _metadata_bonus(query, hit) + _fallback_keyword_score(query, hit)

    constraints = _extract_query_constraints(query)
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
        def luxury_score(hit: dict) -> tuple[int, int, float, int, int, int, int, float]:
            if requested_hotpot:
                return _premium_hotpot_key(constraints, hit)

            avg_price = hit.get("avg_price") or 0
            booking = str(hit.get("booking_difficulty") or "")
            tags = set(hit.get("atmosphere_tags") or [])
            station_score = _station_proximity_score(constraints, hit)
            district_match = 1 if any(
                target.lower() == str(hit.get("district") or "").lower()
                for target in constraints["districts"]
            ) else 0
            return (
                0,
                1 if avg_price >= 1000 else 0,
                station_score,
                district_match,
                1 if ("困難" in booking or "提前" in booking) else 0,
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
            return _station_proximity_score(constraints, hit) > 0 or any(
                target.lower() == str(hit.get("district") or "").lower()
                for target in constraints["districts"]
            )

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
            district = str(hit.get("district") or "").lower()
            station_match = _station_proximity_score(constraints, hit) > 0 or any(
                s.lower() in mrt for s in constraints["stations"]
            )
            district_match = any(
                d.lower() in district for d in constraints["districts"]
            )
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
) -> dict:
    """建立訂位記錄，回 bookingCode + needsDeposit + depositTotal。"""
    from datetime import date as date_cls, timedelta

    if not date:
        date = (date_cls.today() + timedelta(days=1)).isoformat()
    else:
        try:
            requested_date = date_cls.fromisoformat(date)
            if requested_date < date_cls.today():
                date = (date_cls.today() + timedelta(days=1)).isoformat()
        except ValueError:
            date = (date_cls.today() + timedelta(days=1)).isoformat()
    if not time:
        time = "19:00"

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{settings.java_backend_url}/api/booking/reserve",
            json={"shopId": shop_id, "people": people, "date": date, "time": time, "tableType": table_type},
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
                "description": "查詢指定捷運站附近的店家。當使用者提到特定捷運站名（如「市政府」「中山」「信義安和」）時使用。",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "station": {
                            "type": "STRING",
                            "description": "捷運站名，例如「市政府」「中山」",
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
僅在 create_booking 回應 needsDeposit=true 時呼叫。
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
- 若回應 needsDeposit=true → 主動呼叫 pay_booking_with_test_card 完成付款
- 若 needsDeposit=false → 訂位完成、不要付款
- 一次對話最多 1 個 booking，不要重複建立
- 訂位完成後，回應要包含 bookingCode，若有付款也要包含 rec_trade_id

==== Hot Seat 搶位流程（create_hot_seat_order）====
- 用戶說「幫我搶」「搶位」「想搶熱座」→ 呼叫 create_hot_seat_order
- 若不知道 voucher_id，先 semantic_shop_search 找到 hot_seat_vouchers，再取其中一個 id
- 訂單成功後，回應要包含 voucher_order_id，並提示用戶到「我的訂單」查看
- 一個 query 最多訂 1 個 Hot Seat 方案

==== 通用規則 ====
- 不要主動下單，除非用戶明確表示要訂
- 一個 query 最多執行 1 次訂位動作"""


def _agent_system_prompt() -> str:
    from datetime import date as date_cls

    return (
        f"今天日期：{date_cls.today().isoformat()}（Asia/Taipei）。"
        "解析「今天」「明天」「下週」等相對日期時必須以此為準。"
        "禁止建立過去日期訂位；若不確定日期，使用明天。\n\n"
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
        "rec_trade_id": (payment_result or {}).get("rec_trade_id"),
        "payment_amount": (payment_result or {}).get("amount"),
        "payment_note": (payment_result or {}).get("note"),
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

    shop_name = transaction.get("shop_name") or f"店家 ID {transaction.get('shop_id')}"
    base = [
        "訂位已完成。",
        "",
        f"- 店家：{shop_name}",
        f"- 人數：{transaction.get('people')} 人",
        f"- 時間：{transaction.get('date')} {transaction.get('time')}",
        f"- 訂位編號：`{transaction.get('booking_code')}`",
    ]
    if transaction.get("needs_deposit"):
        base.extend(
            [
                f"- 訂金：NT$ {transaction.get('deposit_total')}",
                f"- 付款交易編號：`{transaction.get('rec_trade_id')}`",
            ]
        )
    else:
        base.append("- 訂金：免訂金，已直接確認")
    return "\n".join(base)


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
  "narrative": "user-facing markdown in Traditional Chinese",
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


async def _run_agent_turn(query: str, session_id: str) -> tuple[str, list[str], dict]:
    history = session_store.load_history(session_id) if session_id else []
    contents = _history_to_contents(history, query)

    tools_used: list[str] = []
    last_tool_result: dict = {}
    final_answer = ""

    for _ in range(4):
        response = generate(
            settings.gemini_agent_model,
            contents,
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

        tool_result = await tool_fn(**tool_args)
        tools_used.append(tool_name)
        last_tool_result = tool_result

        contents.append(candidate.content)
        contents.append(
            types.Content(
                role="tool",
                parts=[
                    types.Part.from_function_response(
                        name=tool_name,
                        response=tool_result,
                    )
                ],
            )
        )
    else:
        final = generate(
            settings.gemini_agent_model,
            contents,
            types.GenerateContentConfig(
                system_instruction="根據以上工具查詢結果，用 2-3 句繁體中文給出最終回答。",
            ),
        )
        final_answer = filter_output(final.text)

    if last_tool_result.get("shops"):
        decision = _build_agent_recommendation_decision(query, last_tool_result)
        if decision.narrative:
            final_answer = decision.narrative
            last_tool_result["agent_decision"] = _decision_payload(decision)

    if session_id:
        new_history = history + [
            {"role": "user", "content": query},
            {"role": "model", "content": final_answer},
        ]
        session_store.save_history(session_id, new_history)

    return final_answer, tools_used, last_tool_result


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
    tools_used: list[str] = []
    last_tool_result: dict = {}
    latest_search_result: dict = {}
    booking_result: dict | None = None
    payment_result: dict | None = None
    direct_answer: str | None = None

    # Phase 1: tool-calling loop (sync) — yields tool events as each fires
    for _ in range(4):
        response = generate(
            settings.gemini_agent_model,
            contents,
            types.GenerateContentConfig(
                tools=TOOLS,
                system_instruction=AGENT_SYSTEM_PROMPT,
            ),
        )
        candidate = response.candidates[0]
        function_call = None
        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_call = part.function_call
                break

        if not function_call:
            if not tools_used:
                # Zero tool calls — answer already computed; fast path, chunk as-is
                direct_answer = filter_output(response.text)
            break

        tool_name = function_call.name
        tool_fn = TOOL_DISPATCH.get(tool_name)
        if tool_fn is None:
            yield {"type": "error", "message": f"unknown tool: {tool_name}"}
            return

        tool_result = await tool_fn(**dict(function_call.args))
        tools_used.append(tool_name)
        last_tool_result = tool_result
        if tool_name in {"semantic_shop_search", "search_shops_by_mrt"}:
            latest_search_result = tool_result
        elif tool_name == "create_booking":
            booking_result = tool_result
        elif tool_name == "pay_booking_with_test_card":
            payment_result = tool_result
        yield {"type": "tool", "name": tool_name}

        contents.append(candidate.content)
        contents.append(
            types.Content(
                role="tool",
                parts=[types.Part.from_function_response(name=tool_name, response=tool_result)],
            )
        )

    # Phase 2: generate final answer
    full_answer = ""
    if direct_answer is not None:
        # Zero-tool path: chunk the pre-computed answer (fast, no visible delay)
        chunk_size = 18
        for i in range(0, len(direct_answer), chunk_size):
            full_answer = direct_answer
            yield {"type": "chunk", "content": direct_answer[i : i + chunk_size]}
    else:
        if booking_result is not None:
            transaction = _build_booking_transaction(
                booking_result,
                payment_result,
                latest_search_result,
            )
            full_answer = _booking_confirmation_narrative(transaction)
            last_tool_result["transaction"] = transaction
        else:
            decision = _build_agent_recommendation_decision(query, last_tool_result)
            full_answer = decision.narrative
            last_tool_result["agent_decision"] = _decision_payload(decision)
        chunk_size = 18
        for i in range(0, len(full_answer), chunk_size):
            yield {"type": "chunk", "content": full_answer[i : i + chunk_size]}

    if session_id:
        session_store.save_history(
            session_id,
            history + [
                {"role": "user", "content": query},
                {"role": "model", "content": full_answer},
            ],
        )

    yield {
        "type": "done",
        "answer": full_answer,
        **last_tool_result.get("agent_decision", {}),
        "transaction": last_tool_result.get("transaction"),
        "tools_used": tools_used,
        "tool_result": last_tool_result,
        "session_id": session_id,
    }


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
        yield _sse_frame({"type": "status", "message": "thinking"})
        try:
            async for payload in _run_agent_turn_stream(req.query, session_id):
                yield _sse_frame(payload)
        except Exception as exc:
            logger.exception("agent_stream_failed")
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


@app.delete("/api/ai/session/{session_id}")
async def clear_chat_session(session_id: str):
    """清除 Redis 對話歷史。"""
    session_store.clear_session(session_id)
    return {"success": True, "session_id": session_id}
