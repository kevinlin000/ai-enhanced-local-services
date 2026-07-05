from __future__ import annotations

import asyncio
import contextvars
import hashlib
import hmac
import json
import logging
import os
import re
import httpx
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import parse_qs, quote_plus
from zoneinfo import ZoneInfo
from app import session_store
from app.booking_draft import (
    booking_draft_confirmation_answer as _booking_draft_confirmation_answer,
    booking_draft_missing as _booking_draft_missing,
    booking_draft_payload as _booking_draft_payload,
    compact_booking_prefill as _compact_booking_prefill,
    merge_booking_prefill as _merge_booking_prefill,
)
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from app.guardrail import GuardrailViolation, check_input, filter_output
from app.line_auth import (
    decode_urlsafe,
    line_user_id_from_token_with_secret,
    line_user_id_from_unsigned_legacy_token,
    resolve_line_context,
)
from app.line_booking_text import line_booking_prefill_from_text, zh_number_to_int
from app.line_bot import (
    LINE_PHOTO_VERSION,
    best_shop_photo_url,
    build_line_flex_message,
    build_text_message,
    line_action_token,
    push_messages,
    reply_messages,
    show_loading_animation,
    verify_line_signature,
)
from app.line_html import (
    dedupe_text,
    html_escape,
    line_booking_path,
    line_bullet_html,
    line_display_rating,
    line_google_maps_uri,
    line_hours_html,
    line_html_page,
    line_parking_distance,
    line_parking_spaces,
    line_parse_hours,
    line_pills_html,
    line_public_uri,
    line_review_card_html,
    line_review_rating,
    line_shell,
    truncate_words,
)
from app.line_state import (
    clear_state_key,
    line_booking_draft_state_key,
    line_booking_state_key,
    line_location_state_key,
    line_recommendation_state_key,
    load_json_state,
    save_json_state,
)
from google import genai
from google.genai.errors import ClientError, ServerError
from google.genai import types

from app.ranking import (  # noqa: F401 — re-export 保持 app.main.* 相容
    BURGER_BLOCK_HINTS,
    BURGER_QUERY_HINTS,
    BURGER_TEXT_HINTS,
    BUSINESS_DINING_HINTS,
    CATEGORY_ALIASES,
    CATEGORY_CONFLICT_KEYWORDS,
    CATEGORY_FALLBACK_KEYWORDS,
    CATEGORY_HINTS,
    CLOSED_SHOP_HINTS,
    CONTEXT_INTENT_RULES,
    DISTRICT_HINTS,
    HOTPOT_BLOCK_HINTS,
    HOTPOT_STRONG_HINTS,
    INTENT_HINTS,
    LUXURY_HINTS,
    SPECIFIC_CUISINE_RULES,
    STATION_HINTS,
    STATION_NEIGHBORHOODS,
    SUPPORTED_CATEGORY_SLUGS,
    TAIWANESE_CUISINE_BLOCK_HINTS,
    TAIWANESE_CUISINE_QUERY_HINTS,
    TAIWANESE_CUISINE_STRONG_HINTS,
    TOOLS,
    TYPE_ID_TO_CATEGORY,
    _authoritative_category_slug,
    _booking_shop_keyword,
    _burger_sort_key,
    _canonical_category_slug,
    _category_slug_from_payload,
    _context_intent_bonus,
    _district_matches,
    _extract_query_constraints,
    _fallback_keyword_score,
    _has_explicit_category_conflict,
    _has_hotpot_semantics,
    _has_steak_semantics,
    _has_taiwanese_cuisine_semantics,
    _is_burger_hit,
    _is_inactive_search_hit,
    _is_restaurant_clarification_response,
    _is_specific_cuisine_mismatch,
    _is_taiwanese_cuisine_mismatch,
    _java_shop_to_search_hit,
    _matches_requested_category,
    _matches_specific_cuisine,
    _metadata_bonus,
    _normalize_district_name,
    _normalized_name,
    _normalized_rating,
    _parse_json_list,
    _payload_text,
    _premium_hotpot_key,
    _prioritize_steak_hits,
    _private_ai_offer_is_off_peak_time,
    _query_requests_steak,
    _recommended_shop_name_score,
    _resolve_taipei_district,
    _restaurant_clarification_gaps,
    _search_category_match,
    _semantic_category_slug,
    _specific_cuisine_sort_key,
    _specific_shop_keyword,
    _station_proximity_score,
    _steak_match_score,
    _steak_sort_key,
    _strip_specific_shop_keyword,
    _taiwanese_cuisine_sort_key,
    _taiwanese_identity_text,
    taipei_today,
)
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
    line_internal_webhook_secret: str = ""
    line_internal_webhook_require_secret: bool = True
    line_action_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
if settings.line_action_secret and not os.getenv("LINE_ACTION_SECRET"):
    os.environ["LINE_ACTION_SECRET"] = settings.line_action_secret
if settings.line_internal_webhook_secret and not os.getenv("LINE_INTERNAL_WEBHOOK_SECRET"):
    os.environ["LINE_INTERNAL_WEBHOOK_SECRET"] = settings.line_internal_webhook_secret
app = FastAPI(title="ByteBites AI Service", version="0.1.0")
_agent_auth_token: contextvars.ContextVar[str] = contextvars.ContextVar("agent_auth_token", default="")
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
LINE_BOOKING_TTL_SECONDS = 1800
LINE_ACTION_TOKEN_TTL_SECONDS = 60 * 60 * 24
_LINE_MEDIA_CACHE: dict | None = None
_LINE_PROFILE_CACHE: dict[str, str] = {}
_PARKING_RESERVATIONS: dict[str, dict] = {}
_LINE_MEDIA_ALIASES: dict[int, int] = {
    10009: 10550,
}
_LINE_SHOP_NAME_FALLBACKS: dict[int, str] = {
    10009: "橘色涮涮屋 信義館",
}


def _line_action_secret() -> bytes:
    value = (
        settings.line_action_secret
        or settings.line_internal_webhook_secret
        or "dev-line-action-secret"
    )
    return value.strip().encode("utf-8")


def _verify_internal_line_secret(payload: dict) -> None:
    expected_secret = (settings.line_internal_webhook_secret or "").strip()
    if not expected_secret:
        if settings.line_internal_webhook_require_secret:
            raise HTTPException(
                status_code=503,
                detail="LINE internal webhook secret is not configured",
            )
        logger.warning("LINE internal webhook accepted without shared secret")
        return
    provided_secret = str(payload.get("secret") or "").strip()
    if not hmac.compare_digest(provided_secret, expected_secret):
        raise HTTPException(status_code=403, detail="Invalid internal secret")


def _line_token_for_user(line_user_id: str) -> str:
    return line_action_token(line_user_id, ttl_seconds=LINE_ACTION_TOKEN_TTL_SECONDS)


def _decode_urlsafe(value: str) -> bytes:
    return decode_urlsafe(value)


def _line_user_id_from_token_with_secret(token: str, secret: bytes) -> str:
    return line_user_id_from_token_with_secret(token, secret)


def _line_user_id_from_token(token: str) -> str:
    return _line_user_id_from_token_with_secret(token, _line_action_secret())


def _line_user_id_from_unsigned_legacy_token(token: str) -> str:
    return line_user_id_from_unsigned_legacy_token(token)


def _line_context(lt: str = "", line_user_id: str = "") -> tuple[str, str]:
    return resolve_line_context(
        lt,
        line_user_id,
        action_secret=_line_action_secret(),
        legacy_channel_secret=settings.line_channel_secret,
        token_for_user=_line_token_for_user,
    )
PREMIUM_HOTPOT_SUPPLEMENT_IDS: tuple[int, ...] = ()
LEGACY_SEED_SHOP_IDS = {
    10001, 10002, 10003, 10004, 10005,
    10006, 10007, 10008, 10009, 10010,
    10011, 10012, 10013, 10014, 10015,
    10016, 10017, 10018, 10019, 10020,
    10021, 10022, 10023, 10024, 10025,
}


















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








def _restaurant_need_clarification(query: str) -> bool:
    normalized = str(query or "").strip()
    if not normalized:
        return False
    if _booking_intent(normalized) or _payment_intent(normalized) or _line_card_request_intent(normalized):
        return False
    if _specific_shop_keyword(normalized):
        return False
    constraints = _extract_query_constraints(normalized)
    has_location = bool(constraints["districts"] or constraints["stations"])
    has_explicit_location_text = bool(re.search(r"(台北|新北|[^\s，,。；;]{1,8}(區|站|路|街|商圈|夜市|百貨))", normalized))
    if constraints.get("wants_nearby") and not (has_location or has_explicit_location_text):
        return True
    if constraints["categories"] or constraints.get("wants_burger") or constraints.get("specific_cuisines"):
        return False
    has_people = bool(re.search(r"[一二三四五六七八九十\d]+\s*(個)?人", normalized))
    has_datetime = bool(re.search(r"(今天|明天|後天|今晚|晚上|晚餐|午餐|中午|早午餐|下午|[0-2]?\d[:：點時])", normalized))
    has_specific_context = bool(re.search(r"(聊天|約會|請客|慶生|商務|安靜|家庭|長輩|包廂)", normalized))
    if has_location and (has_people or has_datetime or has_specific_context):
        return False
    has_restaurant_phrase = any(
        phrase in normalized
        for phrase in ("推薦", "找", "想吃", "想找", "餐廳", "店", "聚餐", "吃飯", "用餐", "約會", "請客", "聊天", "慶生")
    )
    has_people_or_context = bool(re.search(r"[一二三四五六七八九十\d]+\s*(個)?人|聚餐|聊天|約會|請客|慶生|商務|安靜", normalized))
    has_location_only = bool(constraints["districts"] or constraints["stations"]) and has_people_or_context
    return has_restaurant_phrase or has_location_only




def _restaurant_clarification_known_context(query: str) -> str:
    normalized = str(query or "").strip()
    if not normalized:
        return ""
    constraints = _extract_query_constraints(normalized)
    known: list[str] = []
    if constraints.get("districts"):
        known.append("、".join(f"{district}區" for district in constraints["districts"][:2]))
    elif constraints.get("stations"):
        known.append("、".join(f"{station}站附近" for station in constraints["stations"][:2]))
    people_match = re.search(r"([一二三四五六七八九十\d]+)\s*(個)?人", normalized)
    if people_match:
        known.append(f"{people_match.group(1)}人")
    category_label = _category_label_for_constraints(constraints)
    if category_label != "餐廳":
        known.append(category_label)
    for label, pattern in (
        ("安靜聊天", r"安靜|聊天"),
        ("商務請客", r"商務|請客|宴客"),
        ("約會", r"約會"),
        ("慶生", r"慶生|生日"),
    ):
        if re.search(pattern, normalized) and label not in known:
            known.append(label)
    return "、".join(known[:3])


def _restaurant_clarification_text(query: str = "") -> str:
    gaps = _restaurant_clarification_gaps(query)
    known = _restaurant_clarification_known_context(query)
    prefix = f"{known}我先記下。" if known else ""
    if gaps:
        return (
            f"{prefix}還需要{'、'.join(gaps)}，我才能把候選收斂到可訂、適合的店。"
            "直接回一句就好，例如「大安區，適合聊天，明天晚上」或「中山站，台菜，週六晚餐」。"
        )
    return (
        f"{prefix}再補地點或捷運站、日期/時段與料理氣氛，我就能開始精準篩選。"
        "例如「信義區，商務請客，明晚 7 點」。"
    )














def _last_clarified_restaurant_query(history: list[dict]) -> str:
    if not history:
        return ""
    for index in range(len(history) - 1, 0, -1):
        current = history[index]
        previous = history[index - 1]
        if current.get("role") != "model" or previous.get("role") != "user":
            continue
        if not _is_restaurant_clarification_response(current):
            continue
        clarification_query = str(current.get("clarification_query") or "").strip()
        if clarification_query and _restaurant_need_clarification(clarification_query):
            return clarification_query
        query = str(previous.get("content") or "").strip()
        if query and _restaurant_need_clarification(query):
            return query
    return ""


def _query_is_clarification_followup(query: str) -> bool:
    normalized = str(query or "").strip()
    if not normalized:
        return False
    if _complete_fresh_restaurant_query(normalized):
        return False
    if _booking_intent(normalized) or _payment_intent(normalized) or _line_more_recommendation_intent(normalized):
        return False
    if _specific_shop_keyword(normalized):
        return False
    constraints = _extract_query_constraints(normalized)
    return bool(
        constraints["districts"]
        or constraints["stations"]
        or constraints["categories"]
        or constraints.get("specific_cuisines")
        or constraints.get("wants_burger")
        or constraints.get("wants_nearby")
        or re.search(
            r"(今天|明天|後天|今晚|晚上|晚餐|午餐|中午|早午餐|下午|"
            r"[0-2]?\d[:：點時]|聊天|約會|請客|慶生|商務|安靜|家庭|長輩|包廂|"
            r"[一二三四五六七八九十\d]+\s*(個)?人)",
            normalized,
        )
    )


def _effective_agent_query(query: str, history: list[dict]) -> str:
    previous_query = _last_clarified_restaurant_query(history)
    if previous_query and _query_is_clarification_followup(query):
        return _line_merge_followup_query(previous_query, query)
    return query


def _agent_should_force_search(query: str) -> bool:
    return bool(_specific_shop_keyword(query) or _line_should_force_recommendation_cards(query))




















































def _dedupe_search_hits(hits: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    positions: dict[int, int] = {}

    def quality(hit: dict) -> tuple[int, int, float, int]:
        return (
            _steak_match_score(hit),
            1 if _shop_has_rich_context(hit) else 0,
            float(hit.get("rerank_score") or hit.get("score") or 0.0),
            int(hit.get("comments") or 0),
        )

    for hit in hits:
        try:
            shop_id = int(hit.get("shop_id") or 0)
        except (TypeError, ValueError):
            shop_id = 0
        if not shop_id:
            deduped.append(hit)
            continue
        if shop_id not in positions:
            positions[shop_id] = len(deduped)
            deduped.append(hit)
            continue
        index = positions[shop_id]
        if quality(hit) > quality(deduped[index]):
            deduped[index] = hit
    return deduped












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
                    "district": _resolve_taipei_district(shop.get("address"), shop.get("district")),
                    "address": shop.get("address"),
                    "mrt_station": shop.get("mrtStation"),
                    "score": 0.0,
                    "rating": shop.get("score"),
                    "comments": shop.get("comments"),
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




def _is_legacy_seed_hit(hit: dict) -> bool:
    try:
        shop_id = int(hit.get("shop_id") or 0)
    except (TypeError, ValueError):
        return False
    return shop_id in LEGACY_SEED_SHOP_IDS


def _prefer_rich_hits(hits: list[dict], top_k: int) -> list[dict]:
    if not hits:
        return hits
    rich_hits = [hit for hit in hits if not _is_legacy_seed_hit(hit)]
    skipped = [hit.get("name") for hit in hits if _is_legacy_seed_hit(hit)]
    if skipped:
        logger.warning("search_legacy_seed_filtered skipped=%s", skipped[:8])
        return rich_hits[:top_k]
    if rich_hits:
        return rich_hits[:top_k]
    return hits


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


async def _burger_supplements(constraints: dict, existing_ids: set[int], limit: int = 12) -> list[dict]:
    if not constraints.get("wants_burger"):
        return []

    supplements: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get(
                f"{settings.java_backend_url}/api/shop/search",
                params={"q": "burger", "page": 1, "size": max(limit, 12)},
            )
        if response.status_code != 200:
            return []
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else {}
        records = data.get("records") if isinstance(data, dict) else []
    except Exception:
        logger.exception("burger_supplement_failed")
        return []

    for shop in records or []:
        if not isinstance(shop, dict):
            continue
        try:
            shop_id = int(shop.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if not shop_id or shop_id in existing_ids:
            continue
        hit = _java_shop_to_search_hit(shop)
        hit["rerank_score"] = float(hit.get("score") or 0.0) + _metadata_bonus("漢堡 美式餐廳", hit)
        if not _is_burger_hit(hit):
            continue
        supplements.append(hit)

    supplements.sort(key=lambda hit: _burger_sort_key(constraints, hit), reverse=True)
    return supplements[:limit]


async def _steak_supplements(query: str, constraints: dict, _existing_ids: set[int], limit: int = 8) -> list[dict]:
    if not _query_requests_steak(query):
        return []

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get(
                f"{settings.java_backend_url}/api/shop/search",
                params={"q": "牛排", "page": 1, "size": max(limit, 12)},
            )
        if response.status_code != 200:
            return []
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else {}
        records = data.get("records") if isinstance(data, dict) else []
    except Exception:
        logger.exception("steak_supplement_failed")
        return []

    supplements: list[dict] = []
    for shop in records or []:
        if not isinstance(shop, dict):
            continue
        try:
            shop_id = int(shop.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if not shop_id:
            continue
        metadata = await _fetch_java_ai_metadata(shop_id)
        hit = _java_shop_to_search_hit(shop, metadata)
        if constraints["districts"] and not _district_matches(constraints, hit):
            continue
        if not _has_steak_semantics(hit):
            continue
        hit["score"] = max(float(hit.get("score") or 0.0), 2.5)
        hit["rerank_score"] = float(hit.get("score") or 0.0) + _metadata_bonus(query, hit)
        supplements.append(hit)

    supplements.sort(key=lambda hit: _steak_sort_key(constraints, hit), reverse=True)
    return supplements[:limit]


async def _java_shop_name_supplements(query: str, existing_ids: set[int], limit: int = 5) -> list[dict]:
    keyword = _specific_shop_keyword(query)
    if not keyword:
        return []

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get(
                f"{settings.java_backend_url}/api/shop/search",
                params={"q": keyword, "page": 1, "size": max(limit, 8)},
            )
        if response.status_code != 200:
            return []
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else {}
        records = data.get("records") if isinstance(data, dict) else []
    except Exception:
        logger.exception("shop_name_supplement_failed query=%s keyword=%s", query, keyword)
        return []

    normalized_keyword = _normalized_name(keyword)
    supplements: list[dict] = []
    for shop in records or []:
        if not isinstance(shop, dict):
            continue
        try:
            shop_id = int(shop.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if not shop_id or shop_id in existing_ids:
            continue
        name = str(shop.get("name") or "")
        normalized_name = _normalized_name(name)
        if not normalized_keyword or (
            normalized_keyword not in normalized_name and normalized_name not in normalized_keyword
        ):
            continue
        metadata = await _fetch_java_ai_metadata(shop_id)
        hit = _java_shop_to_search_hit(shop, metadata)
        hit["score"] = 2.0
        hit["rerank_score"] = 2.0 + _metadata_bonus(keyword, hit)
        supplements.append(hit)

    supplements.sort(
        key=lambda hit: (
            1 if _normalized_name(keyword) == _normalized_name(str(hit.get("name") or "")) else 0,
            hit.get("rating") or 0,
            hit.get("comments") or 0,
        ),
        reverse=True,
    )
    return supplements[:limit]


_QUERY_EMBEDDING_CACHE: dict[str, list[float]] = {}
_QUERY_EMBEDDING_CACHE_MAX = 512


def _query_embedding(query: str) -> list[float]:
    """查詢向量快取：同 query 重問省一次 Gemini embedding 往返（~0.5-1s）。"""
    cached = _QUERY_EMBEDDING_CACHE.get(query)
    if cached is not None:
        return cached
    emb_resp = get_gemini().models.embed_content(
        model=settings.gemini_embedding_model,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    vector = list(emb_resp.embeddings[0].values)
    if len(_QUERY_EMBEDDING_CACHE) >= _QUERY_EMBEDDING_CACHE_MAX:
        _QUERY_EMBEDDING_CACHE.pop(next(iter(_QUERY_EMBEDDING_CACHE)))
    _QUERY_EMBEDDING_CACHE[query] = vector
    return vector


async def _semantic_hits(query: str, top_k: int) -> list[dict]:
    query_vector = _query_embedding(query)
    raw_hits = []
    try:
        qdrant = get_qdrant()
        results = qdrant.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            limit=max(top_k * 12, 60),
        ).points

        for result in results:
            payload = result.payload
            raw_hits.append(
                {
                    "shop_id": payload.get("shop_id"),
                    "name": payload.get("name"),
                    "district": _resolve_taipei_district(payload.get("address"), payload.get("district")),
                    "address": payload.get("address"),
                    "mrt_station": payload.get("mrt_station"),
                    "score": float(result.score),
                    "rating": payload.get("rating") or payload.get("google_score"),
                    "comments": payload.get("comments") or payload.get("review_count"),
                    "category": payload.get("category"),
                    "category_slug": payload.get("category_slug"),
                    "type_id": payload.get("type_id"),
                    "avg_price": payload.get("avg_price"),
                    "ai_summary": payload.get("ai_summary"),
                    "signature_dishes": _parse_json_list(payload.get("signature_dishes")),
                    "atmosphere_tags": _parse_json_list(payload.get("atmosphere_tags")),
                    "booking_difficulty": payload.get("booking_difficulty"),
                    "price_per_person": payload.get("price_per_person"),
                    "is_active": payload.get("is_active"),
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
    burger_hits = await _burger_supplements(
        constraints,
        {int(hit["shop_id"]) for hit in raw_hits if hit.get("shop_id")},
    )
    if burger_hits:
        raw_hits.extend(burger_hits)
    steak_hits = await _steak_supplements(
        query,
        constraints,
        {int(hit["shop_id"]) for hit in raw_hits if hit.get("shop_id")},
    )
    if steak_hits:
        raw_hits.extend(steak_hits)
    exact_name_hits = await _java_shop_name_supplements(
        query,
        {int(hit["shop_id"]) for hit in raw_hits if hit.get("shop_id")},
        limit=max(3, top_k),
    )
    if exact_name_hits:
        raw_hits = exact_name_hits + raw_hits
        logger.warning(
            "search_exact_name_supplement query=%r exact=%s",
            query,
            [hit.get("name") for hit in exact_name_hits[:8]],
        )

    raw_hits = _dedupe_search_hits(raw_hits)
    before_active_filter = len(raw_hits)
    raw_hits = [hit for hit in raw_hits if not _is_inactive_search_hit(hit)]
    if len(raw_hits) != before_active_filter:
        logger.warning("search_inactive_filtered count=%s", before_active_filter - len(raw_hits))

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

    if constraints.get("wants_burger"):
        burger_only = [hit for hit in raw_hits if _is_burger_hit(hit)]
        burger_other = [hit for hit in raw_hits if not _is_burger_hit(hit)]
        burger_only.sort(key=lambda hit: _burger_sort_key(constraints, hit), reverse=True)
        raw_hits = burger_only + burger_other
        logger.warning(
            "search_burger_partition query=%r burger=%s others=%s",
            query,
            [hit.get("name") for hit in burger_only[:8]],
            [hit.get("name") for hit in burger_other[:8]],
        )

    if _query_requests_steak(query):
        raw_hits = _prioritize_steak_hits(query, constraints, raw_hits)
        logger.warning(
            "search_steak_partition query=%r steak=%s",
            query,
            [hit.get("name") for hit in raw_hits[:8] if _has_steak_semantics(hit)],
        )

    if constraints["categories"]:
        def category_match(hit: dict) -> bool:
            return _search_category_match(query, constraints, hit)

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

    if any(keyword in query.lower() for keyword in LUXURY_HINTS) and not constraints.get("wants_burger"):
        def luxury_score(hit: dict) -> tuple:
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
        if constraints.get("wants_burger"):
            raw_hits = [hit for hit in raw_hits if _is_burger_hit(hit)]
            raw_hits = _prefer_rich_hits(raw_hits, top_k)
            logger.warning(
                "search_strict_burger_filter query=%r strict=%s",
                query,
                [hit.get("name") for hit in raw_hits[:8]],
            )
            return raw_hits[:top_k]
        specific_cuisine_hits = []
        for cuisine in constraints.get("specific_cuisines", []):
            specific_cuisine_hits.extend(
                hit for hit in raw_hits
                if _matches_specific_cuisine(hit, cuisine)
            )
        if specific_cuisine_hits:
            seen_specific_ids = set()
            unique_specific_hits = []
            for hit in specific_cuisine_hits:
                shop_id = hit.get("shop_id")
                if shop_id in seen_specific_ids:
                    continue
                seen_specific_ids.add(shop_id)
                unique_specific_hits.append(hit)
            raw_hits = unique_specific_hits
            for cuisine in constraints.get("specific_cuisines", []):
                raw_hits.sort(key=lambda hit: _specific_cuisine_sort_key(cuisine, hit), reverse=True)
            logger.warning(
                "search_specific_cuisine_filter query=%r cuisines=%s strict=%s",
                query,
                constraints.get("specific_cuisines", []),
                [hit.get("name") for hit in raw_hits[:8]],
            )
        else:
            strict_category = [
                hit for hit in raw_hits
                if _search_category_match(query, constraints, hit)
            ]
            rejected_conflicts = [
                hit for hit in raw_hits
                if any(_has_explicit_category_conflict(hit, category) for category in constraints["categories"])
            ]
            if strict_category:
                raw_hits = strict_category
            else:
                # 分類無人符合時不可清空結果（district/station 過濾都有保底，這裡曾缺）；
                # 退回語意排序、僅剔除明確衝突的店。
                raw_hits = [hit for hit in raw_hits if hit not in rejected_conflicts]
            logger.warning(
                "search_strict_category_filter query=%r categories=%s rejected_conflicts=%s strict=%s",
                query,
                constraints["categories"],
                [hit.get("name") for hit in rejected_conflicts[:8]],
                [hit.get("name") for hit in strict_category[:8]],
            )

    if constraints.get("wants_taiwanese_cuisine"):
        clean_taiwanese_pool = [
            hit for hit in raw_hits
            if not _is_taiwanese_cuisine_mismatch(hit)
        ]
        strong_taiwanese = [
            hit for hit in clean_taiwanese_pool
            if _has_taiwanese_cuisine_semantics(hit)
        ]
        generic_chinese = [
            hit for hit in clean_taiwanese_pool
            if hit not in strong_taiwanese
            and _semantic_category_slug(hit) == "chinese"
        ]
        rejected_mismatch = [
            hit for hit in raw_hits
            if _is_taiwanese_cuisine_mismatch(hit)
        ]
        if strong_taiwanese or generic_chinese:
            strong_taiwanese.sort(key=lambda hit: _taiwanese_cuisine_sort_key(constraints, hit), reverse=True)
            generic_chinese.sort(key=lambda hit: _taiwanese_cuisine_sort_key(constraints, hit), reverse=True)
            raw_hits = strong_taiwanese + generic_chinese
        logger.warning(
            "search_taiwanese_cuisine_filter query=%r strong=%s generic=%s rejected=%s",
            query,
            [hit.get("name") for hit in strong_taiwanese[:8]],
            [hit.get("name") for hit in generic_chinese[:8]],
            [hit.get("name") for hit in rejected_mismatch[:8]],
        )

    if constraints["districts"]:
        strict_district = [
            hit for hit in raw_hits
            if _district_matches(constraints, hit)
        ]
        if strict_district:
            loose_district = [hit for hit in raw_hits if hit not in strict_district]
            min_results = min(top_k, 3)
            raw_hits = strict_district if len(strict_district) >= min_results else strict_district + loose_district
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
        if strict_station:
            loose_station = [hit for hit in raw_hits if hit not in strict_station]
            min_results = min(top_k, 3)
            raw_hits = strict_station if len(strict_station) >= min_results else strict_station + loose_station
        logger.warning(
            "search_strict_station_filter query=%r stations=%s strict=%s",
            query,
            constraints["stations"],
            [hit.get("name") for hit in strict_station[:8]],
        )

    raw_hits = _prioritize_steak_hits(query, constraints, raw_hits)
    raw_hits = _prefer_rich_hits(raw_hits, top_k)
    return raw_hits[:top_k]


async def _fetch_hot_seat_vouchers(shop_ids: list[int]) -> dict[int, list]:
    """Return {shop_id: [{id, title, pay_value, actual_value, stock}]}. N+1 ok for demo."""
    out: dict[int, list] = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for sid in shop_ids:
            try:
                r = await client.get(f"{settings.java_backend_url}/api/shop/{sid}/flash-deals")
                if r.status_code == 404:
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
    return await _build_agent_search_result(query, hits)


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
        "message": "已為您搶到限時餐券，可在「我的訂單」查看",
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
    auth_headers = _agent_java_auth_headers()
    if not auth_headers:
        return {"success": False, "error": "請先用 LINE 登入網頁，再使用 AI 訂位。"}
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
            headers=auth_headers,
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
    auth_headers = _agent_java_auth_headers()
    if not auth_headers:
        return {"success": False, "error": "請先用 LINE 登入網頁，再完成訂金付款。"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{settings.java_backend_url}/api/booking/pay-test",
            headers=auth_headers,
            json={"bookingCode": booking_code},
        )
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}"}
    data = r.json()
    if not data.get("success"):
        return {"success": False, "error": data.get("errorMsg", "unknown")}
    return {"success": True, **data["data"]}


async def tool_cancel_booking(booking_code: str) -> dict:
    """Cancel a booking after an explicit user confirmation."""
    auth_headers = _agent_java_auth_headers()
    if not auth_headers:
        return {"success": False, "error": "請先用 LINE 登入網頁，再取消訂位。"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{settings.java_backend_url}/api/booking/{quote_plus(booking_code)}/cancel",
            headers=auth_headers,
            json={},
        )
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}"}
    data = r.json()
    if not data.get("success"):
        return {"success": False, "error": data.get("errorMsg", "unknown")}
    return {"success": True, **data["data"]}


async def tool_update_booking(
    booking_code: str,
    people: int | None = None,
    date: str | None = None,
    time: str | None = None,
    table_type: str | None = None,
) -> dict:
    """Update an existing booking by calling Java's transactional reschedule endpoint."""
    auth_headers = _agent_java_auth_headers()
    if not auth_headers:
        return {"success": False, "error": "請先用 LINE 登入網頁，再修改訂位。"}
    body: dict = {}
    if date:
        body["date"] = date
    if time:
        body["time"] = time
    if people is not None:
        body["people"] = people
    if table_type:
        body["tableType"] = table_type
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{settings.java_backend_url}/api/booking/{quote_plus(booking_code)}/reschedule",
            headers=auth_headers,
            json=body,
        )
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}"}
    data = r.json()
    if not data.get("success"):
        return {"success": False, "error": data.get("errorMsg", "unknown")}
    return {"success": True, **data["data"]}


async def tool_create_booking_incident(
    booking_code: str,
    incident_type: str = "CUSTOMER_LATE",
    delay_minutes: int = 15,
    message: str | None = None,
) -> dict:
    """Create a real-time booking rescue incident and ask Java to push LINE status."""
    auth_headers = _agent_java_auth_headers()
    if not auth_headers:
        return {"success": False, "error": "請先用 LINE 登入網頁，再建立救場通知。"}
    body = {
        "incidentType": incident_type,
        "delayMinutes": delay_minutes,
    }
    if message:
        body["message"] = message
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{settings.java_backend_url}/api/booking/{quote_plus(booking_code)}/incidents",
            headers=auth_headers,
            json=body,
        )
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}"}
    data = r.json()
    if not data.get("success"):
        return {"success": False, "error": data.get("errorMsg", "unknown")}
    return {"success": True, **data["data"]}


async def _fetch_private_dining_memory() -> dict:
    auth_headers = _agent_java_auth_headers()
    if not auth_headers:
        return {}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{settings.java_backend_url}/api/dining-memory/me",
                headers=auth_headers,
            )
        if r.status_code != 200:
            return {}
        data = r.json()
        if not data.get("success") or not isinstance(data.get("data"), dict):
            return {}
        return data["data"]
    except Exception:
        logger.exception("private_dining_memory_fetch_failed")
        return {}


def _private_ai_offer_trigger(query: str) -> str | None:
    normalized = (query or "").lower()
    retention_tokens = ("看了幾次", "一直看", "一直找", "還沒訂", "沒訂", "猶豫", "再看看")
    if any(token in normalized for token in retention_tokens):
        return "REPEATED_SEARCH_NO_BOOKING"

    off_peak_tokens = (
        "離峰",
        "空桌",
        "空檔",
        "平日",
        "下午",
        "早點",
        "17:30",
        "17點",
        "五點半",
        "5點半",
        "5:30",
    )
    if any(token in normalized for token in off_peak_tokens):
        return "OFF_PEAK_FILL"

    discount_tokens = ("優惠", "折扣", "省錢", "便宜", "划算", "打折", "9折", "九折", "八折", "coupon", "offer", "discount")
    if any(token in normalized for token in discount_tokens):
        return "SAVE_MONEY_INTENT"

    prefill = _line_booking_prefill_from_text(query)
    if _private_ai_offer_is_off_peak_time(str(prefill.get("time") or "")):
        return "OFF_PEAK_FILL"
    return None




async def _fetch_private_ai_offers(shop_ids: list[int], query: str) -> dict[int, list[dict]]:
    auth_headers = _agent_java_auth_headers()
    trigger = _private_ai_offer_trigger(query)
    if not auth_headers or not trigger:
        return {}

    unique_shop_ids: list[int] = []
    for shop_id in shop_ids:
        try:
            sid = int(shop_id)
        except (TypeError, ValueError):
            continue
        if sid > 0 and sid not in unique_shop_ids:
            unique_shop_ids.append(sid)
        if len(unique_shop_ids) >= 3:
            break
    if not unique_shop_ids:
        return {}

    prefill = _line_booking_prefill_from_text(query)
    payload: dict = {
        "shopIds": unique_shop_ids,
        "trigger": trigger,
    }
    if prefill.get("people"):
        payload["people"] = prefill["people"]
    if prefill.get("time"):
        payload["targetTime"] = prefill["time"]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{settings.java_backend_url}/api/private-offers/match",
                headers=auth_headers,
                json=payload,
            )
        if r.status_code != 200:
            return {}
        data = r.json()
        if not data.get("success") or not isinstance(data.get("data"), dict):
            return {}
        offers = data["data"].get("offers") or []
        by_shop: dict[int, list[dict]] = {}
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            try:
                sid = int(offer.get("shopId"))
            except (TypeError, ValueError):
                continue
            by_shop.setdefault(sid, []).append(offer)
        return by_shop
    except Exception:
        logger.exception("private_ai_offer_fetch_failed")
        return {}


def _agent_java_auth_headers() -> dict[str, str] | None:
    token = _agent_auth_token.get("").strip()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


TOOL_DISPATCH = {
    "search_shops_by_mrt": tool_search_by_mrt,
    "semantic_shop_search": tool_semantic_search,
    "create_hot_seat_order": tool_create_hot_seat_order,
    "create_booking": tool_create_booking,
    "pay_booking_with_test_card": tool_pay_booking_with_test_card,
    "cancel_booking": tool_cancel_booking,
    "update_booking": tool_update_booking,
    "create_booking_incident": tool_create_booking_incident,
}


AGENT_SYSTEM_PROMPT = """你是台灣店家推薦助手。根據使用者的問題，選擇合適的 tool 查詢資料，然後用繁體中文簡潔回答。

==== 對話決策策略（像真人 concierge，不是搜尋框）====
- 先判斷需求完整度，再決定追問、查店家、比較或訂位。
- 明確推薦需求：已有地點、料理類型、用途、人數、日期/時段中的至少 2 個，或指定店名 → 可以查 tool 並推薦。
- 模糊需求：只有「想聚餐」「7 個人能聚餐」「適合聊天」「附近好吃」「推薦餐廳」但缺少區域、日期/時段或料理偏好 → 不要硬推薦；先用 2-3 個短問題收斂需求（區域、日期/時段、料理/氣氛）。
- 使用者後續補充「給我圖卡」「卡片」「我要某店」「明天晚上」時，要沿用前文，不要當成全新的問題。
- 使用者指定精確店名（例如「青田七六」「劉山東牛肉麵」）時，必須以該店為主查詢；禁止改推薦名字相似或向量相近但不是同一家店的餐廳。
- 若使用者問「比較」「哪個適合」「幫我挑」「適合安靜聊天/家庭/約會」→ 回答必須有判斷依據，不只列店名。
- 查到多家候選時，用短段落或條列比較，不要輸出 markdown table；LINE 內表格會跑版。
- 若是口味真實性問題（如「正宗川菜」「香麻辣」「像日本當地」），先說明判斷維度，再推薦符合的店。
- 需要追問時不要道歉；先承接已知條件，再用一句話說還缺什麼，讓使用者知道下一步怎麼回答。
- 不要把不確定資訊寫成事實；資料未標示時寫「目前資料未標示」。

==== 地點與捷運 ====
- 使用者提到明確捷運站名（例如信義安和、中山國小、象山、雙連、市政府）時，優先使用 search_shops_by_mrt。
- 若同時指定捷運站與料理類型，先查捷運站附近，再用分類、評論摘要與可訂狀態篩選。
- 使用者說「附近」但沒有目前位置時，先追問區域或捷運站，不要假設位置。
- 使用者明確提到開車、停車或導航時，推薦後提醒可在店家詳情查看附近停車場與 Google Maps 導航；未提到時不要主動把停車當成主要推薦理由。

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

==== 限時餐券搶購流程（create_hot_seat_order）====
- 用戶說「幫我搶」「搶餐券」「想搶優惠」「想搶熱座」→ 呼叫 create_hot_seat_order
- 若不知道 voucher_id，先 semantic_shop_search 找到 hot_seat_vouchers，再取其中一個 id
- 訂單成功後，回應要包含 voucher_order_id，並提示用戶到「我的訂單」查看
- 一個 query 最多訂 1 個限時餐券方案

==== AI 私密配對優惠 ====
- 若候選資料有 private_ai_offers，描述為「AI 已替你保留/配對的私密優惠」，不要說成公開優惠券或全站折扣。
- 不要引導使用者找「優惠券入口」；私密 offer 只在符合條件的推薦或訂位流程中顯示。
- 私密 offer 是輔助決策訊號，不要為了折扣推薦不符合使用者料理、區域或私人記憶偏好的店。

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
    return _same_day_datetime_request(query)


def _same_day_datetime_request(query: str) -> bool:
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


def _booking_status_intent(query: str) -> bool:
    normalized = str(query or "").strip()
    return any(token in normalized for token in ("訂位狀態", "查看狀態", "狀態", "查訂位", "我的訂位", "訂位編號"))


def _booking_cancel_intent(query: str) -> bool:
    normalized = str(query or "").strip()
    return any(token in normalized for token in ("取消訂位", "取消這筆", "取消這個", "不要這筆", "退訂"))


def _booking_cancel_confirmation_intent(query: str) -> bool:
    normalized = str(query or "").strip()
    return any(token in normalized for token in ("確認取消", "確定取消", "是的取消", "確認退訂", "確定退訂"))


def _booking_reschedule_intent(query: str) -> bool:
    normalized = re.sub(r"\s+", "", str(query or ""))
    if not normalized:
        return False
    if _payment_intent(normalized) or _booking_cancel_intent(normalized) or _booking_cancel_confirmation_intent(normalized):
        return False
    if _negative_selection_intent(normalized):
        return False
    if re.search(r"(改|換)(到|成)?([0-2]?\d[:：點]|明天|明晚|後天|週|星期|[一二兩三四五六七八九十\d]{1,3}[人位])", normalized):
        return True
    return any(
        token in normalized
        for token in (
            "改成",
            "改到",
            "更改",
            "改一下",
            "改時間",
            "改日期",
            "改人數",
            "改位",
            "改訂位",
            "換成",
            "換到",
            "延後",
            "提前",
        )
    )


def _booking_incident_intent(query: str) -> bool:
    normalized = re.sub(r"\s+", "", str(query or "").lower())
    if not normalized:
        return False
    return any(
        token in normalized
        for token in (
            "晚到",
            "遲到",
            "會晚",
            "塞車",
            "路上堵",
            "趕不上",
            "晚點到",
            "店家延誤",
            "延誤通知",
            "延後入座",
            "前面桌",
            "delay",
            "late",
        )
    )


def _booking_incident_type_from_text(query: str) -> str:
    normalized = re.sub(r"\s+", "", str(query or "").lower())
    if any(token in normalized for token in ("店家延誤", "前面桌", "餐廳延", "入座延", "延後入座")):
        return "RESTAURANT_DELAY"
    return "CUSTOMER_LATE"


def _delay_minutes_from_text(query: str, default: int = 15) -> int:
    normalized = str(query or "")
    match = re.search(r"([一二兩三四五六七八九十\d]{1,3})\s*(分|分鐘|min|mins)", normalized, re.IGNORECASE)
    if not match:
        return default
    raw = match.group(1)
    value = _zh_number_to_int(raw) if not raw.isdigit() else int(raw)
    if value is None or value <= 0:
        return default
    return min(value, 45)


def _booking_table_type_from_text(query: str) -> str:
    normalized = re.sub(r"\s+", "", str(query or "").lower())
    if any(token in normalized for token in ("包廂", "包間", "private")):
        return "private"
    if any(token in normalized for token in ("吧台", "bar")):
        return "bar"
    if any(token in normalized for token in ("一般位", "一般座位", "普通位", "normal")):
        return "normal"
    return ""


def _booking_code_from_text(query: str) -> str:
    match = re.search(r"\b(BK[-A-Z0-9]+)\b", str(query or ""), flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


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


def _contextual_shop_choice_score(query: str, shop: dict, dimension: str = "整體") -> tuple[int, int, int, float]:
    text = _payload_text(shop)
    labels = _agent_query_context_labels(query)
    constraints = _extract_query_constraints(query)
    category_slug = _semantic_category_slug(shop)
    booking = str(shop.get("booking_difficulty") or "")
    score = 0

    if _district_matches(constraints, shop):
        score += 4
    categories = constraints.get("categories") or []
    if categories and category_slug in categories:
        score += 5
    if "yakiniku" in categories and category_slug != "yakiniku":
        score -= 4
    if "部門聚餐" in labels or "多人聚餐" in labels:
        if any(token in text for token in ("聚餐", "多人", "團體", "寬敞", "桌距", "二樓", "座位區", "舒適")):
            score += 5
        if any(token in text for token in ("站立", "吧台", "外帶")):
            score -= 6
        if any(token in text for token in ("小吃", "消夜", "米粉湯", "凌晨")):
            score -= 6
        if any(token in text for token in ("電話預約", "預點", "階梯", "廁所空間較為侷促", "動線涉及階梯")):
            score -= 5
        if category_slug == "vegetarian" and not re.search(r"素食|蔬食|植物|無麩質|健康", str(query or "")):
            score -= 2
    if "安靜聊天" in labels or dimension == "聊天":
        if any(token in text for token in ("聊天", "安靜", "舒適", "寬敞", "桌距", "自在", "放鬆", "良好採光", "溫馨")):
            score += 5
        if any(token in text for token in ("安靜", "包廂", "桌距")):
            score += 4
        if any(token in text for token in ("熱鬧", "人聲鼎沸", "酒吧", "餐酒館", "深夜", "尖峰音量")):
            score -= 4
        if any(token in text for token in ("離場時間", "時間掌控", "節奏掌控")):
            score -= 3
    if "家庭聚餐" in labels or dimension == "家庭":
        if any(token in text for token in ("家庭", "長輩", "親子", "舒適", "寬敞")):
            score += 4
    if "開車用餐" in labels:
        score += 2
    if _query_has_meat_lovers(query):
        if category_slug == "yakiniku" or any(token in text for token in ("燒肉", "牛排", "和牛", "牛舌", "肉類主餐", "培根", "雞肉", "豬")):
            score += 4
        if category_slug == "vegetarian":
            score -= 5
    if _query_has_shellfish_allergy(query):
        dishes = [dish for dish in _parse_json_list(shop.get("signature_dishes")) if dish]
        safe_dishes = [dish for dish in dishes if not _dish_has_obvious_shellfish(dish)]
        if dishes and not safe_dishes:
            score -= 5
        if any(token in str(shop.get("name") or "") for token in ("龍蝦", "蝦蟹", "海鮮")):
            score -= 3

    if booking and "未提及" not in booking:
        if any(token in booking for token in ("可線上", "現場可入")):
            score += 2
        if "預約困難" in booking:
            score -= 3
        elif "提前" in booking:
            score -= 1
    else:
        score += 1

    try:
        avg_price = int(shop.get("avg_price") or 0)
    except (TypeError, ValueError):
        avg_price = 0
    if dimension == "預算" and avg_price and avg_price <= 700:
        score += 3
    budget_low, budget_high = _query_budget_range(query)
    shop_low, shop_high = _shop_price_bounds(shop)
    if budget_low and budget_high and (shop_low or shop_high):
        effective_low = shop_low or shop_high or 0
        effective_high = shop_high or shop_low or 0
        if effective_low and effective_low > budget_high:
            score -= 10
        elif effective_high and effective_high < budget_low:
            score -= 1
        elif effective_low <= budget_high and effective_high >= budget_low:
            score += 3

    return (
        score,
        1 if _shop_has_rich_context(shop) else 0,
        int(shop.get("comments") or 0),
        float(shop.get("rerank_score") or shop.get("score") or 0.0),
    )


def _prioritize_contextual_recommended_ids(
    query: str,
    recommended_ids: list[int],
    shops: list[dict],
) -> list[int]:
    if not recommended_ids or not _agent_query_context_labels(query):
        return recommended_ids
    by_id = {
        sid: shop
        for shop in shops
        if (sid := _shop_id(shop)) is not None
    }
    target_count = min(3, len(recommended_ids))
    candidate_ids = [
        sid
        for sid in by_id
        if sid in recommended_ids or _contextual_shop_choice_score(query, by_id[sid])[0] > 8
    ]
    if len(candidate_ids) >= target_count:
        return sorted(
            candidate_ids,
            key=lambda sid: _contextual_shop_choice_score(query, by_id.get(sid, {})),
            reverse=True,
        )[:target_count]
    return sorted(
        recommended_ids,
        key=lambda sid: _contextual_shop_choice_score(query, by_id.get(sid, {})),
        reverse=True,
    )


def _should_expand_initial_recommendations(query: str, recommended: list[int], shops: list[dict]) -> bool:
    if len(recommended) >= 2 or len(shops) < 2:
        return False
    if not _fresh_restaurant_recommendation_request(query) or _recommendation_followup_reference(query):
        return False
    return bool(
        _query_has_shellfish_allergy(query)
        or _query_has_meat_lovers(query)
        or _query_budget_range(query)[0]
        or len(_agent_query_context_labels(query)) >= 2
    )


def _agent_initial_backup_viable(query: str, shop: dict) -> bool:
    if _query_has_shellfish_allergy(query):
        name = str(shop.get("name") or "")
        if any(token in name for token in ("龍蝦", "蝦蟹")):
            return False
        dishes = [dish for dish in _parse_json_list(shop.get("signature_dishes")) if dish]
        if dishes and not any(not _dish_has_obvious_shellfish(dish) for dish in dishes):
            return False
    budget_low, budget_high = _query_budget_range(query)
    if budget_low and budget_high:
        shop_low, shop_high = _shop_price_bounds(shop)
        if shop_low and shop_low > budget_high:
            return False
        if shop_high and shop_high < budget_low:
            return False
    return True


def _expand_initial_recommendations(
    query: str,
    recommended: list[int],
    rejected: list[int],
    shops: list[dict],
) -> tuple[list[int], list[int]]:
    if not _should_expand_initial_recommendations(query, recommended, shops):
        return recommended, rejected
    by_id = {sid: shop for shop in shops if (sid := _shop_id(shop)) is not None}
    candidates = [
        sid
        for sid in rejected
        if sid in by_id and _agent_initial_backup_viable(query, by_id[sid])
    ]
    if not candidates:
        return recommended, rejected
    best_backup = max(candidates, key=lambda sid: _contextual_shop_choice_score(query, by_id.get(sid, {})))
    return [*recommended, best_backup], [sid for sid in rejected if sid != best_backup]


def _private_memory_avoid_shop_ids(memory: dict | None) -> set[int]:
    if not isinstance(memory, dict):
        return set()
    avoid_ids: set[int] = set()
    for raw in memory.get("avoidShopIds") or []:
        try:
            avoid_ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    for item in memory.get("memories") or []:
        if not isinstance(item, dict) or not item.get("doNotRecommend"):
            continue
        try:
            avoid_ids.add(int(item.get("shopId")))
        except (TypeError, ValueError):
            continue
    return avoid_ids


def _private_memory_by_shop(memory: dict | None) -> dict[int, dict]:
    if not isinstance(memory, dict):
        return {}
    by_shop: dict[int, dict] = {}
    for item in memory.get("memories") or []:
        if not isinstance(item, dict):
            continue
        try:
            shop_id = int(item.get("shopId"))
        except (TypeError, ValueError):
            continue
        by_shop[shop_id] = item
    return by_shop


def _adjust_selected_ids_for_private_memory(
    shops: list[dict],
    selected_ids: list[int],
    memory: dict | None,
) -> list[int]:
    avoid_ids = _private_memory_avoid_shop_ids(memory)
    if not avoid_ids:
        return selected_ids
    target_count = min(3, len(selected_ids) or len(shops))
    adjusted = [sid for sid in selected_ids if sid not in avoid_ids]
    for shop in shops:
        sid = _shop_id(shop)
        if sid is None or sid in avoid_ids or sid in adjusted:
            continue
        adjusted.append(sid)
        if len(adjusted) >= target_count:
            break
    return adjusted or selected_ids


def _annotate_private_memory(shops: list[dict], memory: dict | None) -> list[dict]:
    by_shop = _private_memory_by_shop(memory)
    if not by_shop:
        return shops
    annotated: list[dict] = []
    for shop in shops:
        sid = _shop_id(shop)
        memory_item = by_shop.get(sid) if sid is not None else None
        if not memory_item:
            annotated.append(shop)
            continue
        updated = dict(shop)
        tags = [str(tag) for tag in memory_item.get("tags") or [] if tag]
        updated["private_memory_tags"] = tags[:6]
        updated["private_memory_rating"] = memory_item.get("rating")
        if memory_item.get("doNotRecommend"):
            updated["private_memory_status"] = "avoid"
            updated["private_memory_reason"] = "你上次把這家標記為不再推薦"
        elif tags:
            updated["private_memory_status"] = "matched"
            updated["private_memory_reason"] = f"你上次標記：{'、'.join(tags[:3])}"
        annotated.append(updated)
    return annotated


def _annotate_private_ai_offers(shops: list[dict], offers_by_shop: dict[int, list[dict]] | None) -> list[dict]:
    if not offers_by_shop:
        return shops
    annotated: list[dict] = []
    for shop in shops:
        sid = _shop_id(shop)
        offers = offers_by_shop.get(sid) if sid is not None else None
        if not offers:
            annotated.append(shop)
            continue
        updated = dict(shop)
        updated["private_ai_offers"] = offers[:3]
        first = offers[0]
        if isinstance(first, dict):
            title = str(first.get("title") or "AI 私密優惠").strip()
            updated["private_ai_offer_reason"] = title
        annotated.append(updated)
    return annotated


def _apply_private_memory_to_recommendations(
    recommended: list[int],
    rejected: list[int],
    shops: list[dict],
    memory: dict | None,
) -> tuple[list[int], list[int]]:
    avoid_ids = _private_memory_avoid_shop_ids(memory)
    if not avoid_ids:
        return recommended, rejected
    target_count = min(3, len(recommended) or len(shops))
    available_ids = [
        sid
        for shop in shops
        if (sid := _shop_id(shop)) is not None and sid not in avoid_ids
    ]
    next_recommended = [sid for sid in recommended if sid not in avoid_ids]
    for sid in available_ids:
        if sid not in next_recommended:
            next_recommended.append(sid)
        if len(next_recommended) >= target_count:
            break
    if not next_recommended:
        return recommended, rejected
    next_rejected = []
    for sid in rejected + [sid for sid in avoid_ids if sid not in rejected]:
        if sid not in next_recommended and sid not in next_rejected:
            next_rejected.append(sid)
    return next_recommended, next_rejected


def _shop_matches_budget_ceiling(query: str, shop: dict) -> bool:
    _low, high = _query_budget_range(query)
    if high is None:
        return True
    shop_low, shop_high = _shop_price_bounds(shop)
    if shop_low is None and shop_high is None:
        return True
    if shop_low is not None:
        return shop_low <= high
    return bool(shop_high is not None and shop_high <= high)


def _hard_constraint_candidate_ids(query: str, shops: list[dict]) -> set[int]:
    if not query or not shops:
        return set()
    constraints = _extract_query_constraints(query)

    enforce_steak = _query_requests_steak(query) and any(_has_steak_semantics(shop) for shop in shops)
    enforce_burger = bool(constraints.get("wants_burger")) and any(_is_burger_hit(shop) for shop in shops)
    enforce_category = bool(
        constraints.get("categories")
        or constraints.get("specific_cuisines")
        or constraints.get("wants_taiwanese_cuisine")
    ) and any(_search_category_match(query, constraints, shop) for shop in shops)
    enforce_district = bool(constraints.get("districts")) and any(_district_matches(constraints, shop) for shop in shops)
    enforce_station = bool(constraints.get("stations")) and any(_station_proximity_score(constraints, shop) > 0 for shop in shops)
    enforce_budget = _query_budget_range(query)[1] is not None and any(_shop_matches_budget_ceiling(query, shop) for shop in shops)

    if not any((enforce_steak, enforce_burger, enforce_category, enforce_district, enforce_station, enforce_budget)):
        return set()

    valid_ids: list[int] = []
    for shop in shops:
        sid = _shop_id(shop)
        if sid is None:
            continue
        if enforce_steak and not _has_steak_semantics(shop):
            continue
        if enforce_burger and not _is_burger_hit(shop):
            continue
        if enforce_category and not _search_category_match(query, constraints, shop):
            continue
        if enforce_district and not _district_matches(constraints, shop):
            continue
        if enforce_station and _station_proximity_score(constraints, shop) <= 0:
            continue
        if enforce_budget and not _shop_matches_budget_ceiling(query, shop):
            continue
        valid_ids.append(sid)
    return set(valid_ids)


def _apply_hard_constraints_to_recommendations(
    query: str,
    recommended: list[int],
    rejected: list[int],
    shops: list[dict],
) -> tuple[list[int], list[int]]:
    valid_hard_ids = _hard_constraint_candidate_ids(query, shops)
    if not valid_hard_ids:
        return recommended, rejected
    if recommended and all(sid in valid_hard_ids for sid in recommended):
        return recommended, rejected

    target_count = max(1, min(len(recommended) or 3, len(valid_hard_ids)))
    next_recommended = [sid for sid in recommended if sid in valid_hard_ids]
    for shop in shops:
        sid = _shop_id(shop)
        if sid is None or sid not in valid_hard_ids or sid in next_recommended:
            continue
        next_recommended.append(sid)
        if len(next_recommended) >= target_count:
            break

    if not next_recommended:
        return recommended, rejected

    next_rejected: list[int] = []
    for sid in [*recommended, *rejected, *[_shop_id(shop) for shop in shops]]:
        if sid is None or sid in next_recommended or sid in next_rejected:
            continue
        next_rejected.append(sid)
    return next_recommended, next_rejected


def _validate_agent_decision(
    decision: AgentRecommendationDecision,
    tool_result: dict,
    query: str = "",
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
    recommended, rejected = _apply_hard_constraints_to_recommendations(query, recommended, rejected, shops)
    rejected = [sid for sid in rejected if sid not in recommended]
    recommended = _prioritize_contextual_recommended_ids(query, recommended, shops)
    rejected = [sid for sid in rejected if sid not in recommended]
    for sid in available_ids:
        if sid is not None and sid not in recommended and sid not in rejected:
            rejected.append(sid)
    recommended, rejected = _expand_initial_recommendations(query, recommended, rejected, shops)
    recommended, rejected = _apply_private_memory_to_recommendations(
        recommended,
        rejected,
        shops,
        tool_result.get("private_memory") if isinstance(tool_result, dict) else None,
    )
    recommended, rejected = _apply_hard_constraints_to_recommendations(query, recommended, rejected, shops)
    rejected = [sid for sid in rejected if sid not in recommended]
    rejection_summary = decision.rejection_summary
    if rejection_summary:
        recommended_aliases: list[str] = []
        for shop in shops:
            sid = _shop_id(shop)
            if sid is None or sid not in recommended:
                continue
            display_name = _agent_display_shop_name(shop, 0)
            raw_name = str(shop.get("name") or "")
            recommended_aliases.append(display_name)
            recommended_aliases.append(raw_name)
            compact_display = _normalized_name(display_name)
            compact_raw = _normalized_name(raw_name)
            if len(compact_display) >= 4:
                recommended_aliases.append(compact_display[:4])
            if len(compact_raw) >= 4:
                recommended_aliases.append(compact_raw[:4])
            display_token = re.split(r"[\s（(|｜/]+", display_name.strip(), maxsplit=1)[0]
            if len(display_token) >= 3:
                recommended_aliases.append(display_token)
            if "｜" in raw_name:
                right = raw_name.split("｜", 1)[1].strip()
                if right:
                    recommended_aliases.append(right)
                    right_token = re.split(r"[\s（(|｜/]+", right, maxsplit=1)[0]
                    if len(right_token) >= 3:
                        recommended_aliases.append(right_token)
            first_token = re.split(r"[\s（(|｜/]+", raw_name.strip(), maxsplit=1)[0]
            if len(first_token) >= 3:
                recommended_aliases.append(first_token)
        normalized_rejection_summary = _normalized_name(rejection_summary)
        if any(
            alias
            and (
                alias in rejection_summary
                or (
                    len(_normalized_name(alias)) >= 3
                    and _normalized_name(alias) in normalized_rejection_summary
                )
            )
            for alias in recommended_aliases
        ):
            rejection_summary = None

    return AgentRecommendationDecision(
        recommended_shop_ids=recommended,
        narrative=filter_output(decision.narrative),
        rejected_shop_ids=rejected,
        rejection_summary=rejection_summary,
    )


def _agent_query_basis_label(query: str) -> str:
    constraints = _extract_query_constraints(query)
    parts: list[str] = []
    if constraints.get("districts"):
        parts.append("、".join(f"{district}區" for district in constraints["districts"][:2]))
    if constraints.get("stations"):
        parts.append("、".join(f"{station}站附近" for station in constraints["stations"][:2]))
    category_label = _category_label_for_constraints(constraints)
    if category_label != "餐廳":
        parts.append(category_label)
    intent_labels = []
    for label, pattern in (
        ("部門聚餐", r"(部門|公司|團隊|同事).{0,8}聚餐|聚餐.{0,8}(部門|公司|團隊|同事)"),
        ("家庭聚餐", r"家庭|爸媽|父母|長輩|親子|小孩"),
        ("方便開車", r"開車|停車|車位|導航"),
        ("商務請客", r"商務|請客|宴客"),
        ("安靜聊天", r"安靜|聊天"),
        ("約會", r"約會"),
        ("多人聚餐", r"聚餐|多人|[五六七八九十\d]+人"),
        ("慶生", r"慶生|生日"),
    ):
        if re.search(pattern, query):
            intent_labels.append(label)
    parts.extend(intent_labels[:2])
    if constraints.get("wants_luxury") and "高質感" not in parts:
        parts.append("高質感")
    return " / ".join(parts[:4]) if parts else "地點、料理與用餐情境"


def _agent_query_context_labels(query: str) -> list[str]:
    normalized = str(query or "")
    labels: list[str] = []
    if re.search(r"(部門|公司|團隊|同事).{0,8}聚餐|聚餐.{0,8}(部門|公司|團隊|同事)", normalized):
        labels.append("部門聚餐")
    elif re.search(r"多人|[五六七八九十\d]+人", normalized):
        labels.append("多人聚餐")
    if re.search(r"家庭|爸媽|父母|長輩|親子|小孩", normalized):
        labels.append("家庭聚餐")
    if re.search(r"聊天|不會太吵|不要太吵|安靜|好聊|久坐", normalized):
        labels.append("安靜聊天")
    if re.search(r"開車|停車|車位|導航", normalized):
        labels.append("開車用餐")
    if re.search(r"商務|請客|宴客|正式", normalized):
        labels.append("商務請客")
    deduped: list[str] = []
    for label in labels:
        if label not in deduped:
            deduped.append(label)
    return deduped


def _demo_story_recommended_shop_ids(query: str, shops: list[dict]) -> list[int]:
    constraints = _extract_query_constraints(query)
    districts = set(constraints.get("districts") or [])
    labels = set(_agent_query_context_labels(query))
    available = {
        sid
        for shop in shops
        if (sid := _shop_id(shop)) is not None
    }
    if not available:
        return []

    preferred: list[int] = []
    if {"家庭聚餐", "開車用餐"}.issubset(labels) and "信義" in districts:
        preferred = [10598, 10225, 10111]  # 香旬、吟鮮、鼎泰豐 A4
    elif {"部門聚餐", "安靜聊天"}.issubset(labels) and "大安" in districts:
        preferred = [10673, 10610, 10709]  # 光司DATE、Lazy Pasta、知初

    return [sid for sid in preferred if sid in available][:3]


def _query_has_shellfish_allergy(query: str) -> bool:
    normalized = str(query or "")
    return bool(re.search(r"甲殼|蝦蟹|蝦|蟹|龍蝦", normalized) and re.search(r"過敏|不能吃|不要|避開", normalized))


def _query_has_meat_lovers(query: str) -> bool:
    normalized = str(query or "")
    return any(token in normalized for token in ("無肉不歡", "偏愛肉", "愛吃肉", "肉食", "想吃肉"))


def _query_has_executive_context(query: str) -> bool:
    normalized = str(query or "")
    return any(token in normalized for token in ("主管", "老闆", "大老闆", "客戶", "長官"))


def _query_budget_range(query: str) -> tuple[int | None, int | None]:
    normalized = str(query or "").replace(",", "")
    match = re.search(r"(\d{2,5})\s*(?:到|至|-|~|～)\s*(\d{2,5})", normalized)
    if not match:
        return (None, None)
    low = int(match.group(1))
    high = int(match.group(2))
    return (min(low, high), max(low, high))


def _shop_price_bounds(shop: dict) -> tuple[int | None, int | None]:
    try:
        avg_price = int(shop.get("avg_price") or 0)
    except (TypeError, ValueError):
        avg_price = 0
    if avg_price:
        return (avg_price, avg_price)

    raw = " ".join(
        str(value or "")
        for value in (
            shop.get("price_per_person"),
            shop.get("price_range"),
            shop.get("price"),
        )
    ).replace(",", "")
    if not raw or "未提及" in raw:
        return (None, None)
    range_match = re.search(r"(\d{2,5})\s*(?:到|至|-|~|～)\s*(\d{2,5})", raw)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        return (min(low, high), max(low, high))
    floor_match = re.search(r"(\d{2,5})\s*(?:以上|\+)", raw)
    if floor_match:
        return (int(floor_match.group(1)), None)
    numbers = [int(item) for item in re.findall(r"\d{2,5}", raw)]
    if numbers:
        return (numbers[0], numbers[0])
    return (None, None)


def _agent_sorting_label(query: str) -> str:
    basis = _agent_query_basis_label(query)
    if basis != "地點、料理與用餐情境":
        return basis
    labels = _agent_query_context_labels(query)
    parts = labels[:2]
    if _query_has_shellfish_allergy(query):
        parts.append("過敏避雷")
    if _query_has_meat_lovers(query):
        parts.append("肉類偏好")
    return " / ".join(parts[:4]) or "地點、料理與用餐情境"


def _agent_constraint_bullets(query: str) -> list[str]:
    prefill = _line_booking_prefill_from_text(query)
    low, high = _query_budget_range(query)
    labels = _agent_query_context_labels(query)
    lines: list[str] = []
    when_parts = []
    if prefill.get("date"):
        when_parts.append(str(prefill["date"]))
    if prefill.get("time"):
        when_parts.append(str(prefill["time"]))
    if prefill.get("people"):
        when_parts.append(f"{prefill['people']} 人")
    if when_parts:
        lines.append(f"時間人數：{'、'.join(when_parts)}")
    basis = _agent_sorting_label(query)
    if basis:
        lines.append(f"地點情境：{basis}")
    dining_rules: list[str] = []
    if _query_has_shellfish_allergy(query):
        dining_rules.append("甲殼類過敏，先避開蝦蟹與龍蝦")
    if _query_has_meat_lovers(query):
        dining_rules.append("需要照顧吃肉需求")
    if dining_rules:
        lines.append(f"飲食限制：{'；'.join(dining_rules)}")
    if low and high:
        lines.append(f"預算：NT$ {low}-{high}/人")
    elif "安靜聊天" in labels:
        lines.append("座位偏好：能正常聊天、避免太吵")
    return lines[:5]


def _agent_story_frame(query: str) -> str:
    labels = _agent_query_context_labels(query)
    prefill = _line_booking_prefill_from_text(query)
    low, high = _query_budget_range(query)
    constraints: list[str] = []
    if prefill.get("people"):
        constraints.append(f"{prefill['people']} 人")
    if prefill.get("date") and prefill.get("time"):
        constraints.append(f"{prefill['date']} {prefill['time']}")
    if _query_has_shellfish_allergy(query):
        constraints.append("甲殼類過敏先避開蝦蟹")
    if _query_has_meat_lovers(query):
        constraints.append("要照顧吃肉需求")
    if low and high:
        constraints.append(f"預算抓 NT$ {low}-{high}/人")
    if constraints and "部門聚餐" in labels:
        return f"我先把條件拆開：" + "、".join(constraints[:5]) + f"；再用{_agent_sorting_label(query)}與可接訂位來排序。"
    if "部門聚餐" in labels:
        return "我會優先看三件事：多人座位是否合適、環境是否適合聊天、熱門時段能不能接訂位或候位。"
    if "家庭聚餐" in labels and "開車用餐" in labels:
        return "我會優先看三件事：是否適合長輩同行、地點是否方便抵達、訂位後能不能接停車提醒與車位保留展示。"
    if "開車用餐" in labels:
        return "我會把開車抵達一起納入考量，推薦後可接店家詳情的附近停車與車位保留展示。"
    if "安靜聊天" in labels:
        return "我會優先避開太吵、太像酒吧或桌距偏近的選項，先看適合聊天的餐廳。"
    return ""


def _agent_shop_match_reason(query: str, shop: dict) -> str:
    labels = _agent_query_context_labels(query)
    prefill = _line_booking_prefill_from_text(query)
    if not labels and not (prefill.get("date") or prefill.get("time") or prefill.get("people")):
        return ""

    constraints = _extract_query_constraints(query)
    reasons: list[str] = []
    districts = constraints.get("districts") or []
    if districts and _district_matches(constraints, shop):
        reasons.append(f"符合{districts[0]}區")
    stations = constraints.get("stations") or []
    if stations and _station_proximity_score(constraints, shop) > 0:
        reasons.append(f"靠近{stations[0]}站")

    text = _payload_text(shop)
    tags = "、".join(_parse_json_list(shop.get("atmosphere_tags")))
    evidence = f"{text} {tags}"
    if "部門聚餐" in labels:
        reasons.append("適合部門聚餐")
    elif "多人聚餐" in labels:
        reasons.append("適合多人聚餐")
    if "家庭聚餐" in labels:
        reasons.append("適合家庭與長輩同行")
    if "安靜聊天" in labels:
        if any(token in evidence for token in ("安靜", "聊天", "舒適", "寬敞", "包廂", "桌距")):
            reasons.append("有聊天與舒適度線索")
        else:
            reasons.append("已避開明顯吵雜類型")
    if "開車用餐" in labels:
        reasons.append("訂位後可接停車提醒")

    if prefill.get("date") or prefill.get("time") or prefill.get("people"):
        reasons.append("可接訂位或額滿候位")

    deduped: list[str] = []
    for reason in reasons:
        if reason and reason not in deduped:
            deduped.append(reason)
    return "、".join(deduped[:3])


def _agent_display_shop_name(shop: dict, index: int) -> str:
    name = str(shop.get("name") or f"店家 {index}").strip()
    if "｜" in name:
        left, right = [part.strip() for part in name.split("｜", 1)]
        if right and re.fullmatch(r"[\u4e00-\u9fff]{2,4}", left):
            name = right
    for separator in ("（", "(", "/", "｜", "|"):
        if separator in name:
            name = name.split(separator, 1)[0].strip()
    name = re.sub(r"[.。．…·]{3,}.*$", "", name).strip()
    return _short_agent_text(name, 34) or f"店家 {index}"


def _agent_shop_feature(shop: dict) -> str:
    dishes = [item for item in _parse_json_list(shop.get("signature_dishes")) if item][:2]
    if dishes:
        return f"招牌 {'、'.join(dishes)}"
    feature = _agent_comparison_feature(shop).replace("招牌：", "招牌 ")
    return _short_agent_text(feature, 42)


def _agent_context_best_for_label(query: str, shop: dict) -> str:
    query_lower = str(query or "").lower()
    text = _payload_text(shop)
    if any(token in query_lower for token in CONTEXT_INTENT_RULES["quiet_chat"]["query"]):
        if _context_intent_bonus(query, shop) > 0.18:
            return "安靜聊天"
    if any(token in query_lower for token in CONTEXT_INTENT_RULES["business"]["query"]):
        if _context_intent_bonus(query, shop) > 0.18:
            return "商務請客"
    if any(token in query_lower for token in CONTEXT_INTENT_RULES["date"]["query"]):
        if _context_intent_bonus(query, shop) > 0.18:
            return "約會"
    if any(token in query_lower for token in CONTEXT_INTENT_RULES["family"]["query"]):
        if _context_intent_bonus(query, shop) > 0.18:
            return "家庭聚餐"
    if "聚餐" in query_lower and "聚餐" in text:
        return "聚餐"
    return ""


def _agent_distinct_context_label(shop: dict) -> str:
    text = _payload_text(shop).lower()
    name = str(shop.get("name") or "").lower()
    category = str(shop.get("category") or shop.get("category_slug") or "").lower()
    dishes = "、".join(_parse_json_list(shop.get("signature_dishes"))).lower()
    combined = f"{name} {category} {text} {dishes}"
    if re.search(r"植物|蔬食|素食|vegetarian|無麩質", combined):
        return "蔬食友善"
    if re.search(r"熱炒|合菜|桌菜|中式|chinese", combined):
        return "中式合菜"
    if re.search(r"火鍋|鍋物|麻辣鍋|hotpot", combined):
        return "鍋物聚餐"
    if re.search(r"燒肉|烤肉|和牛|牛舌|yakiniku", combined):
        return "燒肉聚餐"
    if re.search(r"鼎泰豐|小籠包|炒飯", combined):
        return "長輩接受度高"
    if re.search(r"日式|定食|丼|japanese", combined):
        return "日式定食"
    if "lazy" in name or re.search(r"拼盤|共享|炸物", combined):
        return "多人分食"
    if re.search(r"義大利麵|燉飯|pasta|euro|義式", combined):
        return "義式主餐"
    if re.search(r"咖啡|甜點|cafe|不限時|久坐", combined):
        return "久坐聊天"
    return ""


def _agent_shop_best_for(shop: dict, query: str) -> str:
    query_labels = _agent_query_context_labels(query)
    contextual = _agent_context_best_for_label(query, shop)
    base_items = [item for item in _agent_comparison_best_for(shop).split("、") if item]
    merged: list[str] = []
    for label in query_labels:
        if label not in merged:
            merged.append(label)
    has_specific_gathering = any(label.endswith("聚餐") for label in merged)
    if contextual and contextual not in merged:
        if contextual != "聚餐" or not has_specific_gathering:
            merged.append(contextual)
    if "聚餐" in str(query or "") and "聚餐" in _payload_text(shop) and "聚餐" not in merged and not has_specific_gathering:
        merged.append("聚餐")
    if query_labels:
        distinct = _agent_distinct_context_label(shop)
        if distinct and distinct not in merged:
            merged.append(distinct)
        return "、".join(merged[:3])
    for item in base_items:
        if contextual and item in contextual:
            continue
        if item == "聚餐" and any(label.endswith("聚餐") for label in merged):
            continue
        if item not in merged:
            merged.append(item)
    return "、".join(merged[:3])


def _agent_booking_status_for_query(shop: dict, query: str) -> str:
    status = _agent_comparison_booking_status(shop)
    prefill = _line_booking_prefill_from_text(query)
    if prefill.get("date") or prefill.get("time") or prefill.get("people"):
        if "候位" not in status and "空位通知" not in status:
            status = f"{status}；額滿可候位通知"
    if "開車用餐" in _agent_query_context_labels(query) and "停車" not in status:
        status = f"{status}；訂位後可開停車提醒"
    return status


def _agent_shop_line(shop: dict, index: int, query: str = "") -> str:
    name = _agent_display_shop_name(shop, index)
    feature = _agent_shop_feature(shop)
    best_for = _agent_shop_best_for(shop, query)
    booking = _agent_booking_status_for_query(shop, query)
    if _query_has_shellfish_allergy(query):
        safe_menu = _shop_menu_items(shop, query)
        if safe_menu:
            feature = f"可先看非蝦蟹選項：{safe_menu}"
    parts = [feature]
    if best_for:
        parts.append(f"適合{best_for}")
    if booking:
        parts.append(f"訂位：{booking}")
    return f"{index}. {name}：{'；'.join(part for part in parts[:3] if part)}。"


def _agent_shop_markdown_line(shop: dict, index: int, query: str = "") -> str:
    name = _agent_display_shop_name(shop, index)
    feature = _agent_shop_feature(shop)
    if _query_has_shellfish_allergy(query):
        safe_menu = _shop_menu_items(shop, query)
        if safe_menu:
            feature = f"安全點餐：{safe_menu}"
    best_for = _agent_shop_best_for(shop, query)
    booking = _agent_booking_status_for_query(shop, query)
    details = [feature]
    if best_for:
        details.append(f"適合：{best_for}")
    if booking:
        details.append(f"訂位：{booking}")
    return f"{index}. {name}\n   - " + "\n   - ".join(item for item in details if item)


def _agent_missing_booking_fields(prefill: dict) -> list[str]:
    missing: list[str] = []
    if not prefill.get("date"):
        missing.append("日期")
    if not prefill.get("time"):
        missing.append("時間")
    if not prefill.get("people"):
        missing.append("人數")
    return missing


def _agent_recommendation_cta(query: str) -> str:
    prefill = _line_booking_prefill_from_text(query)
    labels = _agent_query_context_labels(query)
    missing = _agent_missing_booking_fields(prefill)
    suffix = ""
    if "開車用餐" in labels:
        suffix = "訂位完成後也能接停車提醒與車位保留展示。"
    elif prefill.get("date") or prefill.get("time") or prefill.get("people"):
        suffix = "如果該時段額滿，可以改設定候位 / 空位通知，不用自己重刷。"
    if not missing:
        return f"下一步：如果你要其中一間，我可以接著幫你建立訂位。{suffix}"
    if prefill.get("date") or prefill.get("time") or prefill.get("people"):
        return f"下一步：再補齊{'、'.join(missing)}，我就能把訂位流程接上。{suffix}"
    return "下一步：告訴我日期、時間與人數，我可以直接幫你查可訂並接到訂位流程。"


def _agent_concierge_narrative(
    query: str,
    tool_result: dict,
    decision: AgentRecommendationDecision,
) -> str:
    shops = tool_result.get("shops", []) if isinstance(tool_result, dict) else []
    selected = _shops_for_ids(shops, decision.recommended_shop_ids)[:3]
    if not selected:
        return decision.narrative

    basis = _agent_query_basis_label(query)
    count = len(selected)
    display_count = min(3, len(shops))
    if count == 1:
        if display_count > count:
            lead = f"結論：我先用「{basis}」篩，主推這 1 家，另保留 {display_count - count} 家備案比較。"
        else:
            lead = f"結論：我先用「{basis}」篩，最值得先看這 1 家。"
    else:
        if display_count > count:
            lead = f"結論：我先用「{basis}」篩，主推這 {count} 家，另保留 {display_count - count} 家備案比較。"
        else:
            lead = f"結論：我先用「{basis}」篩，優先看這 {count} 家。"
    lines = [lead]
    frame = _agent_story_frame(query)
    if frame:
        lines.extend(["", frame])
    bullets = _agent_constraint_bullets(query)
    if bullets:
        lines.extend(["", "我抓到的條件"])
        lines.extend(f"- {bullet}" for bullet in bullets)
    lines.extend(["", "精選推薦"])
    lines.extend(_agent_shop_markdown_line(shop, index, query) for index, shop in enumerate(selected, start=1))
    if len(selected) < 3 and (_query_has_shellfish_allergy(query) or _query_has_meat_lovers(query) or _query_budget_range(query)[0]):
        if decision.rejection_summary:
            tradeoff = _short_agent_text(decision.rejection_summary, limit=92)
        else:
            tradeoff = "其餘選項不是預算、座位型態，就是過敏備註穩定性不夠適合這次聚餐"
        backup_note = "下方其他卡片只作備案比較。" if display_count > len(selected) else ""
        lines.extend(["", f"取捨：主推名單先收斂，{tradeoff}。{backup_note}"])
    lines.extend(["", f"下一步：{_agent_recommendation_cta(query).removeprefix('下一步：')}"])
    return "\n".join(lines)


def _decision_payload(decision: AgentRecommendationDecision) -> dict:
    return {
        "recommended_shop_ids": decision.recommended_shop_ids,
        "narrative": decision.narrative,
        "rejected_shop_ids": decision.rejected_shop_ids,
        "rejection_summary": decision.rejection_summary,
    }


def _short_agent_text(value: str | None, limit: int = 58) -> str:
    text = re.sub(r"\s+", " ", value or "").strip().rstrip("。！？!")
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    cut = max(clipped.rfind("，"), clipped.rfind("、"), clipped.rfind("；"))
    return f"{(clipped[:cut] if cut > 18 else clipped).rstrip('，、；')}..."


def _agent_comparison_feature(shop: dict, query: str = "") -> str:
    dishes = _shop_menu_dishes_for_query(shop, query) if query else [item for item in _parse_json_list(shop.get("signature_dishes")) if item][:3]
    if dishes:
        return f"招牌：{'、'.join(dishes)}"
    summary = _short_agent_text(str(shop.get("ai_summary") or ""))
    if summary:
        return summary
    comments = shop.get("comments")
    if isinstance(comments, int) and comments >= 500:
        return f"Google 評論量 {comments} 則，可先作為人氣參考"
    return "資料較少，建議先確認菜單、營業時間與訂位狀態"


def _agent_comparison_best_for(shop: dict) -> str:
    tags = [item for item in _parse_json_list(shop.get("atmosphere_tags")) if item][:2]
    if tags:
        return "、".join(tags)

    text = " ".join(
        str(part or "")
        for part in (
            shop.get("name"),
            shop.get("category"),
            shop.get("category_slug"),
            shop.get("ai_summary"),
        )
    ).lower()
    if re.search(r"火鍋|麻辣|鍋底|鴛鴦鍋", text):
        return "多人聚餐、想吃鍋物"
    if re.search(r"漢堡|burger|美式", text):
        return "朋友聚餐、想吃美式漢堡"
    if re.search(r"家庭|長輩|親子|小孩", text):
        return "家庭聚餐、長輩同行"
    if re.search(r"商務|包廂|正式|宴客", text):
        return "商務聚餐、正式宴客"
    if re.search(r"約會|氣氛|浪漫|安靜", text):
        return "約會、安靜聊天"
    try:
        if int(shop.get("avg_price") or 0) <= 300:
            return "快速簡餐、預算友善"
    except (TypeError, ValueError):
        pass
    return "朋友聚餐、一般正餐" if _shop_has_rich_context(shop) else "需先確認資料完整度"


def _agent_comparison_booking_status(shop: dict) -> str:
    if shop.get("hot_seat_vouchers"):
        return "限時餐券可搶"
    booking = str(shop.get("booking_difficulty") or "").strip()
    if booking and "未提及" not in booking:
        return booking
    return "可線上訂位，建議確認"


def _agent_price_label(shop: dict) -> str:
    price = str(shop.get("price_per_person") or "").strip()
    if price and "未提及" not in price and "未知" not in price:
        return price
    if shop.get("avg_price"):
        return f"NT$ {shop.get('avg_price')}"
    manifest_price = _agent_manifest_price_label(shop)
    if manifest_price:
        return manifest_price
    text = _payload_text(shop)
    explicit = _explicit_price_label_from_text(text)
    if explicit:
        return explicit
    if any(token in text for token in ("性價比", "價格", "cp值", "划算", "份量")):
        return "價格口碑可參考"
    return ""


def _agent_manifest_price_label(shop: dict) -> str:
    shop_id = _shop_id(shop)
    if shop_id is None:
        return ""
    manifest_shop = _line_media_shop(int(shop_id))
    overview = manifest_shop.get("overview") if isinstance(manifest_shop, dict) else {}
    raw = str((overview or {}).get("price_overview") or "").strip()
    if not raw or any(token in raw for token in ("未提及", "未知")):
        return ""
    explicit = _explicit_price_label_from_text(raw)
    return explicit or raw


def _explicit_price_label_from_text(text: str) -> str:
    normalized = str(text or "").replace(",", "")
    match = re.search(r"(?:\$|nt\$?\s*)\s*(\d{2,5})\s*(?:到|至|-|~|～)\s*(\d{2,5})", normalized, flags=re.IGNORECASE)
    if not match:
        return ""
    low = int(match.group(1))
    high = int(match.group(2))
    return f"${min(low, high)}-{max(low, high)}"


def _agent_comparison_meta(shop: dict) -> str:
    price = _agent_price_label(shop)
    location = " · ".join(
        part
        for part in (
            shop.get("district"),
            f"捷運{shop.get('mrt_station')}" if shop.get("mrt_station") else None,
        )
        if part
    )
    return " · ".join(part for part in (price, location) if part)


def _selected_agent_response_shops(tool_result: dict) -> list[dict]:
    shops = tool_result.get("shops", []) if isinstance(tool_result, dict) else []
    if not isinstance(shops, list) or not shops:
        return []

    ids = (
        tool_result.get("agent_decision", {}).get("recommended_shop_ids")
        if isinstance(tool_result.get("agent_decision"), dict)
        else None
    )
    selected_ids = [
        int(shop_id)
        for shop_id in (ids or [])
        if str(shop_id).isdigit()
    ]
    if selected_ids:
        selected = _shops_for_ids(shops, selected_ids)
        if tool_result.get("strict_recommended_only"):
            return selected
        selected_id_set = {_shop_id(shop) for shop in selected}
        selected.extend(shop for shop in shops if _shop_id(shop) not in selected_id_set)
        return selected[: min(3, len(shops))]
    return shops[: min(3, len(shops))]


def _agent_comparison_rows(shops: list[dict], query: str = "") -> list[dict]:
    rows: list[dict] = []
    for shop in shops:
        shop_id = _shop_id(shop)
        if shop_id is None:
            continue
        match_reason = _agent_shop_match_reason(query, shop)
        rows.append(
            {
                "shop_id": shop_id,
                "name": _agent_display_shop_name(shop, int(shop_id)),
                "feature_highlight": _agent_comparison_feature(shop, query) or match_reason,
                "best_for": _agent_shop_best_for(shop, query) or _agent_comparison_best_for(shop),
                "booking_status": _agent_booking_status_for_query(shop, query),
                "meta": _agent_comparison_meta(shop),
            }
        )
    return rows


def _agent_response_contract(tool_result: dict) -> dict:
    contract = {
        **(tool_result.get("agent_decision", {}) if isinstance(tool_result.get("agent_decision"), dict) else {}),
        "transaction": tool_result.get("transaction") if isinstance(tool_result, dict) else None,
        "booking_draft": tool_result.get("booking_draft") if isinstance(tool_result.get("booking_draft"), dict) else None,
        "scope_note": tool_result.get("scope_note") if isinstance(tool_result, dict) else None,
    }
    shops = _selected_agent_response_shops(tool_result) if isinstance(tool_result, dict) else []
    if shops:
        contract["shops"] = shops
        contract["comparison_rows"] = _agent_comparison_rows(shops, str(tool_result.get("query") or ""))
    return contract


def _recommendation_context_from_tool_result(query: str, tool_result: dict) -> dict | None:
    shops = _selected_agent_response_shops(tool_result) if isinstance(tool_result, dict) else []
    compact_shops = []
    for shop in shops[:3]:
        shop_id = _shop_id(shop)
        if shop_id is None:
            continue
        compact_shops.append(
            {
                "shop_id": shop_id,
                "name": str(shop.get("name") or f"店家 {shop_id}"),
                "district": shop.get("district"),
                "category": shop.get("category") or shop.get("category_slug"),
                "avg_price": shop.get("avg_price"),
                "price_per_person": _agent_price_label(shop) or None,
                "ai_summary": shop.get("ai_summary"),
                "signature_dishes": _parse_json_list(shop.get("signature_dishes"))[:5],
                "atmosphere_tags": _parse_json_list(shop.get("atmosphere_tags"))[:5],
                "booking_difficulty": shop.get("booking_difficulty"),
            }
        )
    if not compact_shops:
        return None
    return {"query": query, "shops": compact_shops}


def _latest_recommendation_context(history: list[dict]) -> dict:
    for turn in reversed(history):
        recommendation = turn.get("recommendation") if isinstance(turn, dict) else None
        if isinstance(recommendation, dict):
            shops = recommendation.get("shops")
            if isinstance(shops, list) and shops:
                return recommendation
    return {}


def _recommendation_context_for_selection(query: str, history: list[dict]) -> dict:
    index = _selection_index_from_text(query)
    for turn in reversed(history):
        recommendation = turn.get("recommendation") if isinstance(turn, dict) else None
        if not isinstance(recommendation, dict):
            continue
        shops = recommendation.get("shops")
        if not isinstance(shops, list) or not shops:
            continue
        if index is not None and 0 <= index < len(shops):
            return recommendation
        if index is None and _recommended_shop_from_text(query, shops) is not None:
            return recommendation
    return _latest_recommendation_context(history)


def _latest_booking_draft(history: list[dict]) -> dict:
    for turn in reversed(history):
        recommendation = turn.get("recommendation") if isinstance(turn, dict) else None
        booking_draft = turn.get("booking_draft") if isinstance(turn, dict) else None
        if isinstance(booking_draft, dict) and booking_draft:
            return booking_draft
        if isinstance(recommendation, dict):
            shops = recommendation.get("shops")
            if isinstance(shops, list) and shops:
                return {}
    return {}


def _fresh_restaurant_recommendation_request(query: str) -> bool:
    normalized = re.sub(r"\s+", "", str(query or "").strip())
    if not normalized or _payment_intent(normalized) or _line_more_recommendation_intent(normalized):
        return False
    if _booking_confirm_intent(normalized) or _booking_draft_edit_intent(normalized):
        return False
    explicit_booking_phrases = (
        "我要訂",
        "我想訂",
        "想訂",
        "幫我訂",
        "幫我預約",
        "我要預約",
        "我想預約",
        "確認訂位",
        "送出訂位",
        "就訂",
    )
    if any(phrase in normalized for phrase in explicit_booking_phrases):
        return False
    return any(
        phrase in normalized
        for phrase in (
            "推薦",
            "想找",
            "找",
            "想吃",
            "適合",
            "附近",
            "餐廳",
            "聚餐",
            "吃飯",
            "用餐",
        )
    )


def _fresh_restaurant_query_signal_count(query: str) -> int:
    normalized = str(query or "").strip()
    if not normalized:
        return 0
    constraints = _extract_query_constraints(normalized)
    signals = 0
    if constraints.get("districts") or constraints.get("stations") or constraints.get("wants_nearby"):
        signals += 1
    if (
        constraints.get("categories")
        or constraints.get("specific_cuisines")
        or constraints.get("wants_burger")
        or _query_requests_steak(normalized)
    ):
        signals += 1
    if _agent_query_context_labels(normalized) or constraints.get("wants_luxury") or constraints.get("wants_hot_seat"):
        signals += 1
    if _query_budget_range(normalized) != (None, None):
        signals += 1
    if any(phrase in normalized for phrase in ("推薦", "想找", "找", "想吃", "餐廳", "吃飯", "用餐", "聚餐")):
        signals += 1
    return signals


def _complete_fresh_restaurant_query(query: str) -> bool:
    normalized = str(query or "").strip()
    if not _fresh_restaurant_recommendation_request(normalized):
        return False
    if _recommendation_followup_reference(normalized):
        return False
    return _fresh_restaurant_query_signal_count(normalized) >= 3


def _booking_confirm_intent(query: str) -> bool:
    normalized = re.sub(r"\s+", "", str(query or ""))
    if not normalized:
        return False
    return any(
        phrase in normalized
        for phrase in (
            "確認訂位",
            "確認送出",
            "送出訂位",
            "幫我送出",
            "可以訂",
            "就訂這個",
            "就這樣訂",
            "沒問題",
            "確認",
        )
    )


def _negative_selection_intent(query: str) -> bool:
    normalized = re.sub(r"\s+", "", str(query or ""))
    return any(token in normalized for token in ("不要", "不想要", "不訂", "換一家", "換別家", "其他家", "別間"))


def _booking_draft_edit_intent(query: str) -> bool:
    normalized = re.sub(r"\s+", "", str(query or ""))
    if not normalized or _booking_confirm_intent(normalized):
        return False
    if _negative_selection_intent(normalized):
        return False
    return any(token in normalized for token in ("改成", "改到", "更改", "改一下", "換成", "換到", "改", "換"))


def _selection_index_from_text(text: str) -> int | None:
    normalized = re.sub(r"\s+", "", str(text or ""))
    ordinal_match = re.search(r"第([一二兩三四五六七八九十\d]{1,3})(間|家|個|張|名|項)?", normalized)
    if ordinal_match:
        value = _zh_number_to_int(ordinal_match.group(1))
        return value - 1 if value and value > 0 else None
    prefix_match = re.search(r"(選|訂|要|看|換|改)([一二兩三四五六七八九十\d]{1,3})(間|家|個|張|名|項)", normalized)
    if prefix_match:
        value = _zh_number_to_int(prefix_match.group(2))
        return value - 1 if value and value > 0 else None
    simple_map = {"第一間": 0, "第一家": 0, "第一個": 0, "第二間": 1, "第二家": 1, "第二個": 1, "第三間": 2, "第三家": 2, "第三個": 2}
    for phrase, index in simple_map.items():
        if phrase in normalized:
            return index
    return None


def _recommended_shop_from_text(query: str, shops: list[dict]) -> dict | None:
    if not shops:
        return None
    index = _selection_index_from_text(query)
    if index is not None:
        return shops[index] if 0 <= index < len(shops) else None

    scored_matches = [
        (score, idx, shop)
        for idx, shop in enumerate(shops)
        if (score := _recommended_shop_name_score(query, shop)) > 0
    ]
    if scored_matches:
        return max(scored_matches, key=lambda item: (item[0], -item[1]))[2]

    keyword = _specific_shop_keyword(query)
    normalized_keyword = _normalized_name(keyword)
    if not normalized_keyword:
        return None
    for shop in shops:
        name = _normalized_name(str(shop.get("name") or ""))
        if normalized_keyword in name or name in normalized_keyword:
            return shop
    return None


def _line_recommendation_shop_snapshots(shops: list[dict], selected_ids: list[int]) -> list[dict]:
    selected = []
    seen = set()
    selected_id_set = {int(shop_id) for shop_id in selected_ids if str(shop_id).isdigit()}
    for shop in shops:
        if not isinstance(shop, dict):
            continue
        shop_id = _shop_id(shop)
        if shop_id is None or shop_id not in selected_id_set or shop_id in seen:
            continue
        seen.add(shop_id)
        selected.append(
            {
                "shop_id": shop_id,
                "name": str(shop.get("name") or f"店家 {shop_id}"),
                "district": str(shop.get("district") or ""),
                "category": str(shop.get("category") or shop.get("category_slug") or ""),
            }
        )
    return selected


def _booking_selection_intent(query: str) -> bool:
    normalized = re.sub(r"\s+", "", str(query or "").strip())
    if not normalized or _payment_intent(normalized) or _line_more_recommendation_intent(normalized):
        return False
    if _negative_selection_intent(normalized):
        return False
    if _booking_intent(normalized):
        return True
    return bool(
        re.search(
            r"(我要|我想要|選|要|就|訂|換|改).{0,4}(第[一二兩三四五六七八九十\d]{1,3}|[一二兩三四五六七八九十\d]{1,3})(間|家|個)",
            normalized,
        )
    )


def _exact_shop_matches_for_keyword(keyword: str, shops: list[dict]) -> list[dict]:
    normalized_keyword = _normalized_name(keyword)
    if not normalized_keyword:
        return []

    matches = []
    for shop in _dedupe_shops_by_brand(shops):
        normalized_name = _normalized_name(str(shop.get("name") or ""))
        if not normalized_name:
            continue
        if (
            normalized_keyword in normalized_name
            or normalized_name in normalized_keyword
            or _recommended_shop_name_score(keyword, shop) > 0
        ):
            matches.append(shop)

    return sorted(
        matches,
        key=lambda shop: (
            _normalized_name(str(shop.get("name") or "")) != normalized_keyword,
            not _normalized_name(str(shop.get("name") or "")).startswith(normalized_keyword),
        ),
    )


def _exact_shop_matches(query: str, shops: list[dict]) -> list[dict]:
    return _exact_shop_matches_for_keyword(_specific_shop_keyword(query), shops)


def _recommendation_advice_intent(query: str) -> bool:
    normalized = str(query or "").strip()
    if not normalized or _line_more_recommendation_intent(normalized):
        return False
    if _booking_intent(normalized) or _payment_intent(normalized):
        return False
    return any(
        phrase in normalized
        for phrase in (
            "為什麼",
            "原因",
            "哪間",
            "哪家",
            "哪個",
            "比較",
            "差異",
            "差在哪",
            "幫我挑",
            "你覺得",
            "最適合",
            "適合我",
            "適合聊天",
            "適合商務",
            "適合約會",
            "適合聚餐",
            "推薦什麼",
            "推薦菜",
            "菜色",
            "招牌",
            "必點",
            "避雷",
            "注意",
            "預算",
            "價位",
            "多少錢",
            "划算",
            "搭配",
            "捷運",
            "交通",
            "特定",
            "想吃",
        )
    )


def _recommendation_followup_reference(query: str) -> bool:
    normalized = str(query or "").strip()
    return bool(
        re.search(r"這[三兩二幾0-9一二三四五六七八九十]+家|這些|上述|剛剛|上一輪|前面", normalized)
        or any(
            phrase in normalized
            for phrase in (
                "主管",
                "老闆",
                "大老闆",
                "最後決策",
                "幫我看",
                "幫我選",
                "幫我挑",
                "怎麼選",
                "怎麼幫我選",
                "哪間",
                "哪家",
                "哪個",
            )
        )
    )


def _recommendation_dimension(query: str) -> str:
    normalized = str(query or "")
    if any(token in normalized for token in ("聊天", "安靜", "久坐")):
        return "聊天"
    if any(token in normalized for token in ("商務", "請客", "宴客", "正式")):
        return "商務"
    if any(token in normalized for token in ("約會", "慶生", "氣氛")):
        return "約會"
    if any(token in normalized for token in ("多人", "聚餐", "7人", "七人", "包廂")):
        return "多人聚餐"
    if any(token in normalized for token in ("家庭", "長輩", "小孩", "親子")):
        return "家庭"
    if any(token in normalized for token in ("菜色", "推薦菜", "招牌", "必點", "吃什麼", "特定")):
        return "菜色"
    if any(token in normalized for token in ("避雷", "注意", "缺點", "雷")):
        return "避雷"
    if any(token in normalized for token in ("捷運", "交通", "附近", "距離")):
        return "交通"
    if any(token in normalized for token in ("便宜", "平價", "預算", "划算")):
        return "預算"
    return "整體"


def _shop_advice_text(shop: dict) -> str:
    summary = str(shop.get("ai_summary") or "").strip()
    if summary:
        return _short_agent_text(summary, limit=72)
    dishes = _parse_json_list(shop.get("signature_dishes"))
    if dishes:
        return f"招牌可先看 {'、'.join(dishes[:3])}"
    tags = _parse_json_list(shop.get("atmosphere_tags"))
    if tags:
        return f"用餐情境偏 {'、'.join(tags[:3])}"
    return "目前資料較少，建議進詳情確認菜單、評論與訂位規則"


def _shop_dimension_score(shop: dict, dimension: str) -> int:
    text = " ".join(
        str(part or "")
        for part in (
            shop.get("name"),
            shop.get("category"),
            shop.get("ai_summary"),
            shop.get("booking_difficulty"),
            " ".join(_parse_json_list(shop.get("signature_dishes"))),
            " ".join(_parse_json_list(shop.get("atmosphere_tags"))),
        )
    )
    keyword_map = {
        "聊天": ("聊天", "安靜", "舒適", "寬敞", "久坐", "包廂"),
        "商務": ("商務", "請客", "宴客", "包廂", "正式", "精緻", "高級"),
        "約會": ("約會", "氣氛", "浪漫", "慶生", "精緻"),
        "多人聚餐": ("多人", "聚餐", "包廂", "合菜", "寬敞", "家庭"),
        "家庭": ("家庭", "長輩", "親子", "小孩", "合菜"),
        "預算": ("平價", "划算", "便宜", "預算"),
    }
    score = 0
    for keyword in keyword_map.get(dimension, ()):
        if keyword in text:
            score += 2
    if _shop_has_rich_context(shop):
        score += 1
    try:
        avg_price = int(shop.get("avg_price") or 0)
    except (TypeError, ValueError):
        avg_price = 0
    if dimension in {"商務", "約會"} and avg_price >= 800:
        score += 1
    if dimension == "預算" and avg_price and avg_price <= 500:
        score += 2
    return score


def _dish_has_obvious_shellfish(dish: str) -> bool:
    return bool(re.search(r"蝦|蟹|龍蝦", str(dish or "")))


def _dish_has_meat(dish: str) -> bool:
    return bool(re.search(r"肉|牛|豬|雞|培根|火腿|羊|鴨", str(dish or "")))


def _shop_menu_dishes_for_query(shop: dict, query: str, limit: int = 3) -> list[str]:
    dishes = [dish for dish in _parse_json_list(shop.get("signature_dishes")) if dish]
    if _query_has_shellfish_allergy(query):
        dishes = [dish for dish in dishes if not _dish_has_obvious_shellfish(dish)]
    if _query_has_meat_lovers(query):
        dishes = sorted(dishes, key=lambda dish: 0 if _dish_has_meat(dish) else 1)
    return dishes[:limit]


def _shop_menu_suggestion(shop: dict, query: str = "") -> str:
    dishes = _shop_menu_dishes_for_query(shop, query)
    if dishes:
        return f"可先看 {'、'.join(dishes)}"
    summary = str(shop.get("ai_summary") or "")
    if "義大利麵" in summary:
        return "可優先看義大利麵與燉飯類"
    if "合菜" in summary:
        return "適合點合菜或多人分享品項"
    return "建議進詳情頁確認菜單與熱門評論"


def _shop_watchout_text(shop: dict, query: str = "") -> str:
    text = _payload_text(shop)
    booking = _agent_comparison_booking_status(shop)
    warnings: list[str] = []
    if _query_has_shellfish_allergy(query):
        warnings.append("蝦蟹類先避開，訂位備註過敏並請店家二次確認")
    if _query_has_executive_context(query):
        warnings.append("主管在場，尖峰出餐與服務節奏要預留彈性")
    if "預約困難" in booking:
        warnings.append("熱門時段建議先訂，額滿就開候位通知")
    elif "現場可入" in booking:
        warnings.append("可訂位但現場彈性較高，7 人仍建議先鎖位")
    if any(token in text for token in ("熱鬧", "人聲鼎沸", "尖峰音量")):
        warnings.append("尖峰可能偏熱鬧")
    if any(token in text for token in ("離場時間", "時間掌控", "用餐時間")):
        warnings.append("用餐節奏可能較明確")
    if not _query_has_executive_context(query) and any(token in text for token in ("服務人員在忙碌", "人力", "漏單", "出餐節奏")):
        warnings.append("尖峰服務節奏要預留彈性")
    if "安靜聊天" in _agent_query_context_labels(query) and "熱鬧" not in text:
        warnings.append("訂位備註可寫希望安排較不吵的位置")
    deduped: list[str] = []
    for warning in warnings:
        if warning not in deduped:
            deduped.append(warning)
    limit = 3 if (_query_has_shellfish_allergy(query) or _query_has_executive_context(query)) else 2
    return "；".join(deduped[:limit]) or "目前沒有明顯避雷點，建議確認營業時間與訂位規則"


def _shop_budget_text(shop: dict) -> str:
    price = _agent_price_label(shop)
    if price:
        return price
    return "目前沒有結構化人均，先以詳情頁評論與訂金規則確認"


def _shop_choice_reason(shop: dict, query: str) -> str:
    reason = _agent_shop_match_reason(query, shop)
    best_for = _agent_shop_best_for(shop, query)
    summary = _short_agent_text(str(shop.get("ai_summary") or ""), limit=56)
    menu = _shop_menu_suggestion(shop, query)
    watchout = _shop_watchout_text(shop, query)
    parts = []
    if reason:
        parts.append(reason)
    if best_for:
        parts.append(f"適合 {best_for}")
    if summary:
        parts.append(summary)
    parts.append(menu)
    parts.append(f"提醒：{watchout}")
    return "；".join(parts[:5])


def _shop_menu_items(shop: dict, query: str = "") -> str:
    dishes = _shop_menu_dishes_for_query(shop, query)
    if dishes:
        return "、".join(dishes)
    suggestion = _shop_menu_suggestion(shop, query)
    return re.sub(r"^可先看\s*", "", suggestion).strip()


def _shop_concierge_fit(shop: dict, query: str, *, primary: bool = False) -> str:
    labels = _agent_query_context_labels(query)
    summary = _short_agent_text(str(shop.get("ai_summary") or ""), limit=44)
    distinct = _agent_distinct_context_label(shop)
    if not primary:
        if "部門聚餐" in labels and "安靜聊天" in labels:
            if distinct == "義式主餐":
                return "菜色接受度高，適合穩定聚餐"
            if distinct == "多人分食":
                return "適合共享，彈性比正式餐廳高"
            if distinct == "蔬食友善":
                return "安靜、蔬食友善，適合有飲食限制時"
        if "家庭聚餐" in labels and "開車用餐" in labels:
            if distinct == "日式定食":
                return "口味穩定，長輩接受度高"
            if distinct == "中式合菜":
                return "適合分享，家庭聚餐感明確"
            if distinct == "長輩接受度高":
                return "品牌穩定，適合保守安全牌"
        if distinct:
            return distinct
        if summary:
            return summary

    parts: list[str] = []
    if "部門聚餐" in labels and "安靜聊天" in labels:
        parts.append("最貼近 7 人部門聚餐又能聊天")
        if summary:
            parts.append(summary)
    elif "家庭聚餐" in labels and "開車用餐" in labels:
        parts.append("適合長輩同行，訂位後可接停車提醒")
        if summary:
            parts.append(summary)
    elif summary:
        parts.append(summary)
    if primary:
        menu = _shop_menu_items(shop, query)
        if menu:
            parts.append(f"菜色可從 {menu} 開始")
    if distinct and distinct not in "、".join(parts):
        parts.append(distinct)
    return "；".join(parts[:3]) or _agent_comparison_feature(shop)


def _shop_role_for_advice(index: int, shop: dict, query: str) -> str:
    if index == 0:
        return "首選"
    booking = _agent_comparison_booking_status(shop)
    distinct = _agent_distinct_context_label(shop)
    if "預約困難" in booking:
        return "有特殊飲食需求時"
    if distinct in {"蔬食友善", "中式合菜", "鍋物聚餐"}:
        return distinct
    if "現場可入" in booking:
        return "備案，彈性較高"
    return "備案"


def _budget_summary_for_shops(shops: list[dict]) -> str:
    items: list[str] = []
    for shop in shops[:3]:
        price = _shop_budget_text(shop)
        if not price or "未提及" in price or "目前沒有結構化" in price:
            continue
        name = _agent_display_shop_name(shop, int(_shop_id(shop) or 0))
        items.append(f"{name}：{price}")
    return "；".join(items) if items else "目前價格資料不完整，建議以詳情頁評論與訂金規則確認"


def _budget_summary_for_query(shops: list[dict], query: str) -> str:
    low, high = _query_budget_range(query)
    if not (low and high):
        return _budget_summary_for_shops(shops)
    items: list[str] = []
    for shop in shops[:3]:
        name = _agent_display_shop_name(shop, int(_shop_id(shop) or 0))
        price = _shop_budget_text(shop)
        try:
            avg_price = int(shop.get("avg_price") or 0)
        except (TypeError, ValueError):
            avg_price = 0
        if avg_price:
            fit = "落在預算內" if low <= avg_price <= high else ("偏高" if avg_price > high else "預算有餘裕")
            items.append(f"{name}：NT$ {avg_price}，{fit}")
        elif price and "目前沒有結構化" not in price:
            items.append(f"{name}：{price}")
    if items:
        return f"預算抓 NT$ {low}-{high}/人，" + "；".join(items)
    return f"預算抓 NT$ {low}-{high}/人，但目前結構化價格不足，建議以詳情頁評論與訂金規則確認"


def _constraint_strategy_line(shop: dict, query: str) -> str:
    parts: list[str] = []
    menu = _shop_menu_items(shop, query)
    if menu:
        prefix = "點餐"
        if _query_has_shellfish_allergy(query):
            prefix = "安全點餐"
        parts.append(f"{prefix}：{menu}")
    if _query_has_meat_lovers(query):
        parts.append("先用培根、雞肉或肉類主餐照顧吃肉同事")
    if _query_has_shellfish_allergy(query):
        parts.append("蝦、蟹、龍蝦類不要放進建議菜單，訂位備註過敏")
    return "；".join(parts)


def _booking_followup_cta_from_context(query: str) -> str:
    prefill = _line_booking_prefill_from_text(query)
    parts: list[str] = []
    if prefill.get("date") and prefill.get("time"):
        parts.append(f"{prefill['date']} {prefill['time']}")
    elif prefill.get("date"):
        parts.append(str(prefill["date"]))
    elif prefill.get("time"):
        parts.append(str(prefill["time"]))
    if prefill.get("people"):
        parts.append(f"{prefill['people']} 人")
    if parts:
        return f"要訂的話，我會沿用 {'、'.join(parts)}；額滿就改開候位 / 空位通知。"
    return "要訂的話，補日期、時間與人數後我可以直接接訂位；額滿就改開候位 / 空位通知。"


def _recommendation_advice_answer(query: str, shops: list[dict], context_query: str = "") -> str:
    valid_shops = [shop for shop in shops if isinstance(shop, dict) and _shop_id(shop) is not None]
    if not valid_shops:
        return ""
    combined_query = " ".join(part for part in (context_query, query) if part).strip()
    selected = _recommended_shop_from_text(query, valid_shops)
    if selected is not None:
        name = _agent_display_shop_name(selected, int(_shop_id(selected) or 0))
        return (
            f"**最後決策：我會把「{name}」放第一順位。**\n\n"
            f"**理由**\n- {_shop_concierge_fit(selected, combined_query, primary=True)}\n\n"
            f"**避雷**\n- {_shop_watchout_text(selected, combined_query)}\n\n"
            f"**預算**\n- {_shop_budget_text(selected)}"
        )

    dimension = _recommendation_dimension(query)
    ranked = sorted(
        valid_shops,
        key=lambda shop: (
            _contextual_shop_choice_score(combined_query, shop, dimension),
            _shop_dimension_score(shop, dimension),
            _shop_has_rich_context(shop),
        ),
        reverse=True,
    )
    best = ranked[0]
    best_name = _agent_display_shop_name(best, int(_shop_id(best) or 0))
    has_complex_constraints = (
        _query_has_shellfish_allergy(combined_query)
        or _query_has_meat_lovers(combined_query)
        or _query_has_executive_context(combined_query)
        or bool(_query_budget_range(combined_query)[0])
    )
    if has_complex_constraints:
        strategy = _constraint_strategy_line(best, combined_query)
        lines = [
            f"**結論：我會選「{best_name}」。**",
            "",
            "**為什麼是它**",
            f"- {_shop_concierge_fit(best, combined_query, primary=True)}",
        ]
        if strategy:
            lines.extend(["", "**點餐策略**", f"- {strategy}"])
        lines.extend(["", "**避雷**", f"- {_shop_watchout_text(best, combined_query)}"])
        lines.extend(["", "**預算判斷**", f"- {_budget_summary_for_query(ranked, combined_query)}"])
        lines.extend(["", "**三家分工**"])
        for index, shop in enumerate(ranked[:3]):
            name = _agent_display_shop_name(shop, int(_shop_id(shop) or index + 1))
            role = _shop_role_for_advice(index, shop, combined_query)
            lines.append(f"- **{name}**：{role}，{_shop_concierge_fit(shop, combined_query)}。")
        lines.extend(["", f"**下一步**：{_booking_followup_cta_from_context(combined_query)}"])
        return "\n".join(lines)

    lines = [
        f"**最後決策：我會優先選「{best_name}」。**",
        "",
        f"**理由**：{_shop_concierge_fit(best, combined_query, primary=True)}。",
        "",
        f"**注意**：{_shop_watchout_text(best, combined_query)}。",
        "",
        "**三家分工**",
    ]
    for index, shop in enumerate(ranked[:3]):
        name = _agent_display_shop_name(shop, int(_shop_id(shop) or index + 1))
        role = _shop_role_for_advice(index, shop, combined_query)
        lines.append(f"- **{name}**：{role}。{_shop_concierge_fit(shop, combined_query)}。")
    lines.extend(["", f"**預算**：{_budget_summary_for_query(ranked, combined_query)}。"])
    lines.append(f"**下一步**：{_booking_followup_cta_from_context(combined_query)}")
    return "\n".join(lines)


def _agent_recommendation_advice_from_history(query: str, history: list[dict]) -> ToolGuardResult | None:
    if not _recommendation_advice_intent(query):
        return None
    if _complete_fresh_restaurant_query(query) and not _recommendation_followup_reference(query):
        return None
    recommendation = _latest_recommendation_context(history)
    shops = recommendation.get("shops") if isinstance(recommendation, dict) else []
    if not isinstance(shops, list) or not shops:
        return None
    answer = _recommendation_advice_answer(query, shops, str(recommendation.get("query") or ""))
    if not answer:
        return None
    return ToolGuardResult(
        action="direct",
        direct_answer=answer,
        last_tool_result={"query": str(recommendation.get("query") or query), "shops": shops},
    )


def _agent_booking_followup_from_history(query: str, history: list[dict]) -> ToolGuardResult | None:
    if _payment_intent(query):
        return None
    if _fresh_restaurant_recommendation_request(query):
        return None
    prefill = _line_booking_prefill_from_text(query)
    has_prefill = bool(prefill.get("date") or prefill.get("time") or prefill.get("people"))
    booking_draft = _latest_booking_draft(history)
    edit_intent = _booking_draft_edit_intent(query) and bool(booking_draft)
    if not has_prefill and not _booking_selection_intent(query) and not _booking_confirm_intent(query) and not edit_intent:
        return None
    if _same_day_datetime_request(query):
        return ToolGuardResult(action="direct", direct_answer=_same_day_booking_policy_answer())

    prefill = _merge_booking_prefill(prefill, booking_draft, override=edit_intent)
    recommendation = _recommendation_context_for_selection(query, history) if edit_intent else _latest_recommendation_context(history)
    contract_query = " ".join(
        part
        for part in (str(recommendation.get("query") or "") if isinstance(recommendation, dict) else "", query)
        if part
    ).strip()
    shops = recommendation.get("shops") if isinstance(recommendation, dict) else []
    selected_shop = None
    if isinstance(shops, list) and shops:
        selected_shop = shops[0] if len(shops) == 1 else _recommended_shop_from_text(query, shops)
    if selected_shop is None and isinstance(booking_draft, dict) and booking_draft.get("shop_id"):
        selected_shop = {
            "shop_id": booking_draft.get("shop_id"),
            "name": booking_draft.get("shop_name") or f"店家 {booking_draft.get('shop_id')}",
        }
    if not isinstance(shops, list) or not shops:
        if selected_shop is None:
            return None
    if selected_shop is None:
        return ToolGuardResult(
            action="direct",
            direct_answer="我收到訂位需求了。請先回覆要訂哪一間店名或第幾間，避免幫你訂錯餐廳。",
        )

    try:
        shop_id = int(selected_shop.get("shop_id"))
    except (TypeError, ValueError):
        return None
    shop_name = str(selected_shop.get("name") or f"店家 {shop_id}")
    selected_shop_payload = dict(selected_shop)
    selected_shop_payload["shop_id"] = shop_id
    selected_shop_payload["name"] = shop_name
    missing = []
    if not prefill.get("date"):
        missing.append("日期")
    if not prefill.get("time"):
        missing.append("時間")
    if not prefill.get("people"):
        missing.append("人數")
    if missing:
        draft = _booking_draft_payload(shop_id, shop_name, prefill)
        return ToolGuardResult(
            action="direct",
            direct_answer=_booking_draft_confirmation_answer(draft, query),
            last_tool_result={
                "query": contract_query or query,
                "shops": [selected_shop_payload],
                "booking_draft": draft,
            },
        )

    draft = _booking_draft_payload(shop_id, shop_name, prefill)
    if not _booking_confirm_intent(query):
        return ToolGuardResult(
            action="direct",
            direct_answer=_booking_draft_confirmation_answer(draft, query),
            last_tool_result={
                "query": contract_query or query,
                "shops": [selected_shop_payload],
                "booking_draft": draft,
            },
        )

    return ToolGuardResult(
        action="continue",
        args={
            "shop_id": shop_id,
            "people": int(prefill["people"]),
            "date": str(prefill["date"]),
            "time": str(prefill["time"]),
            "table_type": "normal",
        },
        last_tool_result={
            "query": contract_query or query,
            "shops": [selected_shop_payload],
            "booking_draft": draft,
        },
    )


async def _agent_more_recommendations_from_history(query: str, history: list[dict]) -> ToolGuardResult | None:
    if not _line_more_recommendation_intent(query):
        return None

    recommendation = _latest_recommendation_context(history)
    previous_query = str(recommendation.get("query") or "").strip()
    shops = recommendation.get("shops") if isinstance(recommendation, dict) else []
    if not previous_query:
        return ToolGuardResult(
            action="direct",
            direct_answer="可以，請先告訴我想找的地點和類型，例如「信義區火鍋」或「中山站聚餐」。",
        )
    seen_ids = {
        int(shop.get("shop_id"))
        for shop in shops
        if isinstance(shop, dict) and str(shop.get("shop_id") or "").isdigit()
    }

    try:
        hits = await _semantic_hits(previous_query, top_k=30)
    except Exception:
        logger.exception("agent_more_recommendations_failed query=%s", previous_query)
        return ToolGuardResult(
            action="direct",
            direct_answer="我暫時無法取得更多餐廳，請稍後再試一次。",
        )

    remaining = [
        shop
        for shop in hits
        if (sid := _shop_id(shop)) is not None and sid not in seen_ids
    ]
    seen_brands = {
        _shop_brand_key(shop).lower()
        for shop in hits
        if (sid := _shop_id(shop)) is not None and sid in seen_ids
    }
    remaining = [
        shop
        for shop in remaining
        if not (brand := _shop_brand_key(shop).lower()) or brand not in seen_brands
    ]
    remaining = _dedupe_shops_by_brand(remaining)
    if not remaining:
        return ToolGuardResult(
            action="direct",
            direct_answer="目前同一個條件下沒有更多明顯符合的餐廳了。你可以放寬地區或換一個類型，我再幫你找。",
        )

    selected_ids = [
        int(sid)
        for shop in remaining[:3]
        if (sid := _shop_id(shop)) is not None
    ]
    search_result = await _build_agent_search_result(previous_query, remaining, selected_ids)
    search_result["agent_decision"] = _decision_payload(
        AgentRecommendationDecision(
            recommended_shop_ids=selected_ids,
            narrative="我避開剛剛已推薦的店，另外整理了這幾個選項。",
            rejected_shop_ids=[],
        )
    )
    return ToolGuardResult(action="continue", last_tool_result=search_result)


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
    if transaction.get("status") == "RESCHEDULE_FAILED":
        shop_name = transaction.get("shop_name") or f"店家 ID {transaction.get('shop_id')}"
        return "\n".join(
            [
                f"改單失敗：{transaction.get('error') or '新時段目前無法保留'}",
                "原訂位已保留不變。",
                "",
                f"- 店家：{shop_name}",
                f"- 原時間：{transaction.get('date')} {transaction.get('time')}",
                f"- 訂位編號：`{transaction.get('booking_code')}`",
            ]
        )
    if transaction.get("action") == "rescheduled":
        shop_name = transaction.get("shop_name") or f"店家 ID {transaction.get('shop_id')}"
        status_line = "訂位已更新。" if transaction.get("changed", True) else "訂位內容沒有變更。"
        lines = [
            status_line,
            "",
            f"- 店家：{shop_name}",
            f"- 人數：{transaction.get('people')} 人",
            f"- 新時間：{transaction.get('date')} {transaction.get('time')}",
            f"- 訂位編號：`{transaction.get('booking_code')}`",
        ]
        if transaction.get("status") == "PENDING_PAYMENT" and transaction.get("needs_deposit"):
            lines.append(f"- 待付訂金：NT$ {transaction.get('deposit_total') or 0}")
        return "\n".join(lines)
    if transaction.get("action") == "incident":
        shop_name = transaction.get("shop_name") or f"店家 ID {transaction.get('shop_id')}"
        incident = transaction.get("incident") if isinstance(transaction.get("incident"), dict) else {}
        return "\n".join(
            [
                incident.get("title") or "已建立臨場救場通知。",
                "",
                f"- 店家：{shop_name}",
                f"- 原訂位：{transaction.get('date')} {transaction.get('time')}，{transaction.get('people')} 人",
                f"- 新預估：{incident.get('adjustedTime') or '-'}",
                f"- 訂位編號：`{transaction.get('booking_code')}`",
                "",
                incident.get("customerMessage") or "我已幫你記錄現場狀況，並同步通知 LINE。",
            ]
        )
    if transaction.get("status") == "INCIDENT_FAILED":
        shop_name = transaction.get("shop_name") or f"店家 ID {transaction.get('shop_id')}"
        return "\n".join(
            [
                f"救場通知建立失敗：{transaction.get('error') or '後端未回傳原因'}",
                "",
                f"- 店家：{shop_name}",
                f"- 訂位編號：`{transaction.get('booking_code') or '-'}`",
            ]
        )
    if transaction.get("status") == "CANCELED":
        shop_name = transaction.get("shop_name") or f"店家 ID {transaction.get('shop_id')}"
        return "\n".join(
            [
                "訂位已取消。",
                "",
                f"- 店家：{shop_name}",
                f"- 時間：{transaction.get('date')} {transaction.get('time')}",
                f"- 訂位編號：`{transaction.get('booking_code')}`",
            ]
        )
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


def _booking_status_narrative(transaction: dict) -> str:
    shop_name = transaction.get("shop_name") or f"店家 ID {transaction.get('shop_id')}"
    lines = [
        f"我找到最近一筆訂位：{shop_name}",
        "",
        f"- 狀態：{transaction.get('status') or '未標示'}",
        f"- 人數：{transaction.get('people') or '-'} 人",
        f"- 時間：{transaction.get('date') or '-'} {transaction.get('time') or ''}".rstrip(),
        f"- 訂位編號：`{transaction.get('booking_code') or '-'}`",
    ]
    if transaction.get("status") == "PENDING_PAYMENT" and transaction.get("needs_deposit"):
        lines.append(f"- 待付訂金：NT$ {transaction.get('deposit_total') or 0}")
        lines.append("若要付款，請回覆「我要付款」。")
    elif transaction.get("status") in {"CONFIRMED", "PAID"}:
        lines.append("這筆訂位目前已成立。")
    elif transaction.get("status") == "CANCELED":
        lines.append("這筆訂位已取消。")
    return "\n".join(lines)


def _booking_cancel_prompt(transaction: dict) -> str:
    shop_name = transaction.get("shop_name") or f"店家 ID {transaction.get('shop_id')}"
    return "\n".join(
        [
            f"我找到最近一筆訂位：{shop_name}",
            f"- 時間：{transaction.get('date') or '-'} {transaction.get('time') or ''}".rstrip(),
            f"- 人數：{transaction.get('people') or '-'} 人",
            f"- 訂位編號：`{transaction.get('booking_code') or '-'}`",
            "",
            "取消是不可逆動作。若確定要取消，請回覆「確認取消」並附上訂位編號。",
        ]
    )


def _booking_cancel_confirmation_mismatch(query: str, transaction: dict) -> str | None:
    requested_code = _booking_code_from_text(query)
    current_code = str(transaction.get("booking_code") or "").upper()
    if requested_code and current_code and requested_code != current_code:
        return (
            f"你提供的訂位編號 `{requested_code}` 和最近一筆 `{current_code}` 不一致。"
            "為避免取消錯訂位，請重新確認訂位編號。"
        )
    return None


def _booking_cancel_not_allowed_narrative(transaction: dict) -> str | None:
    status = str(transaction.get("status") or "")
    if status == "CANCELED":
        return "這筆訂位已取消，不需要重複取消。"
    if status == "EXPIRED":
        return "這筆訂位保留已逾期，不需要取消。"
    if not transaction.get("booking_code"):
        return "我找不到這筆訂位的訂位編號，無法安全取消。"
    return None


def _booking_payment_not_needed_narrative(transaction: dict) -> str:
    status = str(transaction.get("status") or "")
    if status in {"PAID", "CONFIRMED"}:
        return _booking_status_narrative(transaction)
    if status == "CANCELED":
        return "這筆訂位已取消，不能再付款。"
    if status == "EXPIRED":
        return "這筆訂位保留已逾期，請重新建立訂位。"
    return "我找不到可付款的待付訂金訂位。請先確認訂位狀態或重新建立訂位。"


def _booking_reschedule_action(query: str, transaction: dict) -> ToolGuardResult:
    current_code = str(transaction.get("booking_code") or "").upper()
    requested_code = _booking_code_from_text(query)
    if requested_code and current_code and requested_code != current_code:
        return ToolGuardResult(
            action="direct",
            direct_answer=(
                f"你提供的訂位編號 `{requested_code}` 和最近一筆 `{current_code}` 不一致。"
                "為避免改錯訂位，請重新確認訂位編號。"
            ),
            last_tool_result={"transaction": transaction},
        )
    if not current_code:
        return ToolGuardResult(
            action="direct",
            direct_answer="我找不到這筆訂位的訂位編號，無法安全改單。",
            last_tool_result={"transaction": transaction},
        )

    status = str(transaction.get("status") or "")
    if status == "CANCELED":
        return ToolGuardResult(action="direct", direct_answer="這筆訂位已取消，不能再改時間。", last_tool_result={"transaction": transaction})
    if status == "EXPIRED" or _pending_booking_expired(transaction):
        return ToolGuardResult(action="direct", direct_answer="這筆訂位保留已逾期，請重新建立訂位。", last_tool_result={"transaction": transaction})
    if status not in {"PAID", "CONFIRMED", "PENDING_PAYMENT"}:
        return ToolGuardResult(action="direct", direct_answer="我找不到可修改的有效訂位。", last_tool_result={"transaction": transaction})
    if _same_day_datetime_request(query):
        return ToolGuardResult(action="direct", direct_answer=_same_day_booking_policy_answer(), last_tool_result={"transaction": transaction})

    prefill = _line_booking_prefill_from_text(query)
    requested_table_type = _booking_table_type_from_text(query)
    touched = bool(prefill.get("date") or prefill.get("time") or prefill.get("people") or requested_table_type)
    if not touched:
        return ToolGuardResult(
            action="direct",
            direct_answer="可以改單。請直接告訴我要改成哪個日期、時間或人數，例如「改成明晚 8 點，同樣 4 位」。",
            last_tool_result={"transaction": transaction},
        )

    date = prefill.get("date") or transaction.get("date")
    time = prefill.get("time") or transaction.get("time")
    people = prefill.get("people") or transaction.get("people")
    table_type = requested_table_type or transaction.get("table_type") or "normal"
    if not date or not time or not people:
        return ToolGuardResult(
            action="direct",
            direct_answer="我需要完整的日期、時間與人數才能改單。請用「改成明晚 8 點 4 位」這種格式回覆。",
            last_tool_result={"transaction": transaction},
        )
    try:
        people = int(people)
        requested_date = date_cls.fromisoformat(str(date))
    except (TypeError, ValueError):
        return ToolGuardResult(
            action="direct",
            direct_answer="改單格式我沒有讀懂，請確認日期為 YYYY-MM-DD、時間為 HH:MM、人數為 1-12。",
            last_tool_result={"transaction": transaction},
        )
    if people < 1 or people > 12:
        return ToolGuardResult(action="direct", direct_answer="訂位人數需介於 1-12 人。", last_tool_result={"transaction": transaction})
    if requested_date <= taipei_today():
        return ToolGuardResult(action="direct", direct_answer=_same_day_booking_policy_answer(), last_tool_result={"transaction": transaction})

    old_people = int(transaction.get("people") or 0)
    old_table_type = transaction.get("table_type") or "normal"
    if (
        str(date) == str(transaction.get("date") or "")
        and str(time) == str(transaction.get("time") or "")
        and people == old_people
        and str(table_type) == str(old_table_type)
    ):
        return ToolGuardResult(
            action="direct",
            direct_answer="這筆訂位目前已經是你指定的日期、時間與人數，不需要再改。",
            last_tool_result={"transaction": transaction},
        )

    return ToolGuardResult(
        action="reschedule",
        args={
            "booking_code": current_code,
            "date": str(date),
            "time": str(time),
            "people": people,
            "table_type": str(table_type),
        },
        last_tool_result={"transaction": transaction},
    )


def _booking_incident_action(query: str, transaction: dict) -> ToolGuardResult:
    current_code = str(transaction.get("booking_code") or "").upper()
    requested_code = _booking_code_from_text(query)
    if requested_code and current_code and requested_code != current_code:
        return ToolGuardResult(
            action="direct",
            direct_answer=(
                f"你提供的訂位編號 `{requested_code}` 和最近一筆 `{current_code}` 不一致。"
                "為避免通知錯訂位，請重新確認訂位編號。"
            ),
            last_tool_result={"transaction": transaction},
        )
    if not current_code:
        return ToolGuardResult(action="direct", direct_answer="我找不到這筆訂位的訂位編號，無法建立救場通知。", last_tool_result={"transaction": transaction})
    status = str(transaction.get("status") or "")
    if status == "CANCELED":
        return ToolGuardResult(action="direct", direct_answer="這筆訂位已取消，不能建立救場通知。", last_tool_result={"transaction": transaction})
    if status == "EXPIRED" or _pending_booking_expired(transaction):
        return ToolGuardResult(action="direct", direct_answer="這筆訂位保留已逾期，不能建立救場通知。", last_tool_result={"transaction": transaction})
    if status not in {"PAID", "CONFIRMED", "PENDING_PAYMENT"}:
        return ToolGuardResult(action="direct", direct_answer="我找不到可建立救場通知的有效訂位。", last_tool_result={"transaction": transaction})
    return ToolGuardResult(
        action="incident",
        args={
            "booking_code": current_code,
            "incident_type": _booking_incident_type_from_text(query),
            "delay_minutes": _delay_minutes_from_text(query),
        },
        last_tool_result={"transaction": transaction},
    )


def _booking_transaction_after_payment(transaction: dict, payment_result: dict) -> dict:
    updated = dict(transaction)
    if payment_result.get("success"):
        updated.update(
            {
                "success": True,
                "status": "PAID",
                "rec_trade_id": payment_result.get("rec_trade_id"),
                "payment_amount": payment_result.get("amount"),
                "payment_note": payment_result.get("note") or "Demo 付款完成，非真實扣款。",
                "error": None,
            }
        )
    else:
        updated.update(
            {
                "success": False,
                "status": "PAYMENT_FAILED",
                "error": payment_result.get("error") or "付款流程未完成",
            }
        )
    return updated


def _booking_transaction_after_incident(transaction: dict, incident_result: dict) -> dict:
    updated = dict(transaction)
    if incident_result.get("success"):
        incident = {key: value for key, value in incident_result.items() if key != "success"}
        updated.update(
            {
                "success": True,
                "action": "incident",
                "incident": incident,
                "error": None,
            }
        )
    else:
        updated.update(
            {
                "success": False,
                "status": "INCIDENT_FAILED",
                "action": "incident_failed",
                "error": incident_result.get("error") or "救場通知建立失敗",
            }
        )
    return updated


def _booking_transaction_after_cancel(transaction: dict, cancel_result: dict) -> dict:
    updated = dict(transaction)
    if cancel_result.get("success"):
        updated.update(
            {
                "success": True,
                "status": "CANCELED",
                "shop_id": cancel_result.get("shopId") or updated.get("shop_id"),
                "shop_name": cancel_result.get("shopName") or updated.get("shop_name"),
                "booking_code": cancel_result.get("bookingCode") or updated.get("booking_code"),
                "people": cancel_result.get("people") or updated.get("people"),
                "date": cancel_result.get("date") or updated.get("date"),
                "time": cancel_result.get("time") or updated.get("time"),
                "table_type": cancel_result.get("tableType") or updated.get("table_type"),
                "needs_deposit": bool(cancel_result.get("needsDeposit", updated.get("needs_deposit"))),
                "deposit_total": cancel_result.get("depositTotal") or updated.get("deposit_total"),
                "error": None,
            }
        )
    else:
        updated.update(
            {
                "success": False,
                "status": "FAILED",
                "error": cancel_result.get("error") or "取消訂位失敗",
            }
        )
    return updated


def _booking_transaction_after_reschedule(transaction: dict, update_result: dict) -> dict:
    updated = dict(transaction)
    if update_result.get("success"):
        updated.update(
            {
                "kind": "booking",
                "success": True,
                "action": "rescheduled",
                "changed": bool(update_result.get("changed", True)),
                "status": update_result.get("status") or updated.get("status"),
                "shop_id": update_result.get("shopId") or updated.get("shop_id"),
                "shop_name": update_result.get("shopName") or updated.get("shop_name"),
                "booking_code": update_result.get("bookingCode") or updated.get("booking_code"),
                "people": update_result.get("people") or updated.get("people"),
                "date": update_result.get("date") or updated.get("date"),
                "time": update_result.get("time") or updated.get("time"),
                "table_type": update_result.get("tableType") or updated.get("table_type"),
                "needs_deposit": bool(update_result.get("needsDeposit", updated.get("needs_deposit"))),
                "deposit_total": update_result.get("depositTotal") or updated.get("deposit_total"),
                "hold_expires_at": update_result.get("holdExpiresAt") or updated.get("hold_expires_at"),
                "error": None,
            }
        )
    else:
        updated.update(
            {
                "success": False,
                "action": "reschedule_failed",
                "status": "RESCHEDULE_FAILED",
                "error": update_result.get("error") or "改單失敗",
            }
        )
    return updated


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


def _latest_booking_transaction(history: list[dict]) -> dict | None:
    for turn in reversed(history):
        tx = turn.get("transaction") if isinstance(turn, dict) else None
        if not isinstance(tx, dict) or tx.get("kind") != "booking":
            continue
        return dict(tx)
    return None


def _latest_booking_context_kind(history: list[dict]) -> str:
    for turn in reversed(history):
        if not isinstance(turn, dict):
            continue
        tx = turn.get("transaction")
        if isinstance(tx, dict) and tx.get("kind") == "booking":
            return "transaction"
        booking_draft = turn.get("booking_draft")
        if isinstance(booking_draft, dict) and booking_draft:
            return "draft"
    return ""


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
- 若候選資料標示「私人記憶:不再推薦」，除非沒有其他候選，不能放進 recommended_shop_ids；可在 narrative 裡簡短說明已避開使用者上次標記的店。
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

    validated = _validate_agent_decision(decision, tool_result, query)
    return AgentRecommendationDecision(
        recommended_shop_ids=validated.recommended_shop_ids,
        narrative=_agent_concierge_narrative(query, tool_result, validated),
        rejected_shop_ids=validated.rejected_shop_ids,
        rejection_summary=validated.rejection_summary,
    )


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
    update_result: dict | None = None
    final_transaction: dict | None = None
    direct_answer: str | None = None


@dataclass
class ToolGuardResult:
    action: str
    args: dict = field(default_factory=dict)
    direct_answer: str | None = None
    final_transaction: dict | None = None
    last_tool_result: dict | None = None


async def _agent_exact_shop_from_query(query: str) -> ToolGuardResult | None:
    if _booking_intent(query) or _payment_intent(query):
        return None

    keyword = _specific_shop_keyword(query)
    if not keyword:
        return None

    hits = await _semantic_hits(keyword, top_k=30)
    selected_shops = _exact_shop_matches_for_keyword(keyword, hits)
    if not selected_shops:
        return None

    selected_ids = [
        int(sid)
        for shop in selected_shops[:1]
        if (sid := _shop_id(shop)) is not None
    ]
    if not selected_ids:
        return None

    search_result = await _build_agent_search_result(keyword, hits, selected_ids)
    search_result["strict_recommended_only"] = True
    shops = search_result.get("shops") if isinstance(search_result, dict) else []
    selected = _shops_for_ids(shops, selected_ids)[0] if isinstance(shops, list) else selected_shops[0]
    name = str(selected.get("name") or keyword)
    answer = (
        f"我已改以「{name}」為準，不沿用前一輪推薦。"
        f"{_shop_advice_text(selected)}。"
        "如果要訂位，請直接回覆日期、時間與人數。"
    )
    rejected_ids = [
        int(sid)
        for shop in hits
        if (sid := _shop_id(shop)) is not None and int(sid) not in selected_ids
    ][:8]
    search_result["agent_decision"] = _decision_payload(
        AgentRecommendationDecision(
            recommended_shop_ids=selected_ids,
            narrative=answer,
            rejected_shop_ids=rejected_ids,
        )
    )
    return ToolGuardResult(action="direct", direct_answer=answer, last_tool_result=search_result)


async def _agent_exact_booking_from_query(query: str) -> ToolGuardResult | None:
    if not _booking_intent(query) or _payment_intent(query):
        return None

    keyword = _booking_shop_keyword(query)
    if not keyword:
        return None

    hits = await _semantic_hits(keyword, top_k=30)
    selected_shops = _exact_shop_matches_for_keyword(keyword, hits)
    if not selected_shops:
        return None

    selected_ids = [
        int(sid)
        for shop in selected_shops[:1]
        if (sid := _shop_id(shop)) is not None
    ]
    if not selected_ids:
        return None

    search_result = await _build_agent_search_result(keyword, hits, selected_ids)
    search_result["strict_recommended_only"] = True
    shops = search_result.get("shops") if isinstance(search_result, dict) else []
    selected = _shops_for_ids(shops, selected_ids)[0] if isinstance(shops, list) else selected_shops[0]
    shop_id = selected_ids[0]
    shop_name = str(selected.get("name") or keyword)

    prefill = _line_booking_prefill_from_text(query)
    missing = []
    if not prefill.get("date"):
        missing.append("日期")
    if not prefill.get("time"):
        missing.append("時間")
    if not prefill.get("people"):
        missing.append("人數")
    if missing:
        draft = _booking_draft_payload(shop_id, shop_name, prefill)
        search_result["booking_draft"] = draft
        return ToolGuardResult(
            action="direct",
            direct_answer=_booking_draft_confirmation_answer(draft, query),
            last_tool_result=search_result,
        )

    draft = _booking_draft_payload(shop_id, shop_name, prefill)
    search_result["booking_draft"] = draft
    return ToolGuardResult(
        action="direct",
        direct_answer=_booking_draft_confirmation_answer(draft, query),
        last_tool_result=search_result,
    )


def _agent_booking_action_from_history(query: str, history: list[dict]) -> ToolGuardResult | None:
    reschedule_intent = _booking_reschedule_intent(query)
    incident_intent = _booking_incident_intent(query)
    if not (
        _payment_intent(query)
        or _booking_status_intent(query)
        or _booking_cancel_intent(query)
        or _booking_cancel_confirmation_intent(query)
        or reschedule_intent
        or incident_intent
    ):
        return None
    if reschedule_intent and _latest_booking_context_kind(history) == "draft":
        return None

    transaction = _latest_booking_transaction(history)
    if not transaction:
        return ToolGuardResult(
            action="direct",
            direct_answer="我目前找不到最近一筆訂位。請提供訂位編號，或先到「我的訂位」確認。",
        )

    if _booking_cancel_confirmation_intent(query):
        mismatch = _booking_cancel_confirmation_mismatch(query, transaction)
        if mismatch:
            return ToolGuardResult(action="direct", direct_answer=mismatch, last_tool_result={"transaction": transaction})
        not_allowed = _booking_cancel_not_allowed_narrative(transaction)
        if not_allowed:
            return ToolGuardResult(action="direct", direct_answer=not_allowed, last_tool_result={"transaction": transaction})
        return ToolGuardResult(
            action="cancel",
            args={"booking_code": str(transaction.get("booking_code"))},
            last_tool_result={"transaction": transaction},
        )

    if reschedule_intent:
        return _booking_reschedule_action(query, transaction)

    if incident_intent:
        return _booking_incident_action(query, transaction)

    if _payment_intent(query):
        if transaction.get("status") == "PENDING_PAYMENT" and transaction.get("needs_deposit") and transaction.get("booking_code"):
            return ToolGuardResult(
                action="continue",
                args={"booking_code": str(transaction.get("booking_code"))},
                last_tool_result={"transaction": transaction},
            )
        return ToolGuardResult(
            action="direct",
            direct_answer=_booking_payment_not_needed_narrative(transaction),
            last_tool_result={"transaction": transaction},
        )

    if _booking_cancel_intent(query):
        return ToolGuardResult(
            action="direct",
            direct_answer=_booking_cancel_prompt(transaction),
            last_tool_result={"transaction": transaction},
        )

    return ToolGuardResult(
        action="direct",
        direct_answer=_booking_status_narrative(transaction),
        last_tool_result={"transaction": transaction},
    )


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
    elif tool_name == "update_booking":
        state.update_result = tool_result

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
    effective_query = _effective_agent_query(query, history)
    contents = _history_to_contents(history, effective_query)
    state = AgentToolState(query=effective_query, session_id=session_id, history=history, contents=contents)
    final_answer = ""

    booking_action = _agent_booking_action_from_history(effective_query, history)
    if booking_action is not None:
        state.last_tool_result = booking_action.last_tool_result or {}
        if booking_action.action == "direct":
            final_answer = booking_action.direct_answer or ""
            if session_id:
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {"role": "model", "content": final_answer},
                    ],
                )
            return final_answer, [], state.last_tool_result
        if booking_action.action == "cancel":
            cancel_result = await tool_cancel_booking(**booking_action.args)
            state.tools_used.append("cancel_booking")
            base_transaction = (booking_action.last_tool_result or {}).get("transaction") or {}
            transaction = _booking_transaction_after_cancel(base_transaction, cancel_result)
            final_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result = {"transaction": transaction}
            if session_id:
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {"role": "model", "content": final_answer, "transaction": transaction},
                    ],
                )
            return final_answer, state.tools_used, state.last_tool_result
        if booking_action.action == "reschedule":
            update_result = await tool_update_booking(**booking_action.args)
            state.tools_used.append("update_booking")
            base_transaction = (booking_action.last_tool_result or {}).get("transaction") or {}
            transaction = _booking_transaction_after_reschedule(base_transaction, update_result)
            final_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result = {"transaction": transaction}
            if session_id:
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {"role": "model", "content": final_answer, "transaction": transaction},
                    ],
                )
            return final_answer, state.tools_used, state.last_tool_result
        if booking_action.action == "incident":
            incident_result = await tool_create_booking_incident(**booking_action.args)
            state.tools_used.append("create_booking_incident")
            base_transaction = (booking_action.last_tool_result or {}).get("transaction") or {}
            transaction = _booking_transaction_after_incident(base_transaction, incident_result)
            final_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result = {"transaction": transaction}
            if session_id:
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {"role": "model", "content": final_answer, "transaction": transaction},
                    ],
                )
            return final_answer, state.tools_used, state.last_tool_result
        guard = _before_tool_call(state, "pay_booking_with_test_card", booking_action.args)
        if guard.action != "stop":
            payment_result = await tool_pay_booking_with_test_card(**guard.args)
            _after_tool_call(state, "pay_booking_with_test_card", payment_result)
            base_transaction = (booking_action.last_tool_result or {}).get("transaction") or {}
            transaction = _booking_transaction_after_payment(base_transaction, payment_result)
            final_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result = {"transaction": transaction}
            if session_id:
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {"role": "model", "content": final_answer, "transaction": transaction},
                    ],
                )
            return final_answer, state.tools_used, state.last_tool_result

    if _explicit_same_day_booking_request(effective_query):
        final_answer = _same_day_booking_policy_answer()
        if session_id:
            session_store.save_history(
                session_id,
                history + [
                    {"role": "user", "content": query},
                    {"role": "model", "content": final_answer},
                ],
            )
        return final_answer, [], {}

    booking_followup = _agent_booking_followup_from_history(effective_query, history)
    if booking_followup is not None:
        if booking_followup.action == "direct":
            final_answer = booking_followup.direct_answer or ""
            state.last_tool_result = booking_followup.last_tool_result or {}
            if session_id:
                recommendation = _recommendation_context_from_tool_result(effective_query, state.last_tool_result)
                booking_draft = (
                    state.last_tool_result.get("booking_draft")
                    if isinstance(state.last_tool_result.get("booking_draft"), dict)
                    else None
                )
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {
                            "role": "model",
                            "content": final_answer,
                            **({"recommendation": recommendation} if recommendation else {}),
                            **({"booking_draft": booking_draft} if booking_draft else {}),
                        },
                    ],
                )
            return final_answer, [], state.last_tool_result

        state.latest_search_result = booking_followup.last_tool_result or {}
        guard = _before_tool_call(state, "create_booking", booking_followup.args)
        if guard.action == "direct":
            final_answer = guard.direct_answer or ""
            state.final_transaction = guard.final_transaction
            state.last_tool_result = guard.last_tool_result or {}
            if session_id:
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {
                            "role": "model",
                            "content": final_answer,
                            **({"transaction": state.final_transaction} if state.final_transaction else {}),
                        },
                    ],
                )
            return final_answer, state.tools_used, state.last_tool_result
        elif guard.action != "stop":
            tool_result = await tool_create_booking(**guard.args)
            _after_tool_call(state, "create_booking", tool_result)
            transaction = _build_booking_transaction(
                state.booking_result,
                state.payment_result,
                state.latest_search_result,
            )
            final_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result["transaction"] = transaction
            if session_id:
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {
                            "role": "model",
                            "content": final_answer,
                            "transaction": state.final_transaction,
                        },
                    ],
                )
            return final_answer, state.tools_used, state.last_tool_result

    exact_booking = await _agent_exact_booking_from_query(effective_query)
    if exact_booking is not None:
        state.latest_search_result = exact_booking.last_tool_result or {}
        state.last_tool_result = exact_booking.last_tool_result or {}
        if exact_booking.action == "direct":
            final_answer = exact_booking.direct_answer or ""
            if session_id:
                recommendation = _recommendation_context_from_tool_result(effective_query, state.last_tool_result)
                booking_draft = (
                    state.last_tool_result.get("booking_draft")
                    if isinstance(state.last_tool_result.get("booking_draft"), dict)
                    else None
                )
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {
                            "role": "model",
                            "content": final_answer,
                            **({"recommendation": recommendation} if recommendation else {}),
                            **({"booking_draft": booking_draft} if booking_draft else {}),
                        },
                    ],
                )
            return final_answer, [], state.last_tool_result
        guard = _before_tool_call(state, "create_booking", exact_booking.args)
        if guard.action == "direct":
            final_answer = guard.direct_answer or ""
            state.final_transaction = guard.final_transaction
            state.last_tool_result = guard.last_tool_result or state.last_tool_result
        elif guard.action != "stop":
            tool_result = await tool_create_booking(**guard.args)
            _after_tool_call(state, "create_booking", tool_result)

    exact_shop = await _agent_exact_shop_from_query(effective_query)
    if exact_shop is not None:
        final_answer = exact_shop.direct_answer or ""
        state.tools_used.append("semantic_shop_search")
        state.last_tool_result = exact_shop.last_tool_result or {}
        if session_id:
            recommendation = _recommendation_context_from_tool_result(effective_query, state.last_tool_result)
            session_store.save_history(
                session_id,
                history + [
                    {"role": "user", "content": query},
                    {
                        "role": "model",
                        "content": final_answer,
                        **({"recommendation": recommendation} if recommendation else {}),
                    },
                ],
            )
        return final_answer, state.tools_used, state.last_tool_result

    recommendation_advice = _agent_recommendation_advice_from_history(effective_query, history)
    if recommendation_advice is not None:
        final_answer = recommendation_advice.direct_answer or ""
        state.last_tool_result = recommendation_advice.last_tool_result or {}
        if session_id:
            session_store.save_history(
                session_id,
                history + [
                    {"role": "user", "content": query},
                    {"role": "model", "content": final_answer},
                ],
            )
        return final_answer, [], state.last_tool_result

    if _restaurant_need_clarification(effective_query):
        final_answer = _restaurant_clarification_text(effective_query)
        if session_id:
            session_store.save_history(
                session_id,
                history + [
                    {"role": "user", "content": query},
                    {"role": "model", "content": final_answer, "clarification_query": effective_query},
                ],
            )
        return final_answer, [], {}

    more_recommendations = await _agent_more_recommendations_from_history(effective_query, history)
    if more_recommendations is not None:
        if more_recommendations.action == "direct":
            final_answer = more_recommendations.direct_answer or ""
            state.last_tool_result = more_recommendations.last_tool_result or {}
            if session_id:
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {"role": "model", "content": final_answer},
                    ],
                )
            return final_answer, [], state.last_tool_result
        state.tools_used.append("semantic_shop_search")
        state.last_tool_result = more_recommendations.last_tool_result or {}

    if (
        state.booking_result is None
        and not final_answer
        and not state.last_tool_result.get("shops")
        and not state.tools_used
        and _agent_should_force_search(effective_query)
    ):
        tool_result = await tool_semantic_search(effective_query)
        _after_tool_call(state, "semantic_shop_search", tool_result)

    for _ in range(4):
        if state.booking_result is not None or final_answer or state.last_tool_result.get("shops"):
            break
        response = generate(
            settings.gemini_agent_model,
            state.contents,
            types.GenerateContentConfig(
                tools=TOOLS,
                system_instruction=_agent_system_prompt(),
                # 低溫讓 tool 選擇與回答路徑可重現；預設 1.0 會造成同問不同答
                temperature=0.2,
            ),
        )

        candidate = response.candidates[0]
        function_call = None
        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_call = part.function_call
                break

        if not function_call:
            if not state.tools_used and _agent_should_force_search(effective_query):
                tool_result = await tool_semantic_search(effective_query)
                _after_tool_call(state, "semantic_shop_search", tool_result)
                break
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
                temperature=0.2,
            ),
        )
        final_answer = filter_output(final.text)

    if state.update_result is not None:
        base_transaction = _latest_booking_transaction(state.history) or {}
        transaction = _booking_transaction_after_reschedule(base_transaction, state.update_result)
        final_answer = _booking_confirmation_narrative(transaction)
        state.final_transaction = transaction
        state.last_tool_result["transaction"] = transaction
    elif state.booking_result is not None:
        transaction = _build_booking_transaction(
            state.booking_result,
            state.payment_result,
            state.latest_search_result,
        )
        final_answer = _booking_confirmation_narrative(transaction)
        state.final_transaction = transaction
        state.last_tool_result["transaction"] = transaction
    elif state.last_tool_result.get("shops"):
        decision = _build_agent_recommendation_decision(effective_query, state.last_tool_result)
        state.last_tool_result = await _enrich_agent_search_result(
            effective_query,
            state.last_tool_result,
            decision.recommended_shop_ids,
        )
        if decision.narrative:
            final_answer = decision.narrative
            state.last_tool_result["agent_decision"] = _decision_payload(decision)

    if session_id:
        recommendation = _recommendation_context_from_tool_result(effective_query, state.last_tool_result)
        new_history = history + [
            {"role": "user", "content": query},
            {
                "role": "model",
                "content": final_answer,
                **({"transaction": state.final_transaction} if state.final_transaction else {}),
                **({"recommendation": recommendation} if recommendation else {}),
            },
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
        **_agent_response_contract(last_tool_result),
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
        private_memory = s.get("private_memory_reason") or ""
        private_offers = s.get("private_ai_offers") or []
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
        if private_memory:
            status = "不再推薦" if s.get("private_memory_status") == "avoid" else "偏好記憶"
            parts.append(f"私人記憶:{status}:{private_memory}")
        if private_offers and isinstance(private_offers, list):
            offer = private_offers[0]
            if isinstance(offer, dict):
                offer_title = str(offer.get("title") or "AI 私密優惠").strip()
                offer_desc = str(offer.get("description") or "").strip()
                offer_until = str(offer.get("validUntil") or "").strip()
                offer_parts = [offer_title]
                if offer_desc:
                    offer_parts.append(offer_desc[:80])
                if offer_until:
                    offer_parts.append(f"有效至{offer_until}")
                parts.append(f"AI私密優惠:{' / '.join(offer_parts)}")
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
    effective_query = _effective_agent_query(query, history)
    contents = _history_to_contents(history, effective_query)
    state = AgentToolState(query=effective_query, session_id=session_id, history=history, contents=contents)
    direct_answer: str | None = None
    yield {"type": "turn_start", "query": query, "session_id": session_id}

    if _explicit_same_day_booking_request(effective_query):
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

    booking_action = _agent_booking_action_from_history(effective_query, history)
    if booking_action is not None:
        state.last_tool_result = booking_action.last_tool_result or {}
        if booking_action.action == "direct":
            full_answer = booking_action.direct_answer or ""
            chunk_size = 18
            for i in range(0, len(full_answer), chunk_size):
                chunk = full_answer[i : i + chunk_size]
                yield {"type": "message_update", "content": chunk}
                yield {"type": "chunk", "content": chunk}
            if session_id:
                recommendation = _recommendation_context_from_tool_result(effective_query, state.last_tool_result)
                booking_draft = (
                    state.last_tool_result.get("booking_draft")
                    if isinstance(state.last_tool_result.get("booking_draft"), dict)
                    else None
                )
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {
                            "role": "model",
                            "content": full_answer,
                            **({"recommendation": recommendation} if recommendation else {}),
                            **({"booking_draft": booking_draft} if booking_draft else {}),
                        },
                    ],
                )
            done_payload = {
                "type": "done",
                "answer": full_answer,
                **_agent_response_contract(state.last_tool_result),
                "tools_used": [],
                "tool_result": state.last_tool_result,
                "session_id": session_id,
            }
            yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
            yield done_payload
            return

        if booking_action.action == "cancel":
            tool_name = "cancel_booking"
            state.tools_used.append(tool_name)
            yield {
                "type": "tool_execution_start",
                "name": tool_name,
                "args": booking_action.args,
                "session_id": session_id,
            }
            cancel_result = await tool_cancel_booking(**booking_action.args)
            yield {
                "type": "tool_execution_end",
                "name": tool_name,
                "result_summary": _tool_result_summary(cancel_result),
                "session_id": session_id,
            }
            yield {"type": "tool", "name": tool_name}
            base_transaction = (booking_action.last_tool_result or {}).get("transaction") or {}
            transaction = _booking_transaction_after_cancel(base_transaction, cancel_result)
            full_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result = {"transaction": transaction}
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
                        {"role": "model", "content": full_answer, "transaction": transaction},
                    ],
                )
            done_payload = {
                "type": "done",
                "answer": full_answer,
                **_agent_response_contract(state.last_tool_result),
                "tools_used": state.tools_used,
                "tool_result": state.last_tool_result,
                "session_id": session_id,
            }
            yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
            yield done_payload
            return

        if booking_action.action == "reschedule":
            tool_name = "update_booking"
            state.tools_used.append(tool_name)
            yield {
                "type": "tool_execution_start",
                "name": tool_name,
                "args": booking_action.args,
                "session_id": session_id,
            }
            update_result = await tool_update_booking(**booking_action.args)
            yield {
                "type": "tool_execution_end",
                "name": tool_name,
                "result_summary": _tool_result_summary(update_result),
                "session_id": session_id,
            }
            yield {"type": "tool", "name": tool_name}
            base_transaction = (booking_action.last_tool_result or {}).get("transaction") or {}
            transaction = _booking_transaction_after_reschedule(base_transaction, update_result)
            full_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result = {"transaction": transaction}
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
                        {"role": "model", "content": full_answer, "transaction": transaction},
                    ],
                )
            done_payload = {
                "type": "done",
                "answer": full_answer,
                **_agent_response_contract(state.last_tool_result),
                "tools_used": state.tools_used,
                "tool_result": state.last_tool_result,
                "session_id": session_id,
            }
            yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
            yield done_payload
            return

        if booking_action.action == "incident":
            tool_name = "create_booking_incident"
            state.tools_used.append(tool_name)
            yield {
                "type": "tool_execution_start",
                "name": tool_name,
                "args": booking_action.args,
                "session_id": session_id,
            }
            incident_result = await tool_create_booking_incident(**booking_action.args)
            yield {
                "type": "tool_execution_end",
                "name": tool_name,
                "result_summary": _tool_result_summary(incident_result),
                "session_id": session_id,
            }
            yield {"type": "tool", "name": tool_name}
            base_transaction = (booking_action.last_tool_result or {}).get("transaction") or {}
            transaction = _booking_transaction_after_incident(base_transaction, incident_result)
            full_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result = {"transaction": transaction}
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
                        {"role": "model", "content": full_answer, "transaction": transaction},
                    ],
                )
            done_payload = {
                "type": "done",
                "answer": full_answer,
                **_agent_response_contract(state.last_tool_result),
                "tools_used": state.tools_used,
                "tool_result": state.last_tool_result,
                "session_id": session_id,
            }
            yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
            yield done_payload
            return

        guard = _before_tool_call(state, "pay_booking_with_test_card", booking_action.args)
        if guard.action != "stop":
            tool_name = "pay_booking_with_test_card"
            yield {
                "type": "tool_execution_start",
                "name": tool_name,
                "args": guard.args,
                "session_id": session_id,
            }
            payment_result = await tool_pay_booking_with_test_card(**guard.args)
            _after_tool_call(state, tool_name, payment_result)
            yield {
                "type": "tool_execution_end",
                "name": tool_name,
                "result_summary": _tool_result_summary(payment_result),
                "session_id": session_id,
            }
            yield {"type": "tool", "name": tool_name}
            base_transaction = (booking_action.last_tool_result or {}).get("transaction") or {}
            transaction = _booking_transaction_after_payment(base_transaction, payment_result)
            full_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result = {"transaction": transaction}
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
                        {"role": "model", "content": full_answer, "transaction": transaction},
                    ],
                )
            done_payload = {
                "type": "done",
                "answer": full_answer,
                **_agent_response_contract(state.last_tool_result),
                "tools_used": state.tools_used,
                "tool_result": state.last_tool_result,
                "session_id": session_id,
            }
            yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
            yield done_payload
            return

    booking_followup = _agent_booking_followup_from_history(effective_query, history)
    if booking_followup is not None:
        if booking_followup.action == "direct":
            full_answer = booking_followup.direct_answer or ""
            state.last_tool_result = booking_followup.last_tool_result or {}
            chunk_size = 18
            for i in range(0, len(full_answer), chunk_size):
                chunk = full_answer[i : i + chunk_size]
                yield {"type": "message_update", "content": chunk}
                yield {"type": "chunk", "content": chunk}
            if session_id:
                recommendation = _recommendation_context_from_tool_result(effective_query, state.last_tool_result)
                booking_draft = (
                    state.last_tool_result.get("booking_draft")
                    if isinstance(state.last_tool_result.get("booking_draft"), dict)
                    else None
                )
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {
                            "role": "model",
                            "content": full_answer,
                            **({"recommendation": recommendation} if recommendation else {}),
                            **({"booking_draft": booking_draft} if booking_draft else {}),
                        },
                    ],
                )
            done_payload = {
                "type": "done",
                "answer": full_answer,
                **_agent_response_contract(state.last_tool_result),
                "tools_used": [],
                "tool_result": state.last_tool_result,
                "session_id": session_id,
            }
            yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
            yield done_payload
            return

        state.latest_search_result = booking_followup.last_tool_result or {}
        guard = _before_tool_call(state, "create_booking", booking_followup.args)
        if guard.action == "direct":
            direct_answer = guard.direct_answer
            state.final_transaction = guard.final_transaction
            state.last_tool_result = guard.last_tool_result or {}
            full_answer = direct_answer or ""
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
                **_agent_response_contract(state.last_tool_result),
                "tools_used": state.tools_used,
                "tool_result": state.last_tool_result,
                "session_id": session_id,
            }
            yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
            yield done_payload
            return
        elif guard.action != "stop":
            tool_name = "create_booking"
            yield {
                "type": "tool_execution_start",
                "name": tool_name,
                "args": guard.args,
                "session_id": session_id,
            }
            tool_result = await tool_create_booking(**guard.args)
            _after_tool_call(state, tool_name, tool_result)
            yield {
                "type": "tool_execution_end",
                "name": tool_name,
                "result_summary": _tool_result_summary(tool_result),
                "session_id": session_id,
            }
            yield {"type": "tool", "name": tool_name}
            transaction = _build_booking_transaction(
                state.booking_result,
                state.payment_result,
                state.latest_search_result,
            )
            full_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result["transaction"] = transaction
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
                            "transaction": state.final_transaction,
                        },
                    ],
                )
            done_payload = {
                "type": "done",
                "answer": full_answer,
                **_agent_response_contract(state.last_tool_result),
                "tools_used": state.tools_used,
                "tool_result": state.last_tool_result,
                "session_id": session_id,
            }
            yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
            yield done_payload
            return

    exact_booking = await _agent_exact_booking_from_query(effective_query)
    if exact_booking is not None:
        tool_name = "semantic_shop_search"
        state.tools_used.append(tool_name)
        state.latest_search_result = exact_booking.last_tool_result or {}
        state.last_tool_result = exact_booking.last_tool_result or {}
        yield {
            "type": "tool_execution_start",
            "name": tool_name,
            "args": {"query": _specific_shop_keyword(effective_query) or effective_query},
            "session_id": session_id,
        }
        yield {
            "type": "tool_execution_end",
            "name": tool_name,
            "result_summary": _tool_result_summary(state.last_tool_result),
            "session_id": session_id,
        }
        yield {"type": "tool", "name": tool_name}

        if exact_booking.action == "direct":
            full_answer = exact_booking.direct_answer or ""
            chunk_size = 18
            for i in range(0, len(full_answer), chunk_size):
                chunk = full_answer[i : i + chunk_size]
                yield {"type": "message_update", "content": chunk}
                yield {"type": "chunk", "content": chunk}
            if session_id:
                recommendation = _recommendation_context_from_tool_result(effective_query, state.last_tool_result)
                booking_draft = (
                    state.last_tool_result.get("booking_draft")
                    if isinstance(state.last_tool_result.get("booking_draft"), dict)
                    else None
                )
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {
                            "role": "model",
                            "content": full_answer,
                            **({"recommendation": recommendation} if recommendation else {}),
                            **({"booking_draft": booking_draft} if booking_draft else {}),
                        },
                    ],
                )
            done_payload = {
                "type": "done",
                "answer": full_answer,
                **_agent_response_contract(state.last_tool_result),
                "tools_used": state.tools_used,
                "tool_result": state.last_tool_result,
                "session_id": session_id,
            }
            yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
            yield done_payload
            return

        guard = _before_tool_call(state, "create_booking", exact_booking.args)
        if guard.action == "direct":
            direct_answer = guard.direct_answer
            state.final_transaction = guard.final_transaction
            state.last_tool_result = guard.last_tool_result or state.last_tool_result
        elif guard.action != "stop":
            tool_name = "create_booking"
            yield {
                "type": "tool_execution_start",
                "name": tool_name,
                "args": guard.args,
                "session_id": session_id,
            }
            tool_result = await tool_create_booking(**guard.args)
            _after_tool_call(state, tool_name, tool_result)
            yield {
                "type": "tool_execution_end",
                "name": tool_name,
                "result_summary": _tool_result_summary(tool_result),
                "session_id": session_id,
            }
            yield {"type": "tool", "name": tool_name}

    exact_shop = await _agent_exact_shop_from_query(effective_query)
    if exact_shop is not None:
        tool_name = "semantic_shop_search"
        state.tools_used.append(tool_name)
        state.last_tool_result = exact_shop.last_tool_result or {}
        yield {
            "type": "tool_execution_start",
            "name": tool_name,
            "args": {"query": _specific_shop_keyword(effective_query) or effective_query},
            "session_id": session_id,
        }
        yield {
            "type": "tool_execution_end",
            "name": tool_name,
            "result_summary": _tool_result_summary(state.last_tool_result),
            "session_id": session_id,
        }
        yield {"type": "tool", "name": tool_name}
        full_answer = exact_shop.direct_answer or ""
        chunk_size = 18
        for i in range(0, len(full_answer), chunk_size):
            chunk = full_answer[i : i + chunk_size]
            yield {"type": "message_update", "content": chunk}
            yield {"type": "chunk", "content": chunk}
        if session_id:
            recommendation = _recommendation_context_from_tool_result(effective_query, state.last_tool_result)
            session_store.save_history(
                session_id,
                history + [
                    {"role": "user", "content": query},
                    {
                        "role": "model",
                        "content": full_answer,
                        **({"recommendation": recommendation} if recommendation else {}),
                    },
                ],
            )
        done_payload = {
            "type": "done",
            "answer": full_answer,
            **_agent_response_contract(state.last_tool_result),
            "tools_used": state.tools_used,
            "tool_result": state.last_tool_result,
            "session_id": session_id,
        }
        yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
        yield done_payload
        return

    recommendation_advice = _agent_recommendation_advice_from_history(effective_query, history)
    if recommendation_advice is not None:
        full_answer = recommendation_advice.direct_answer or ""
        state.last_tool_result = recommendation_advice.last_tool_result or {}
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
            **_agent_response_contract(state.last_tool_result),
            "tools_used": [],
            "tool_result": state.last_tool_result,
            "session_id": session_id,
        }
        yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
        yield done_payload
        return

    if _restaurant_need_clarification(effective_query):
        full_answer = _restaurant_clarification_text(effective_query)
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
                    {"role": "model", "content": full_answer, "clarification_query": effective_query},
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

    more_recommendations = await _agent_more_recommendations_from_history(effective_query, history)
    if more_recommendations is not None:
        if more_recommendations.action == "direct":
            full_answer = more_recommendations.direct_answer or ""
            state.last_tool_result = more_recommendations.last_tool_result or {}
            chunk_size = 18
            for i in range(0, len(full_answer), chunk_size):
                chunk = full_answer[i : i + chunk_size]
                yield {"type": "message_update", "content": chunk}
                yield {"type": "chunk", "content": chunk}
            if session_id:
                recommendation = _recommendation_context_from_tool_result(effective_query, state.last_tool_result)
                session_store.save_history(
                    session_id,
                    history + [
                        {"role": "user", "content": query},
                        {
                            "role": "model",
                            "content": full_answer,
                            **({"recommendation": recommendation} if recommendation else {}),
                        },
                    ],
                )
            done_payload = {
                "type": "done",
                "answer": full_answer,
                **_agent_response_contract(state.last_tool_result),
                "tools_used": [],
                "tool_result": state.last_tool_result,
                "session_id": session_id,
            }
            yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
            yield done_payload
            return

        tool_name = "semantic_shop_search"
        yield {
            "type": "tool_execution_start",
            "name": tool_name,
            "args": {"query": str(_latest_recommendation_context(history).get("query") or effective_query)},
            "session_id": session_id,
        }
        state.tools_used.append(tool_name)
        state.last_tool_result = more_recommendations.last_tool_result or {}
        yield {
            "type": "tool_execution_end",
            "name": tool_name,
            "result_summary": _tool_result_summary(state.last_tool_result),
            "session_id": session_id,
        }
        yield {"type": "tool", "name": tool_name}

    if (
        state.booking_result is None
        and direct_answer is None
        and not state.last_tool_result.get("shops")
        and not state.tools_used
        and _agent_should_force_search(effective_query)
    ):
        tool_name = "semantic_shop_search"
        tool_args = {"query": effective_query}
        yield {
            "type": "tool_execution_start",
            "name": tool_name,
            "args": tool_args,
            "session_id": session_id,
        }
        tool_result = await tool_semantic_search(effective_query)
        _after_tool_call(state, tool_name, tool_result)
        yield {
            "type": "tool_execution_end",
            "name": tool_name,
            "result_summary": _tool_result_summary(tool_result),
            "session_id": session_id,
        }
        yield {"type": "tool", "name": tool_name}

    # Phase 1: tool-calling loop (sync) — yields tool events as each fires
    for _ in range(4):
        if state.booking_result is not None or direct_answer is not None or state.last_tool_result.get("shops"):
            break
        response = generate(
            settings.gemini_agent_model,
            state.contents,
            types.GenerateContentConfig(
                tools=TOOLS,
                system_instruction=_agent_system_prompt(),
                # 與非串流版一致：低溫穩定 tool 選擇
                temperature=0.2,
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
                if _agent_should_force_search(effective_query):
                    tool_name = "semantic_shop_search"
                    tool_args = {"query": effective_query}
                    yield {
                        "type": "tool_execution_start",
                        "name": tool_name,
                        "args": tool_args,
                        "session_id": session_id,
                    }
                    tool_result = await tool_semantic_search(effective_query)
                    _after_tool_call(state, tool_name, tool_result)
                    yield {
                        "type": "tool_execution_end",
                        "name": tool_name,
                        "result_summary": _tool_result_summary(tool_result),
                        "session_id": session_id,
                    }
                    yield {"type": "tool", "name": tool_name}
                    break
                # Zero tool calls — answer already computed; fast path, chunk as-is
                direct_answer = filter_output(response.text)
                if _booking_intent(effective_query):
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
        if state.update_result is not None:
            base_transaction = _latest_booking_transaction(state.history) or {}
            transaction = _booking_transaction_after_reschedule(base_transaction, state.update_result)
            full_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result["transaction"] = transaction
        elif state.booking_result is not None:
            transaction = _build_booking_transaction(
                state.booking_result,
                state.payment_result,
                state.latest_search_result,
            )
            full_answer = _booking_confirmation_narrative(transaction)
            state.final_transaction = transaction
            state.last_tool_result["transaction"] = transaction
        else:
            clarification = _booking_branch_clarification_from_search(effective_query, state.last_tool_result)
            if clarification:
                full_answer = clarification
            else:
                decision = _build_agent_recommendation_decision(effective_query, state.last_tool_result)
                state.last_tool_result = await _enrich_agent_search_result(
                    effective_query,
                    state.last_tool_result,
                    decision.recommended_shop_ids,
                )
                full_answer = decision.narrative
                state.last_tool_result["agent_decision"] = _decision_payload(decision)
        chunk_size = 18
        for i in range(0, len(full_answer), chunk_size):
            chunk = full_answer[i : i + chunk_size]
            yield {"type": "message_update", "content": chunk}
            yield {"type": "chunk", "content": chunk}

    if session_id:
        recommendation = _recommendation_context_from_tool_result(effective_query, state.last_tool_result)
        booking_draft = (
            state.last_tool_result.get("booking_draft")
            if isinstance(state.last_tool_result.get("booking_draft"), dict)
            else None
        )
        session_store.save_history(
            session_id,
            history + [
                {"role": "user", "content": query},
                {
                    "role": "model",
                    "content": full_answer,
                    **({"transaction": state.final_transaction} if state.final_transaction else {}),
                    **({"recommendation": recommendation} if recommendation else {}),
                    **({"booking_draft": booking_draft} if booking_draft else {}),
                },
            ],
        )

    done_payload = {
        "type": "done",
        "answer": full_answer,
        **_agent_response_contract(state.last_tool_result),
        "tools_used": state.tools_used,
        "tool_result": state.last_tool_result,
        "session_id": session_id,
    }
    yield {"type": "agent_end", **{key: value for key, value in done_payload.items() if key != "type"}}
    yield done_payload


@app.post("/api/ai/agent/stream")
async def agent_stream(req: AgentRequest, request: Request):
    """SSE stream for multi-turn agent. Tool calls sync; final synthesis true-streamed via Gemini."""
    try:
        check_input(req.query)
    except GuardrailViolation as exc:
        raise HTTPException(400, f"input rejected: {exc}") from exc

    session_id = req.session_id or ""
    bearer = request.headers.get("Authorization", "")
    auth_token = bearer.removeprefix("Bearer ").strip() if bearer.startswith("Bearer ") else ""
    ai_requests.labels(endpoint="agent_stream").inc()

    async def event_gen() -> AsyncIterator[bytes]:
        token_context = _agent_auth_token.set(auth_token)
        yield _sse_frame({"type": "agent_start", "session_id": session_id})
        yield _sse_frame({"type": "status", "message": "thinking"})
        try:
            async for payload in _run_agent_turn_stream(req.query, session_id):
                yield _sse_frame(payload)
        except Exception as exc:
            logger.exception("agent_stream_failed")
            yield _sse_frame({"type": "agent_error", "message": str(exc), "session_id": session_id})
            yield _sse_frame({"type": "error", "message": str(exc)})
        finally:
            _agent_auth_token.reset(token_context)

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
        logger.warning(
            "line_webhook_invalid_signature verify=%s signature_present=%s secret_len=%s body_len=%s",
            settings.line_signature_verify,
            bool(signature),
            len((settings.line_channel_secret or "").strip()),
            len(body_bytes),
        )
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


@app.post("/internal/line/availability-released")
async def internal_line_availability_released(request: Request):
    payload = await request.json()
    _verify_internal_line_secret(payload)
    line_user_id = str(payload.get("lineUserId") or "").strip()
    if not line_user_id:
        return {"ok": True, "skipped": True, "reason": "No LINE user id"}
    result = await push_messages(
        user_id=line_user_id,
        messages=[_line_availability_flex_message(payload)],
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled or settings.line_background_push_enabled,
    )
    return {"ok": bool(result.get("ok")), "line_result": result}


@app.post("/internal/line/booking-updated")
async def internal_line_booking_updated(request: Request):
    payload = await request.json()
    _verify_internal_line_secret(payload)
    line_user_id = str(payload.get("lineUserId") or "").strip()
    if not line_user_id:
        return {"ok": True, "skipped": True, "reason": "No LINE user id"}
    phase = str(payload.get("phase") or "").strip() or "updated"
    booking = payload.get("booking") if isinstance(payload.get("booking"), dict) else payload
    _save_line_booking_state(line_user_id, booking, phase)
    result = await push_messages(
        user_id=line_user_id,
        messages=[_line_booking_flex_message(booking, phase, line_user_id=line_user_id)],
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled or settings.line_background_push_enabled,
    )
    return {"ok": bool(result.get("ok")), "line_result": result}


@app.post("/internal/line/booking-incident")
async def internal_line_booking_incident(request: Request):
    payload = await request.json()
    _verify_internal_line_secret(payload)
    line_user_id = str(payload.get("lineUserId") or "").strip()
    if not line_user_id:
        return {"ok": True, "skipped": True, "reason": "No LINE user id"}
    incident = payload.get("incident") if isinstance(payload.get("incident"), dict) else payload
    result = await push_messages(
        user_id=line_user_id,
        messages=[_line_booking_incident_flex_message(incident, line_user_id=line_user_id)],
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled or settings.line_background_push_enabled,
    )
    return {"ok": bool(result.get("ok")), "line_result": result}


@app.post("/internal/line/booking-incident-proposal")
async def internal_line_booking_incident_proposal(request: Request):
    payload = await request.json()
    _verify_internal_line_secret(payload)
    line_user_id = str(payload.get("lineUserId") or "").strip()
    if not line_user_id:
        return {"ok": True, "skipped": True, "reason": "No LINE user id"}
    incident = payload.get("incident") if isinstance(payload.get("incident"), dict) else payload
    result = await push_messages(
        user_id=line_user_id,
        messages=[_line_booking_incident_proposal_flex_message(incident, line_user_id=line_user_id)],
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled or settings.line_background_push_enabled,
    )
    return {"ok": bool(result.get("ok")), "line_result": result}


@app.post("/internal/line/refund-operations-digest")
async def internal_line_refund_operations_digest(request: Request):
    payload = await request.json()
    _verify_internal_line_secret(payload)
    line_user_id = str(payload.get("lineUserId") or "").strip()
    if not line_user_id:
        return {"ok": True, "skipped": True, "reason": "No LINE user id"}
    report = payload.get("report") if isinstance(payload.get("report"), dict) else payload
    result = await push_messages(
        user_id=line_user_id,
        messages=[_line_refund_operations_digest_flex_message(report)],
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled or settings.line_background_push_enabled,
    )
    return {"ok": bool(result.get("ok")), "line_result": result}


@app.post("/internal/line/parking-reminder")
async def internal_line_parking_reminder(request: Request):
    payload = await request.json()
    _verify_internal_line_secret(payload)
    line_user_id = str(payload.get("lineUserId") or "").strip()
    if not line_user_id:
        return {"ok": True, "skipped": True, "reason": "No LINE user id"}
    result = await push_messages(
        user_id=line_user_id,
        messages=[_line_parking_reminder_flex_message(payload)],
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled or settings.line_background_push_enabled,
    )
    return {"ok": bool(result.get("ok")), "line_result": result}


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
async def line_shop_detail(
    shop_id: int,
    lt: str = "",
    lineUserId: str = "",
    name: str = "",
    district: str = "",
    mrt: str = "",
    avgPrice: str = "",
):
    line_user_id, line_token = _line_context(lt, lineUserId)
    shop = await _fetch_java_shop(shop_id)
    if not shop:
        shop = _line_shop_fallback_from_query(shop_id, name, district, mrt, avgPrice)
    if not shop:
        shop = _line_shop_fallback_from_media(shop_id)
    if not shop:
        shop = _line_shop_minimal_fallback(shop_id)
    if not shop:
        return HTMLResponse(_line_html_page("找不到店家", "這間店目前無法取得資料。", []), status_code=404)
    metadata = await _fetch_java_ai_metadata(shop_id)
    policy = await _fetch_java_booking_policy(shop_id)
    parking_lots = await _fetch_java_nearby_parking(shop.get("x"), shop.get("y"), limit=3)
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
    hours = _line_business_hours(shop, metadata)[:7]
    price = _html_escape(str(metadata.get("pricePerPerson") or (f"NT$ {avg_price}" if avg_price else "價位未標示")))
    booking = _html_escape(str(metadata.get("bookingDifficulty") or "可查看訂位狀態"))
    deposit = _line_deposit_summary(policy)
    review_groups = _line_review_groups(shop_id)
    image_uri = _html_escape(_line_detail_image_uri(shop_id))
    booking_uri = _line_public_uri(
        _line_booking_path(
            shop_id,
            line_token,
            str(shop.get("name") or ""),
            str(shop.get("district") or ""),
            str(shop.get("mrtStation") or shop.get("mrt_station") or ""),
            str(avg_price or ""),
        )
    )
    map_uri = _line_google_maps_uri(str(shop.get("name") or ""), str(shop.get("address") or ""))
    map_link = _html_escape(map_uri)
    basis_items = _line_recommendation_basis(shop, metadata, manifest_shop)
    rating_label = _line_display_rating(rating)
    info_bits = [
        district or "台北",
        f"捷運{mrt}" if mrt else "",
        price,
        f"Google {rating_label} 分" if rating_label else "",
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
        {_line_parking_html(parking_lots)}
        <div class="actions">
          <a class="primary" href="{booking_uri}">填日期人數</a>
          {f'<a class="secondary" href="#parking">附近停車場</a>' if parking_lots else ''}
          <a class="secondary" href="{map_link}">Google 地圖開啟</a>
        </div>
      </main>
    """
    return HTMLResponse(_line_shell(name, body))


@app.get("/line/book/{shop_id}", response_class=HTMLResponse)
async def line_booking_entry(
    shop_id: int,
    lt: str = "",
    lineUserId: str = "",
    name: str = "",
    district: str = "",
    mrt: str = "",
    avgPrice: str = "",
    people: int = 2,
    date: str = "",
    time: str = "19:00",
    tableType: str = "normal",
):
    line_user_id, line_token = _line_context(lt, lineUserId)
    if not line_user_id or not line_token:
        return _line_auth_required_page(shop_id, line_token)
    shop = await _fetch_java_shop(shop_id)
    if not shop:
        shop = _line_shop_fallback_from_query(shop_id, name, district, mrt, avgPrice)
    if not shop:
        shop = _line_shop_fallback_from_media(shop_id)
    if not shop:
        shop = _line_shop_minimal_fallback(shop_id)
    policy = await _fetch_java_booking_policy(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    district = _html_escape(str((shop or {}).get("district") or ""))
    address = _html_escape(str((shop or {}).get("address") or ""))
    tomorrow = taipei_today() + timedelta(days=1)
    selected_date = date if date else tomorrow.isoformat()
    selected_people = min(12, max(1, int(people or 2)))
    selected_time = time if time else "19:00"
    selected_table_type = tableType if tableType in {"normal", "bar", "private"} else "normal"
    deposit_summary = _html_escape(_line_deposit_summary(policy))
    detail_uri = _line_public_uri(
        f"/line/shop/{shop_id}?lt={quote_plus(line_token)}&name={quote_plus(str((shop or {}).get('name') or ''))}&district={quote_plus(str((shop or {}).get('district') or ''))}&mrt={quote_plus(str((shop or {}).get('mrtStation') or (shop or {}).get('mrt_station') or ''))}&avgPrice={quote_plus(str((shop or {}).get('avgPrice') or (shop or {}).get('avg_price') or ''))}"
    )
    confirm_uri = _line_public_uri(f"/line/book/{shop_id}/confirm")
    escaped_line_token = _html_escape(line_token)
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
                {''.join(f'<option value="{count}"{" selected" if count == selected_people else ""}>{count} 人</option>' for count in range(1, 13))}
              </select>
            </label>
            <label>日期
              <input name="date" type="date" min="{tomorrow.isoformat()}" value="{_html_escape(selected_date)}" required>
            </label>
            <label>時間
              <select name="time">
                {''.join(f'<option value="{slot}"{" selected" if slot == selected_time else ""}>{slot}</option>' for slot in ["11:30", "12:00", "12:30", "18:00", "18:30", "19:00", "19:30", "20:00"])}
              </select>
            </label>
            <input type="hidden" name="tableType" value="{_html_escape(selected_table_type)}">
            <input type="hidden" name="lt" value="{escaped_line_token}">
            <input type="hidden" name="name" value="{name}">
            <input type="hidden" name="district" value="{district}">
            <input type="hidden" name="mrt" value="{_html_escape(str((shop or {}).get("mrtStation") or (shop or {}).get("mrt_station") or ""))}">
            <input type="hidden" name="avgPrice" value="{_html_escape(str((shop or {}).get("avgPrice") or (shop or {}).get("avg_price") or ""))}">
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
async def line_booking_confirm(
    shop_id: int,
    people: int = 2,
    date: str = "",
    time: str = "19:00",
    tableType: str = "normal",
    lt: str = "",
    lineUserId: str = "",
    name: str = "",
    district: str = "",
    mrt: str = "",
    avgPrice: str = "",
):
    line_user_id, line_token = _line_context(lt, lineUserId)
    if not line_user_id or not line_token:
        return _line_auth_required_page(shop_id, line_token)
    shop = await _fetch_java_shop(shop_id)
    if not shop:
        shop = _line_shop_fallback_from_query(shop_id, name, district, mrt, avgPrice)
    if not shop:
        shop = _line_shop_fallback_from_media(shop_id)
    if not shop:
        shop = _line_shop_minimal_fallback(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    error = _validate_line_booking(people, date, time, tableType)
    if error:
        return HTMLResponse(
            _line_html_page(
                "訂位資料需要修正",
                error,
                [
                    ("返回填寫", _line_public_uri(f"/line/book/{shop_id}?lt={quote_plus(line_token)}")),
                    ("查看店家資訊", _line_public_uri(f"/line/shop/{shop_id}")),
                ],
            ),
            status_code=400,
        )

    result = await _reserve_line_booking(shop_id, people, date, time, tableType, line_user_id, line_token)
    if not result.get("success"):
        message = str(result.get("errorMsg") or "訂位建立失敗，請稍後再試。")
        watch_uri = _line_public_uri(
            f"/line/availability/watch?shopId={shop_id}&people={people}&date={quote_plus(date)}&time={quote_plus(time)}&tableType={quote_plus(tableType)}&lt={quote_plus(line_token)}"
        )
        return HTMLResponse(
            _line_html_page(
                "訂位未完成",
                message,
                [
                    ("通知我有空位", watch_uri),
                    ("重新填寫", _line_public_uri(f"/line/book/{shop_id}?lt={quote_plus(line_token)}")),
                    ("查看店家資訊", _line_public_uri(f"/line/shop/{shop_id}")),
                ],
            ),
            status_code=409,
        )

    booking = result.get("data") if isinstance(result.get("data"), dict) else {}
    return HTMLResponse(_line_booking_result_page(shop_id, name, booking, line_user_id, line_token))


@app.get("/line/book/{shop_id}/pay", response_class=HTMLResponse)
async def line_booking_pay(shop_id: int, bookingCode: str, lt: str = "", lineUserId: str = ""):
    line_user_id, line_token = _line_context(lt, lineUserId)
    shop = await _fetch_java_shop(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    booking = await _fetch_line_booking(bookingCode, line_user_id, line_token)
    if not booking:
        return HTMLResponse(
            _line_html_page(
                "付款未完成",
                "找不到這筆訂位，請回到訂位狀態確認。",
                [
                    ("查看訂位狀態", _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(bookingCode)}&lt={quote_plus(line_token)}")),
                    ("返回店家資訊", _line_public_uri(f"/line/shop/{shop_id}")),
                ],
            ),
            status_code=404,
        )
    status = str(booking.get("status") or "")
    if status != "PENDING_PAYMENT":
        return HTMLResponse(_line_booking_result_page(shop_id, name, booking, line_user_id, line_token))
    return HTMLResponse(_line_booking_payment_page(shop_id, name, booking, line_token))


@app.post("/line/book/{shop_id}/pay/confirm", response_class=HTMLResponse)
async def line_booking_pay_confirm(request: Request, shop_id: int, bookingCode: str, lt: str = "", lineUserId: str = ""):
    line_user_id, line_token = _line_context(lt, lineUserId)
    payment_method = await _line_payment_method_from_request(request)
    shop = await _fetch_java_shop(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    result = await _pay_line_booking(bookingCode, line_user_id, line_token)
    if not result.get("success"):
        message = str(result.get("errorMsg") or "訂金付款失敗，請稍後再試。")
        return HTMLResponse(
            _line_html_page(
                "付款未完成",
                message,
                [
                    ("查看訂位狀態", _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(bookingCode)}&lt={quote_plus(line_token)}")),
                    ("返回店家資訊", _line_public_uri(f"/line/shop/{shop_id}")),
                ],
            ),
            status_code=409,
        )

    payment = result.get("data") if isinstance(result.get("data"), dict) else {}
    payment["method"] = payment_method
    payment["methodLabel"] = _line_payment_method_label(payment_method)
    booking = await _fetch_line_booking(bookingCode, line_user_id, line_token) or {
        "bookingCode": bookingCode,
        "shopId": shop_id,
        "shopName": str((shop or {}).get("name") or f"店家 {shop_id}"),
        "status": payment.get("status") or "PAID",
        "paymentTransId": payment.get("rec_trade_id"),
        "depositTotal": payment.get("amount"),
    }
    return HTMLResponse(_line_booking_result_page(shop_id, name, booking, line_user_id, line_token, payment=payment))


async def _line_payment_method_from_request(request: Request) -> str:
    try:
        body = (await request.body()).decode("utf-8")
    except Exception:
        body = ""
    values = parse_qs(body)
    raw = str((values.get("paymentMethod") or ["credit_card"])[0] or "credit_card")
    return raw if raw in _LINE_PAYMENT_METHOD_LABELS else "credit_card"


_LINE_PAYMENT_METHOD_LABELS = {
    "credit_card": "信用卡",
    "line_pay": "LINE Pay",
    "apple_pay": "Apple Pay",
    "jkos_pay": "街口支付",
}


def _line_payment_method_label(method: str) -> str:
    return _LINE_PAYMENT_METHOD_LABELS.get(method, "信用卡")


def _line_booking_payment_page(shop_id: int, escaped_shop_name: str, booking: dict, line_token: str) -> str:
    booking_code_raw = str(booking.get("bookingCode") or "")
    booking_code = _html_escape(booking_code_raw)
    people = _html_escape(str(booking.get("people") or ""))
    booking_date = _html_escape(str(booking.get("date") or ""))
    booking_time = _html_escape(str(booking.get("time") or ""))
    deposit_total = _html_escape(str(booking.get("depositTotal") or 0))
    hold_expires_at = _html_escape(str(booking.get("holdExpiresAt") or ""))
    confirm_uri = _line_public_uri(
        f"/line/book/{shop_id}/pay/confirm?bookingCode={quote_plus(booking_code_raw)}&lt={quote_plus(line_token)}"
    )
    status_uri = _line_public_uri(
        f"/line/book/{shop_id}/status?bookingCode={quote_plus(booking_code_raw)}&lt={quote_plus(line_token)}"
    )
    body = f"""
      <main>
        <p class="eyebrow">ByteBites 訂金付款</p>
        <h1>確認訂金付款</h1>
        <div class="meta">{escaped_shop_name} · {booking_date} {booking_time} · {people} 人</div>
        <section>
          <h2>付款金額</h2>
          <p><strong>NT$ {deposit_total}</strong></p>
          <p>訂位編號：<strong>{booking_code}</strong></p>
          <p>座位保留到：{hold_expires_at or "依系統狀態為準"}</p>
        </section>
        <form class="actions" method="post" action="{confirm_uri}">
          <section>
            <h2>選擇付款方式</h2>
            <div class="payment-options" role="radiogroup" aria-label="付款方式">
              <label class="payment-option">
                <input type="radio" name="paymentMethod" value="credit_card" checked>
                <strong>信用卡</strong><span>TapPay sandbox 測試卡</span>
              </label>
              <label class="payment-option">
                <input type="radio" name="paymentMethod" value="line_pay">
                <strong>LINE Pay</strong><span>Demo wallet authorization</span>
              </label>
              <label class="payment-option">
                <input type="radio" name="paymentMethod" value="apple_pay">
                <strong>Apple Pay</strong><span>Demo wallet authorization</span>
              </label>
              <label class="payment-option">
                <input type="radio" name="paymentMethod" value="jkos_pay">
                <strong>街口支付</strong><span>Demo wallet authorization</span>
              </label>
            </div>
          </section>
          <button class="primary" type="submit">確認 demo 付款</button>
          <a class="secondary" href="{status_uri}">返回訂位狀態</a>
        </form>
      </main>
    """
    return _line_shell("確認訂金付款", body)


@app.get("/line/book/{shop_id}/status", response_class=HTMLResponse)
async def line_booking_status(shop_id: int, bookingCode: str, lt: str = "", lineUserId: str = ""):
    line_user_id, line_token = _line_context(lt, lineUserId)
    shop = await _fetch_java_shop(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    booking = await _fetch_line_booking(bookingCode, line_user_id, line_token)
    if not booking:
        return HTMLResponse(
            _line_html_page(
                "找不到訂位",
                "目前查不到這筆訂位，請確認訂位編號是否正確。",
                [("返回店家資訊", _line_public_uri(f"/line/shop/{shop_id}"))],
            ),
            status_code=404,
        )
    return HTMLResponse(_line_booking_result_page(shop_id, name, booking, line_user_id, line_token))


@app.get("/line/book/{shop_id}/incident-proposal/accept", response_class=HTMLResponse)
async def line_booking_incident_proposal_accept(
    shop_id: int,
    bookingCode: str,
    incidentId: int,
    lt: str = "",
    lineUserId: str = "",
):
    line_user_id, line_token = _line_context(lt, lineUserId)
    shop = await _fetch_java_shop(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    result = await _respond_line_incident_proposal(
        bookingCode,
        incidentId,
        "accept",
        line_user_id,
        line_token,
    )
    if not result.get("success"):
        message = str(result.get("errorMsg") or "替代時段確認失敗，請稍後再試。")
        return HTMLResponse(
            _line_html_page(
                "提案未完成",
                message,
                [("查看訂位狀態", _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(bookingCode)}&lt={quote_plus(line_token)}"))],
            ),
            status_code=409,
        )
    booking = result.get("data") if isinstance(result.get("data"), dict) else {}
    return HTMLResponse(
        _line_incident_proposal_response_page(
            "已接受替代時段",
            name,
            booking,
            shop_id,
            bookingCode,
            line_token,
            accepted=True,
        )
    )


@app.get("/line/book/{shop_id}/incident-proposal/decline", response_class=HTMLResponse)
async def line_booking_incident_proposal_decline(
    shop_id: int,
    bookingCode: str,
    incidentId: int,
    lt: str = "",
    lineUserId: str = "",
):
    line_user_id, line_token = _line_context(lt, lineUserId)
    shop = await _fetch_java_shop(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    result = await _respond_line_incident_proposal(
        bookingCode,
        incidentId,
        "decline",
        line_user_id,
        line_token,
    )
    if not result.get("success"):
        message = str(result.get("errorMsg") or "替代時段回覆失敗，請稍後再試。")
        return HTMLResponse(
            _line_html_page(
                "提案未完成",
                message,
                [("查看訂位狀態", _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(bookingCode)}&lt={quote_plus(line_token)}"))],
            ),
            status_code=409,
        )
    booking = result.get("data") if isinstance(result.get("data"), dict) else {}
    return HTMLResponse(
        _line_incident_proposal_response_page(
            "已拒絕替代時段",
            name,
            booking,
            shop_id,
            bookingCode,
            line_token,
            accepted=False,
        )
    )


@app.get("/line/book/{shop_id}/parking", response_class=HTMLResponse)
async def line_booking_parking_preference(
    shop_id: int,
    bookingCode: str,
    driving: bool = True,
    lt: str = "",
    lineUserId: str = "",
):
    line_user_id, line_token = _line_context(lt, lineUserId)
    shop = await _fetch_java_shop(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    result = await _update_line_parking_preference(bookingCode, line_user_id, line_token, driving)
    if not result.get("success"):
        message = str(result.get("errorMsg") or "目前無法更新停車提醒，請稍後再試。")
        return HTMLResponse(
            _line_html_page(
                "停車提醒未更新",
                message,
                [
                    ("查看訂位狀態", _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(bookingCode)}&lt={quote_plus(line_token)}")),
                    ("返回店家資訊", _line_public_uri(f"/line/shop/{shop_id}")),
                ],
            ),
            status_code=409,
        )
    booking = result.get("data") if isinstance(result.get("data"), dict) else {}
    parking_lots = await _fetch_java_nearby_parking((shop or {}).get("x"), (shop or {}).get("y"), limit=3)
    return HTMLResponse(_line_parking_preference_page(shop_id, name, booking, parking_lots, line_token, driving))


@app.get("/line/book/{shop_id}/parking-reserve", response_class=HTMLResponse)
async def line_booking_parking_reserve(
    shop_id: int,
    bookingCode: str,
    lot: int = 0,
    confirm: bool = False,
    lt: str = "",
    lineUserId: str = "",
):
    line_user_id, line_token = _line_context(lt, lineUserId)
    shop = await _fetch_java_shop(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    booking = await _fetch_line_booking(bookingCode, line_user_id, line_token)
    if not booking:
        return HTMLResponse(
            _line_html_page(
                "找不到訂位",
                "目前查不到這筆訂位，請確認訂位編號是否正確。",
                [("返回店家資訊", _line_public_uri(f"/line/shop/{shop_id}"))],
            ),
            status_code=404,
        )

    parking_lots = await _fetch_java_nearby_parking((shop or {}).get("x"), (shop or {}).get("y"), limit=3)
    if not parking_lots:
        return HTMLResponse(
            _line_html_page(
                "暫無可保留車位",
                "目前附近停車場資料更新中，建議先使用導航前往鄰近停車場。",
                [
                    ("查看訂位狀態", _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(bookingCode)}&lt={quote_plus(line_token)}")),
                    ("返回店家資訊", _line_public_uri(f"/line/shop/{shop_id}")),
                ],
            ),
            status_code=409,
        )

    lot_index = max(0, min(int(lot or 0), len(parking_lots) - 1))
    selected_lot = parking_lots[lot_index]
    if confirm:
        reservation = _mock_parking_reservation(booking, shop or {}, selected_lot)
        if line_user_id:
            await _push_line_parking_reservation(line_user_id, reservation)
        return HTMLResponse(
            _line_parking_reservation_success_page(
                shop_id,
                name,
                booking,
                selected_lot,
                reservation,
                line_token,
            )
        )

    return HTMLResponse(
        _line_parking_reservation_confirm_page(
            shop_id,
            name,
            booking,
            parking_lots,
            lot_index,
            line_token,
        )
    )


@app.get("/line/book/{shop_id}/cancel", response_class=HTMLResponse)
async def line_booking_cancel(shop_id: int, bookingCode: str, lt: str = "", lineUserId: str = ""):
    line_user_id, line_token = _line_context(lt, lineUserId)
    shop = await _fetch_java_shop(shop_id)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shop_id}"))
    result = await _cancel_line_booking(bookingCode, line_user_id, line_token)
    if not result.get("success"):
        message = str(result.get("errorMsg") or "取消訂位失敗，請稍後再試。")
        return HTMLResponse(
            _line_html_page(
                "取消未完成",
                message,
                [
                    ("查看訂位狀態", _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(bookingCode)}&lt={quote_plus(line_token)}")),
                    ("返回店家資訊", _line_public_uri(f"/line/shop/{shop_id}")),
                ],
            ),
            status_code=409,
        )
    booking = result.get("data") if isinstance(result.get("data"), dict) else {}
    return HTMLResponse(_line_booking_result_page(shop_id, name, booking, line_user_id, line_token))


def _line_booking_result_page(
    shop_id: int,
    escaped_shop_name: str,
    booking: dict,
    line_user_id: str = "",
    line_token: str = "",
    payment: dict | None = None,
) -> str:
    booking_code_raw = str(booking.get("bookingCode") or "")
    booking_code = _html_escape(booking_code_raw)
    status = str(booking.get("status") or "CONFIRMED")
    status_label = _line_booking_status_label(status)
    people = _html_escape(str(booking.get("people") or ""))
    booking_date = _html_escape(str(booking.get("date") or ""))
    booking_time = _html_escape(str(booking.get("time") or ""))
    needs_deposit = bool(booking.get("needsDeposit"))
    deposit_total = booking.get("depositTotal") or 0
    hold_expires_at = _html_escape(str(booking.get("holdExpiresAt") or ""))
    payment_trans_id = _html_escape(str(booking.get("paymentTransId") or (payment or {}).get("rec_trade_id") or ""))
    detail_uri = _line_public_uri(f"/line/shop/{shop_id}")
    status_uri = _line_public_uri(
        f"/line/book/{shop_id}/status?bookingCode={quote_plus(booking_code_raw)}&lt={quote_plus(line_token)}"
    )
    pay_uri = _line_public_uri(
        f"/line/book/{shop_id}/pay?bookingCode={quote_plus(booking_code_raw)}&lt={quote_plus(line_token)}"
    )
    cancel_uri = _line_public_uri(
        f"/line/book/{shop_id}/cancel?bookingCode={quote_plus(booking_code_raw)}&lt={quote_plus(line_token)}"
    )
    parking_uri = _line_public_uri(
        f"/line/book/{shop_id}/parking?bookingCode={quote_plus(booking_code_raw)}&driving=true&lt={quote_plus(line_token)}"
    )
    my_bookings_uri = _line_public_uri(f"/line/my-bookings?lt={quote_plus(line_token)}")
    proposal_section = _line_incident_proposal_html(booking, shop_id, booking_code_raw, line_token)
    title = "訂位保留成功" if status == "PENDING_PAYMENT" else "訂位完成"
    if status == "CANCELED":
        title = "訂位已取消"
    elif status == "EXPIRED":
        title = "訂位已逾期"
    deposit_note = _line_booking_deposit_note(status, needs_deposit, deposit_total, hold_expires_at)
    payment_method_label = _html_escape(str((payment or {}).get("methodLabel") or ""))
    payment_method_note = f"<p>付款方式：<strong>{payment_method_label}</strong></p>" if payment_method_label else ""
    payment_note = f"<p>付款交易編號：<strong>{payment_trans_id}</strong></p>" if payment_trans_id else ""
    actions = [
        f'<a class="primary" href="{pay_uri}">立即繳訂金</a>'
        if status == "PENDING_PAYMENT" and needs_deposit else "",
        f'<a class="secondary" href="{status_uri}">查看訂位狀態</a>',
        f'<a class="secondary" href="{cancel_uri}">取消訂位</a>'
        if status in {"PENDING_PAYMENT", "PAID", "CONFIRMED"} else "",
        f'<a class="secondary" href="{parking_uri}">我會開車，提醒停車</a>'
        if status in {"PENDING_PAYMENT", "PAID", "CONFIRMED"} else "",
        f'<a class="secondary" href="{my_bookings_uri}">我的訂位</a>',
        f'<a class="secondary" href="{detail_uri}">查看店家資訊</a>',
    ]
    body = f"""
      <main>
        <p class="eyebrow">ByteBites 訂位狀態</p>
        <h1>{escaped_shop_name}</h1>
        <section>
          <h2>{title}</h2>
          <p>訂位編號：<strong>{booking_code}</strong></p>
          <p>{booking_date} {booking_time} · {people} 人</p>
          <p>狀態：<strong>{status_label}</strong></p>
          {deposit_note}
          {payment_method_note}
          {payment_note}
        </section>
        {proposal_section}
        <div class="actions">
          {''.join(action for action in actions if action)}
        </div>
      </main>
    """
    return _line_shell(f"{escaped_shop_name} {status_label}", body)


def _line_incident_proposal_html(booking: dict, shop_id: int, booking_code_raw: str, line_token: str) -> str:
    incident = booking.get("latestIncident") if isinstance(booking.get("latestIncident"), dict) else {}
    proposal = incident.get("proposedChange") if isinstance(incident.get("proposedChange"), dict) else {}
    if str(proposal.get("status") or "") != "PENDING":
        return ""
    incident_id = str(incident.get("id") or "").strip()
    if not incident_id:
        return ""
    proposal_date = _html_escape(str(proposal.get("date") or ""))
    proposal_time = _html_escape(str(proposal.get("time") or ""))
    proposal_people = _html_escape(str(proposal.get("people") or booking.get("people") or ""))
    proposal_message = _html_escape(str(proposal.get("message") or "店家提出替代時段，請確認是否接受。"))
    expires_at = _html_escape(str(proposal.get("expiresAt") or ""))
    accept_uri = _line_public_uri(
        f"/line/book/{shop_id}/incident-proposal/accept?bookingCode={quote_plus(booking_code_raw)}&incidentId={quote_plus(incident_id)}&lt={quote_plus(line_token)}"
    )
    decline_uri = _line_public_uri(
        f"/line/book/{shop_id}/incident-proposal/decline?bookingCode={quote_plus(booking_code_raw)}&incidentId={quote_plus(incident_id)}&lt={quote_plus(line_token)}"
    )
    expires_html = f"<p>有效至：<strong>{expires_at}</strong></p>" if expires_at else ""
    return f"""
        <section>
          <h2>店家提出替代時段</h2>
          <p>{proposal_date} {proposal_time} · {proposal_people} 人</p>
          <p>{proposal_message}</p>
          {expires_html}
          <div class="actions">
            <a class="primary" href="{accept_uri}">接受改到此時段</a>
            <a class="secondary" href="{decline_uri}">拒絕此提案</a>
          </div>
        </section>
    """


def _line_incident_proposal_response_page(
    title: str,
    escaped_shop_name: str,
    booking: dict,
    shop_id: int,
    booking_code_raw: str,
    line_token: str,
    accepted: bool,
) -> str:
    booking_date = _html_escape(str(booking.get("date") or ""))
    booking_time = _html_escape(str(booking.get("time") or ""))
    people = _html_escape(str(booking.get("people") or ""))
    status_uri = _line_public_uri(
        f"/line/book/{shop_id}/status?bookingCode={quote_plus(booking_code_raw)}&lt={quote_plus(line_token)}"
    )
    my_bookings_uri = _line_public_uri(f"/line/my-bookings?lt={quote_plus(line_token)}")
    note = (
        "Java 已完成改單，原時段會依既有改單 contract 釋放。"
        if accepted
        else "已回覆店家不接受此替代時段，事件保持開啟，店家可重新提出可行方案。"
    )
    timing = f"<p>{booking_date} {booking_time} · {people} 人</p>" if booking_date or booking_time or people else ""
    body = f"""
      <main>
        <p class="eyebrow">ByteBites Rescue</p>
        <h1>{title}</h1>
        <section>
          <h2>{escaped_shop_name}</h2>
          <p>訂位編號：<strong>{_html_escape(booking_code_raw)}</strong></p>
          {timing}
          <p>{_html_escape(note)}</p>
        </section>
        <div class="actions">
          <a class="primary" href="{status_uri}">查看訂位狀態</a>
          <a class="secondary" href="{my_bookings_uri}">我的訂位</a>
        </div>
      </main>
    """
    return _line_shell(title, body)


def _line_parking_preference_page(
    shop_id: int,
    escaped_shop_name: str,
    booking: dict,
    parking_lots: list[dict],
    line_token: str,
    driving: bool,
) -> str:
    booking_code_raw = str(booking.get("bookingCode") or "")
    booking_code = _html_escape(booking_code_raw)
    booking_date = _html_escape(str(booking.get("date") or ""))
    booking_time = _html_escape(str(booking.get("time") or ""))
    status_uri = _line_public_uri(
        f"/line/book/{shop_id}/status?bookingCode={quote_plus(booking_code_raw)}&lt={quote_plus(line_token)}"
    )
    title = "已開啟停車提醒" if driving else "已關閉停車提醒"
    note = (
        "訂位當天接近用餐前，ByteBites 會推播附近停車場剩餘車位與導航。"
        if driving
        else "這筆訂位不會再收到停車提醒。"
    )
    body = f"""
      <main>
        <p class="eyebrow">ByteBites 停車提醒</p>
        <h1>{title}</h1>
        <section>
          <h2>{escaped_shop_name}</h2>
          <p>訂位編號：<strong>{booking_code}</strong></p>
          <p>{booking_date} {booking_time}</p>
          <p>{_html_escape(note)}</p>
          <p>車位資訊來自台北市停車場即時剩餘車位資料，實際空位仍可能快速變動。</p>
        </section>
        {_line_parking_html(parking_lots, shop_id=shop_id, booking_code=booking_code_raw, line_token=line_token, reserve=True)}
        <div class="actions">
          <a class="secondary" href="{status_uri}">查看訂位狀態</a>
        </div>
      </main>
    """
    return _line_shell(title, body)


def _line_parking_reservation_confirm_page(
    shop_id: int,
    escaped_shop_name: str,
    booking: dict,
    parking_lots: list[dict],
    lot_index: int,
    line_token: str,
) -> str:
    booking_code_raw = str(booking.get("bookingCode") or "")
    selected_lot = parking_lots[lot_index]
    confirm_uri = _line_public_uri(
        f"/line/book/{shop_id}/parking-reserve?bookingCode={quote_plus(booking_code_raw)}&lot={lot_index}&confirm=true&lt={quote_plus(line_token)}"
    )
    status_uri = _line_public_uri(
        f"/line/book/{shop_id}/status?bookingCode={quote_plus(booking_code_raw)}&lt={quote_plus(line_token)}"
    )
    body = f"""
      <main>
        <p class="eyebrow">ByteBites Parking Hold</p>
        <h1>保留附近車位</h1>
        <section>
          <h2>{escaped_shop_name}</h2>
          <p>我會先幫你保留一個展示車位，抵達前可用這張卡快速確認停車場、樓層、區域與車格。</p>
          <p>此功能目前為 ByteBites 展示保留流程，未向停車場業者送出正式交易。</p>
        </section>
        {_line_parking_html([selected_lot], shop_id=shop_id, booking_code=booking_code_raw, line_token=line_token, reserve=False)}
        <div class="actions">
          <a class="primary" href="{confirm_uri}">確認保留車位</a>
          <a class="secondary" href="{status_uri}">先查看訂位</a>
        </div>
      </main>
    """
    return _line_shell("確認保留車位", body)


def _line_parking_reservation_success_page(
    shop_id: int,
    escaped_shop_name: str,
    booking: dict,
    lot: dict,
    reservation: dict,
    line_token: str,
) -> str:
    booking_code_raw = str(booking.get("bookingCode") or "")
    status_uri = _line_public_uri(
        f"/line/book/{shop_id}/status?bookingCode={quote_plus(booking_code_raw)}&lt={quote_plus(line_token)}"
    )
    navigation_url = _html_escape(str(lot.get("navigationUrl") or ""))
    navigation_html = f'<a class="secondary" href="{navigation_url}">導航到停車場</a>' if navigation_url else ""
    lot_name = _html_escape(str(reservation.get("lotName") or "停車場"))
    floor = _html_escape(str(reservation.get("floor") or ""))
    zone = _html_escape(str(reservation.get("zone") or ""))
    stall = _html_escape(str(reservation.get("stall") or ""))
    hold_until = _html_escape(str(reservation.get("holdUntil") or ""))
    body = f"""
      <main>
        <p class="eyebrow">ByteBites Parking Hold</p>
        <h1>已保留車位</h1>
        <section>
          <h2>{lot_name}</h2>
          <p>餐廳：<strong>{escaped_shop_name}</strong></p>
          <p>車格：<strong>{floor} · {zone} · {stall}</strong></p>
          <p>保留至：<strong>{hold_until}</strong></p>
          <p>抵達後請依現場停車場指示入場；此為 ByteBites 展示保留，不會向停車場業者收費。</p>
        </section>
        {_line_parking_html([_parking_lot_after_reservation(lot, reservation)], reserve=False)}
        <div class="actions">
          {navigation_html}
          <a class="secondary" href="{status_uri}">查看訂位狀態</a>
        </div>
      </main>
    """
    return _line_shell("已保留車位", body)


@app.get("/line/my-bookings", response_class=HTMLResponse)
async def line_my_bookings(lt: str = "", lineUserId: str = ""):
    line_user_id, line_token = _line_context(lt, lineUserId)
    bookings = await _fetch_line_bookings(line_user_id, line_token)
    if not bookings:
        return HTMLResponse(
            _line_html_page(
                "我的訂位",
                "目前沒有你的訂位資料。從 LINE 推薦卡點「填日期人數」完成訂位後，會出現在這裡。",
                [],
            )
        )
    cards = []
    for booking in bookings[:10]:
        shop_id = int(booking.get("shopId") or 0)
        code = str(booking.get("bookingCode") or "")
        status = str(booking.get("status") or "")
        pay_link = (
            f'<a class="primary" href="{_line_public_uri(f"/line/book/{shop_id}/pay?bookingCode={quote_plus(code)}&lt={quote_plus(line_token)}")}">繳訂金</a>'
            if status == "PENDING_PAYMENT" and booking.get("needsDeposit")
            else ""
        )
        proposal_actions = _line_incident_proposal_html(booking, shop_id, code, line_token)
        cards.append(
            f"""
            <section>
              <h2>{_html_escape(str(booking.get("shopName") or f"店家 {shop_id}"))}</h2>
              <p>訂位編號：<strong>{_html_escape(code)}</strong></p>
              <p>{_html_escape(str(booking.get("date") or ""))} {_html_escape(str(booking.get("time") or ""))} · {_html_escape(str(booking.get("people") or ""))} 人</p>
              <p>狀態：<strong>{_html_escape(_line_booking_status_label(status))}</strong></p>
              <p>{_html_escape(_line_booking_deposit_text(booking))}</p>
              <div class="actions">
                {pay_link}
                <a class="secondary" href="{_line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(code)}&lt={quote_plus(line_token)}")}">查看狀態</a>
              </div>
            </section>
            {proposal_actions}
            """
        )
    body = f"""
      <main>
        <p class="eyebrow">ByteBites</p>
        <h1>我的訂位</h1>
        {''.join(cards)}
      </main>
    """
    return HTMLResponse(_line_shell("我的訂位", body))


@app.get("/line/availability/watch", response_class=HTMLResponse)
async def line_create_availability_watch(
    shopId: int,
    date: str,
    time: str,
    people: int = 2,
    tableType: str = "normal",
    lt: str = "",
    lineUserId: str = "",
):
    line_user_id, line_token = _line_context(lt, lineUserId)
    shop = await _fetch_java_shop(shopId)
    name = _html_escape(str((shop or {}).get("name") or f"店家 {shopId}"))
    error = _validate_line_booking(people, date, time, tableType)
    if error:
        return HTMLResponse(
            _line_html_page(
                "空位通知資料需要修正",
                error,
                [("返回訂位", _line_public_uri(f"/line/book/{shopId}?lt={quote_plus(line_token)}"))],
            ),
            status_code=400,
        )
    result = await _create_line_availability_watch(shopId, people, date, time, tableType, line_user_id, line_token)
    if not result.get("success"):
        message = str(result.get("errorMsg") or "空位通知建立失敗，請稍後再試。")
        return HTMLResponse(
            _line_html_page(
                "空位通知未建立",
                message,
                [
                    ("重新訂位", _line_public_uri(f"/line/book/{shopId}?lt={quote_plus(line_token)}&people={people}&date={quote_plus(date)}&time={quote_plus(time)}&tableType={quote_plus(tableType)}")),
                    ("查看店家資訊", _line_public_uri(f"/line/shop/{shopId}")),
                ],
            ),
            status_code=409,
        )
    watch = result.get("data") if isinstance(result.get("data"), dict) else {}
    await _push_line_availability_watch_created(line_user_id, watch)
    body = f"""
      <main>
        <p class="eyebrow">ByteBites 空位通知</p>
        <h1>{name}</h1>
        <section>
          <h2>已設定空位通知</h2>
          <p>{_html_escape(date)} {_html_escape(time)} · {people} 人</p>
          <p>若此時段釋出足夠座位，ByteBites 會在 LINE 主動提醒你回來訂位。</p>
        </section>
        <div class="actions">
          <a class="primary" href="{_line_public_uri('/line/notifications')}">查看通知</a>
          <a class="secondary" href="{_line_public_uri(f'/line/shop/{shopId}')}">查看店家資訊</a>
        </div>
      </main>
    """
    return HTMLResponse(_line_shell(f"{name} 空位通知", body))


@app.get("/line/notifications", response_class=HTMLResponse)
async def line_notifications():
    payload = await _fetch_line_notifications()
    items = payload.get("items") if isinstance(payload, dict) else []
    if not items:
        return HTMLResponse(
            _line_html_page(
                "空位通知",
                "目前沒有空位釋出通知。當你設定的額滿時段釋出座位，通知會出現在這裡，也會推送到 LINE。",
                [],
            )
        )
    cards = []
    for item in items[:20]:
        shop_id = int(item.get("shopId") or 0)
        line_user_id = str(item.get("lineUserId") or "")
        line_token = _line_token_for_user(line_user_id) if line_user_id else ""
        cards.append(
            f"""
            <section>
              <h2>{_html_escape(str(item.get("title") or "空位通知"))}</h2>
              <p>{_html_escape(str(item.get("body") or ""))}</p>
              <p>狀態：<strong>{_html_escape(str(item.get("status") or ""))}</strong></p>
              <div class="actions">
                <a class="primary" href="{_line_public_uri(f"/line/book/{shop_id}?people={quote_plus(str(item.get('people') or 2))}&date={quote_plus(str(item.get('date') or ''))}&time={quote_plus(str(item.get('time') or '19:00'))}&tableType={quote_plus(str(item.get('tableType') or 'normal'))}&lt={quote_plus(line_token)}")}">立即訂位</a>
              </div>
            </section>
            """
        )
    body = f"""
      <main>
        <p class="eyebrow">ByteBites</p>
        <h1>空位通知</h1>
        {''.join(cards)}
      </main>
    """
    return HTMLResponse(_line_shell("空位通知", body))


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
        shown_shops=[
            *[
                shop
                for shop in state.get("shown_shops", [])
                if isinstance(shop, dict)
            ],
            *remaining,
        ],
    )
    search_result = await _build_agent_search_result(previous_query, remaining, selected_ids)
    remaining = search_result.get("shops", remaining)
    flex_or_bundle = build_line_flex_message(
        shops=remaining,
        recommended_shop_ids=selected_ids,
        answer="",
        public_web_url=settings.line_public_web_url,
        line_user_id=user_id,
    )
    messages = flex_or_bundle.get("messages") if flex_or_bundle.get("type") == "_bundle" else [flex_or_bundle]
    return messages or [build_text_message("我找到更多候選，但 LINE 卡片暫時無法產生，請再試一次。")]


async def _build_line_cards_for_query(
    query: str,
    user_id: str,
    selected_ids: list[int] | None = None,
    save_query: str | None = None,
) -> list[dict] | None:
    try:
        shops = await _semantic_hits(query, top_k=30)
    except Exception:
        logger.exception("line_card_search_failed user_id=%s query=%s", user_id, query)
        return None
    if not shops:
        return None

    deduped = _dedupe_shops_by_brand(shops)
    if selected_ids:
        selected = [int(shop_id) for shop_id in selected_ids if str(shop_id).isdigit()]
    else:
        exact_matches = _exact_shop_matches(query, deduped)
        story_ids = _demo_story_recommended_shop_ids(query, shops)
        if exact_matches:
            selection_pool = exact_matches[:1]
            selected = [
                int(sid)
                for shop in selection_pool
                if (sid := _shop_id(shop)) is not None
            ]
        elif story_ids:
            selected = story_ids
        else:
            selected = [
                int(sid)
                for shop in deduped[:3]
                if (sid := _shop_id(shop)) is not None
            ]
    selected = [shop_id for shop_id in selected if any(_shop_id(shop) == shop_id for shop in shops)]
    if not selected:
        return None

    search_result = await _build_agent_search_result(query, shops, selected)
    shops = search_result.get("shops", shops)
    selected_shops = _shops_for_ids(shops, selected)
    _save_line_recommendation_state(user_id, query=save_query or query, shown_shop_ids=selected, shown_shops=selected_shops)
    flex_or_bundle = build_line_flex_message(
        shops=shops,
        recommended_shop_ids=selected,
        answer="",
        public_web_url=settings.line_public_web_url,
        line_user_id=user_id,
    )
    messages = flex_or_bundle.get("messages") if flex_or_bundle.get("type") == "_bundle" else [flex_or_bundle]
    intro = _line_scope_expansion_intro_from_note(search_result.get("scope_note"))
    if not intro:
        intro = _line_scope_expansion_intro(query, selected_shops)
    if intro and messages and messages[0].get("type") == "text":
        messages[0]["text"] = intro
    return messages or None


def _shops_for_ids(shops: list[dict], selected_ids: list[int]) -> list[dict]:
    by_id = {
        int(shop_id): shop
        for shop in shops
        if (shop_id := _shop_id(shop)) is not None
    }
    return [by_id[shop_id] for shop_id in selected_ids if shop_id in by_id]


async def _build_agent_search_result(
    query: str,
    shops: list[dict],
    recommended_shop_ids: list[int] | None = None,
) -> dict:
    result = {"query": query, "shops": shops}
    return await _enrich_agent_search_result(query, result, recommended_shop_ids)


async def _enrich_agent_search_result(
    query: str,
    tool_result: dict,
    recommended_shop_ids: list[int] | None = None,
) -> dict:
    if not isinstance(tool_result, dict):
        return tool_result
    shops = tool_result.get("shops")
    if not isinstance(shops, list) or not shops:
        return tool_result

    selected_ids = [
        int(shop_id)
        for shop_id in (recommended_shop_ids or [])
        if str(shop_id).isdigit()
    ]
    if not selected_ids:
        selected_ids = [
            int(sid)
            for shop in shops[:3]
            if (sid := _shop_id(shop)) is not None
        ]

    private_memory = await _fetch_private_dining_memory()
    if private_memory:
        tool_result["private_memory"] = private_memory
        selected_ids = _adjust_selected_ids_for_private_memory(shops, selected_ids, private_memory)

    private_offers_by_shop = await _fetch_private_ai_offers(selected_ids, query)
    if private_offers_by_shop:
        tool_result["private_ai_offers"] = [
            offer
            for offers in private_offers_by_shop.values()
            for offer in offers
            if isinstance(offer, dict)
        ]

    tool_result["query"] = query
    tool_result["shops"] = _annotate_private_ai_offers(
        _annotate_private_memory(
            await _hydrate_agent_search_shops(shops, selected_ids),
            private_memory,
        ),
        private_offers_by_shop,
    )
    for shop in tool_result["shops"]:
        if isinstance(shop, dict):
            price_label = _agent_price_label(shop)
            if price_label:
                shop["price_per_person"] = price_label
            elif str(shop.get("price_per_person") or "").strip():
                shop.pop("price_per_person", None)
            reason = _agent_shop_match_reason(query, shop)
            if reason:
                shop["match_reason"] = reason
    selected_shops = _shops_for_ids(tool_result["shops"], selected_ids)
    scope_note = _search_scope_note(query, selected_shops)
    if scope_note:
        tool_result["scope_note"] = scope_note
    else:
        tool_result.pop("scope_note", None)
    return tool_result


async def _hydrate_agent_search_shops(shops: list[dict], selected_ids: list[int]) -> list[dict]:
    selected_set = {
        int(shop_id)
        for shop_id in selected_ids
        if str(shop_id).isdigit()
    }
    if not selected_set:
        return shops

    hydrated: list[dict] = []
    for shop in shops:
        shop_id = _shop_id(shop)
        if shop_id not in selected_set:
            hydrated.append(shop)
            continue
        if _line_card_has_rich_context(shop) and _agent_price_label(shop):
            hydrated.append(shop)
            continue

        metadata = await _fetch_java_ai_metadata(shop_id)
        if not metadata:
            hydrated.append(shop)
            continue

        merged = dict(shop)
        merged["ai_summary"] = merged.get("ai_summary") or metadata.get("aiSummary") or metadata.get("highlightReview")
        merged["signature_dishes"] = merged.get("signature_dishes") or _parse_json_list(metadata.get("signatureDishes"))
        merged["atmosphere_tags"] = merged.get("atmosphere_tags") or _parse_json_list(metadata.get("atmosphereTags"))
        merged["booking_difficulty"] = merged.get("booking_difficulty") or metadata.get("bookingDifficulty")
        merged["price_per_person"] = merged.get("price_per_person") or metadata.get("pricePerPerson")
        hydrated.append(merged)
    return hydrated


def _line_card_has_rich_context(shop: dict) -> bool:
    return _shop_has_rich_context(shop)


def _shop_has_rich_context(shop: dict) -> bool:
    return bool(
        str(shop.get("ai_summary") or "").strip()
        or _parse_json_list(shop.get("signature_dishes"))
        or _parse_json_list(shop.get("atmosphere_tags"))
    )


def _search_scope_note(query: str, selected_shops: list[dict]) -> str | None:
    if not selected_shops:
        return None
    constraints = _extract_query_constraints(query)
    requested_stations = constraints.get("stations") or []
    if requested_stations:
        station_matches = sum(1 for shop in selected_shops if _station_proximity_score(constraints, shop) > 0)
        if station_matches < len(selected_shops):
            station_label = "、".join(f"{station}站" for station in requested_stations)
            category_label = _category_label_for_constraints(constraints)
            return (
                f"{station_label}附近符合條件較少，我保留最接近的選項，並擴大到台北{category_label}，"
                f"整理 {len(selected_shops)} 間符合需求的餐廳。"
            )
    requested_districts = constraints.get("districts") or []
    if not requested_districts:
        return None
    district_matches = sum(1 for shop in selected_shops if _district_matches(constraints, shop))
    if district_matches >= len(selected_shops):
        return None

    district_label = "、".join(f"{district}區" for district in requested_districts)
    category_label = _category_label_for_constraints(constraints)
    return (
        f"{district_label}符合條件較少，我先擴大到台北{category_label}，整理 {len(selected_shops)} 間符合需求的餐廳。"
    )


def _line_scope_expansion_intro(query: str, selected_shops: list[dict]) -> str | None:
    note = _search_scope_note(query, selected_shops)
    return _line_scope_expansion_intro_from_note(note)


def _line_scope_expansion_intro_from_note(note: str | None) -> str | None:
    if not note:
        return None
    return (
        f"{note}"
        "請左右滑動查看卡片，點「看完整分析」看菜色、評論與訂位規則；點「填日期人數」直接進訂位表單。"
    )


def _category_label_for_constraints(constraints: dict) -> str:
    categories = constraints.get("categories") or []
    if constraints.get("wants_steak"):
        return "牛排餐廳"
    if constraints.get("wants_burger"):
        return "漢堡店"
    if "hotpot" in categories:
        return "火鍋"
    if "yakiniku" in categories:
        return "燒肉"
    if "euro" in categories:
        return "義式餐廳"
    if "japanese" in categories:
        return "日式餐廳"
    if "izakaya" in categories:
        return "居酒屋"
    if "omakase" in categories:
        return "無菜單料理"
    if "chinese" in categories:
        return "中式餐廳"
    if "american" in categories:
        return "美式餐廳"
    if "korean" in categories:
        return "韓式餐廳"
    if "vegetarian" in categories:
        return "蔬食餐廳"
    if "cafe" in categories:
        return "咖啡甜點"
    if "international" in categories:
        return "異國料理餐廳"
    return "餐廳"


async def _build_line_card_request(user_text: str, user_id: str) -> list[dict] | None:
    if not _line_card_request_intent(user_text):
        return None
    state = _load_line_recommendation_state(user_id)
    previous_query = str(state.get("query") or "").strip()
    if not previous_query:
        return [build_text_message("可以，請先告訴我地點和類型，例如「信義區高級火鍋」，我會直接回圖卡。")]
    selected_ids = [
        int(shop_id)
        for shop_id in state.get("shown_shop_ids", [])
        if str(shop_id).isdigit()
    ]
    messages = await _build_line_cards_for_query(
        previous_query,
        user_id,
        selected_ids=selected_ids or None,
        save_query=previous_query,
    )
    return messages or [build_text_message("我暫時無法重送剛剛的圖卡，請再輸入一次地點和類型。")]


async def _build_line_recommendation_advice(user_text: str, user_id: str) -> list[dict] | None:
    if not _recommendation_advice_intent(user_text):
        return None
    if _complete_fresh_restaurant_query(user_text) and not _recommendation_followup_reference(user_text):
        return None
    state = _load_line_recommendation_state(user_id)
    previous_query = str(state.get("query") or "").strip()
    shown_ids = [
        int(shop_id)
        for shop_id in state.get("shown_shop_ids", [])
        if str(shop_id).isdigit()
    ]
    if not previous_query or not shown_ids:
        return None
    try:
        shops = await _semantic_hits(previous_query, top_k=30)
    except Exception:
        logger.exception("line_recommendation_advice_search_failed user_id=%s query=%s", user_id, previous_query)
        return [build_text_message("我暫時無法讀取剛剛的推薦依據，請稍後再試一次。")]
    selected_shops = _shops_for_ids(shops, shown_ids)
    if not selected_shops:
        return None
    answer = _recommendation_advice_answer(user_text, selected_shops, previous_query)
    return [build_text_message(answer)] if answer else None


async def _build_line_named_selection_cards(user_text: str, user_id: str) -> list[dict] | None:
    normalized = _line_selection_token(user_text)
    if not normalized:
        return None
    state = _load_line_recommendation_state(user_id)
    previous_query = str(state.get("query") or "").strip()
    shown_ids = [
        int(shop_id)
        for shop_id in state.get("shown_shop_ids", [])
        if str(shop_id).isdigit()
    ]
    if not previous_query:
        return await _build_line_cards_for_query(normalized, user_id, selected_ids=None, save_query=normalized)
    ordinal_index = _selection_index_from_text(user_text)
    if ordinal_index is not None and 0 <= ordinal_index < len(shown_ids):
        return await _build_line_cards_for_query(
            previous_query,
            user_id,
            selected_ids=[shown_ids[ordinal_index]],
            save_query=previous_query,
        )
    try:
        shops = await _semantic_hits(previous_query, top_k=30)
    except Exception:
        logger.exception("line_named_selection_search_failed user_id=%s query=%s", user_id, previous_query)
        return None
    matches = [
        shop
        for shop in shops
        if _line_shop_matches_selection(shop, normalized)
    ]
    if not matches:
        return await _build_line_cards_for_query(normalized, user_id, selected_ids=None, save_query=normalized)
    selected_ids = [
        int(sid)
        for shop in _dedupe_shops_by_brand(matches)[:3]
        if (sid := _shop_id(shop)) is not None
    ]
    if not selected_ids:
        return None
    _save_line_recommendation_state(
        user_id,
        query=previous_query,
        shown_shop_ids=[*state.get("shown_shop_ids", []), *selected_ids],
    )
    search_result = await _build_agent_search_result(previous_query, shops, selected_ids)
    shops = search_result.get("shops", shops)
    flex_or_bundle = build_line_flex_message(
        shops=shops,
        recommended_shop_ids=selected_ids,
        answer="",
        public_web_url=settings.line_public_web_url,
        line_user_id=user_id,
    )
    messages = flex_or_bundle.get("messages") if flex_or_bundle.get("type") == "_bundle" else [flex_or_bundle]
    return messages or None


def _line_card_request_intent(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    return bool(normalized) and any(
        phrase in normalized
        for phrase in ("圖卡", "卡片", "給我卡", "給我圖", "用卡片", "出卡", "flex")
    )


def _line_selection_token(text: str) -> str:
    if _line_booking_followup_intent(text):
        return ""
    normalized = re.sub(r"\s+", "", str(text or "").strip().lower())
    normalized = normalized.strip("，,。.!！?？")
    if _booking_intent(normalized) or _payment_intent(normalized):
        return ""
    specific = _specific_shop_keyword(text)
    if specific:
        return specific
    if _restaurant_need_clarification(text):
        return ""
    if not normalized or len(normalized) > 12:
        return ""
    if _line_card_request_intent(normalized) or _line_more_recommendation_intent(normalized):
        return ""
    if _line_should_force_recommendation_cards(normalized):
        return ""
    return normalized


def _line_shop_matches_selection(shop: dict, token: str) -> bool:
    name = re.sub(r"\s+", "", str(shop.get("name") or "").lower())
    brand = re.sub(r"\s+", "", _shop_brand_key(shop).lower())
    return bool(token) and (
        token in name
        or token in brand
        or name.startswith(token)
        or brand.startswith(token)
    )


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
            "不喜歡",
            "不要第",
            "換掉",
        )
    ) or bool(re.search(r"(不要|不喜歡|換掉).{0,6}第?[一二兩三四五六七八九十\d]{1,3}(間|家|個)", normalized))


def _line_should_force_recommendation_cards(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    if _booking_intent(normalized) or _payment_intent(normalized):
        return False
    if _restaurant_need_clarification(normalized):
        return False
    constraints = _extract_query_constraints(normalized)
    has_food_or_place = bool(
        constraints["categories"]
        or constraints["districts"]
        or constraints["stations"]
        or constraints["wants_luxury"]
        or constraints["wants_hot_seat"]
    )
    has_request_phrase = any(
        phrase in normalized
        for phrase in ("推薦", "找", "想吃", "想找", "哪間", "哪家", "餐廳")
    )
    has_specific_dining_need = bool(
        constraints["categories"]
        and (
            constraints["districts"]
            or constraints["stations"]
            or constraints["wants_luxury"]
            or constraints["wants_nearby"]
            or constraints["wants_hot_seat"]
        )
    )
    asks_definition = any(phrase in normalized for phrase in ("是什麼", "怎麼", "如何", "差別", "意思"))
    has_clear_category_only = bool(constraints["categories"] or constraints.get("specific_cuisines") or constraints.get("wants_burger"))
    return has_food_or_place and (has_request_phrase or has_specific_dining_need or (has_clear_category_only and not asks_definition))


def _line_should_reset_agent_context_for_query(text: str) -> bool:
    return bool(
        _line_should_force_recommendation_cards(text)
        and not _line_more_recommendation_intent(text)
        and not _line_card_request_intent(text)
    )


def _reset_line_agent_context_for_fresh_query(user_id: str, text: str) -> bool:
    if not _line_should_reset_agent_context_for_query(text):
        return False
    try:
        session_store.clear_session(f"line:{user_id}")
    except Exception:
        logger.exception("line_agent_session_clear_failed user_id=%s", user_id)
    _clear_line_recommendation_state(user_id)
    return True


async def _build_line_clarification_if_needed(user_text: str, user_id: str) -> list[dict] | None:
    if not _restaurant_need_clarification(user_text):
        return None
    _save_line_recommendation_state(user_id, query=user_text, shown_shop_ids=[])
    return [build_text_message(_restaurant_clarification_text(user_text))]


async def _build_line_fallback_recommendation_cards(user_text: str, user_id: str) -> list[dict] | None:
    if not _line_should_force_recommendation_cards(user_text):
        return None
    return await _build_line_cards_for_query(user_text, user_id)


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
    return line_recommendation_state_key(user_id)


def _load_line_recommendation_state(user_id: str) -> dict:
    return load_json_state(
        _line_recommendation_state_key(user_id),
        "line_recommendation_state_load_failed",
        user_id,
    )


def _clear_line_recommendation_state(user_id: str) -> None:
    clear_state_key(
        _line_recommendation_state_key(user_id),
        "line_recommendation_state_clear_failed",
        user_id,
    )


def _save_line_recommendation_state(
    user_id: str,
    query: str,
    shown_shop_ids: list[int],
    booking_prefill: dict | None = None,
    shown_shops: list[dict] | None = None,
) -> None:
    deduped: list[int] = []
    for shop_id in shown_shop_ids:
        try:
            sid = int(shop_id)
        except (TypeError, ValueError):
            continue
        if sid not in deduped:
            deduped.append(sid)
    payload = {"query": query, "shown_shop_ids": deduped[-60:]}
    if shown_shops:
        compact_shops = _line_recommendation_shop_snapshots(shown_shops, deduped)
        if compact_shops:
            payload["shown_shops"] = compact_shops[-60:]
    compact_prefill = _compact_booking_prefill(booking_prefill)
    if compact_prefill:
        payload["booking_prefill"] = compact_prefill
    save_json_state(
        _line_recommendation_state_key(user_id),
        LINE_RECOMMENDATION_TTL_SECONDS,
        payload,
        "line_recommendation_state_save_failed",
        user_id,
    )


def _line_booking_state_key(user_id: str) -> str:
    return line_booking_state_key(user_id)


def _load_line_booking_state(user_id: str) -> dict:
    return load_json_state(_line_booking_state_key(user_id), "line_booking_state_load_failed", user_id)


def _save_line_booking_state(user_id: str, booking: dict, phase: str = "updated") -> None:
    if not user_id or not isinstance(booking, dict) or not booking.get("bookingCode"):
        return
    save_json_state(
        _line_booking_state_key(user_id),
        LINE_BOOKING_TTL_SECONDS,
        {"phase": phase, "booking": booking},
        "line_booking_state_save_failed",
        user_id,
    )


def _line_booking_draft_state_key(user_id: str) -> str:
    return line_booking_draft_state_key(user_id)


def _load_line_booking_draft_state(user_id: str) -> dict:
    return load_json_state(
        _line_booking_draft_state_key(user_id),
        "line_booking_draft_load_failed",
        user_id,
    )


def _save_line_booking_draft_state(user_id: str, draft: dict) -> None:
    if not user_id or not isinstance(draft, dict) or not draft.get("shop_id"):
        return
    save_json_state(
        _line_booking_draft_state_key(user_id),
        LINE_BOOKING_TTL_SECONDS,
        draft,
        "line_booking_draft_save_failed",
        user_id,
    )


def _clear_line_booking_draft_state(user_id: str) -> None:
    clear_state_key(
        _line_booking_draft_state_key(user_id),
        "line_booking_draft_clear_failed",
        user_id,
    )


def _line_location_state_key(user_id: str) -> str:
    return line_location_state_key(user_id)


def _load_line_location_state(user_id: str) -> dict:
    return load_json_state(_line_location_state_key(user_id), "line_location_state_load_failed", user_id)


def _save_line_location_state(user_id: str, message: dict) -> dict:
    state = {
        "title": str(message.get("title") or "").strip(),
        "address": str(message.get("address") or "").strip(),
        "latitude": message.get("latitude"),
        "longitude": message.get("longitude"),
    }
    save_json_state(
        _line_location_state_key(user_id),
        LINE_LOCATION_TTL_SECONDS,
        state,
        "line_location_state_save_failed",
        user_id,
    )
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
    contextual_adjusted_query = None
    if previous_query and _restaurant_need_clarification(previous_query) and _query_is_clarification_followup(user_text):
        adjusted_query = _line_merge_followup_query(previous_query, user_text)
        if _restaurant_need_clarification(adjusted_query):
            _save_line_recommendation_state(user_id, query=adjusted_query, shown_shop_ids=[])
            return [build_text_message(_restaurant_clarification_text(adjusted_query))]
        contextual_adjusted_query = adjusted_query
    if contextual_adjusted_query is None:
        if not previous_query or not _line_adjustment_intent(user_text):
            return None
        contextual_adjusted_query = _line_merge_followup_query(previous_query, user_text)

    adjusted_query = contextual_adjusted_query
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
        shown_shops=[
            *[
                shop
                for shop in state.get("shown_shops", [])
                if isinstance(shop, dict)
            ],
            *deduped,
        ],
    )
    search_result = await _build_agent_search_result(adjusted_query, shops, selected_ids)
    shops = search_result.get("shops", shops)
    flex_or_bundle = build_line_flex_message(
        shops=shops,
        recommended_shop_ids=selected_ids,
        answer="",
        public_web_url=settings.line_public_web_url,
        line_user_id=user_id,
    )
    messages = flex_or_bundle.get("messages") if flex_or_bundle.get("type") == "_bundle" else [flex_or_bundle]
    return messages or [build_text_message("我已依新條件重新整理，但 LINE 卡片暫時無法產生，請再試一次。")]


async def _build_line_agent_recommendation_messages(
    user_text: str,
    user_id: str,
) -> list[dict]:
    try:
        check_input(user_text)
        _reset_line_agent_context_for_fresh_query(user_id, user_text)
        answer, _tools_used, tool_result = await _run_agent_turn(user_text, f"line:{user_id}")
    except GuardrailViolation:
        return [build_text_message("這個內容我不能協助處理。可以換一個餐廳或訂位相關的問法。")]
    except Exception:
        logger.exception("line_agent_failed user_id=%s text=%s", user_id, user_text)
        return [build_text_message("AI 目前暫時無法完成推薦，請稍後再試一次，或換個地點 / 條件重新輸入。")]

    shops = tool_result.get("shops") if isinstance(tool_result, dict) else None
    if isinstance(shops, list) and shops:
        recommended_ids = tool_result.get("agent_decision", {}).get("recommended_shop_ids")
        shown_ids = (
            [int(shop_id) for shop_id in recommended_ids if str(shop_id).isdigit()]
            if isinstance(recommended_ids, list)
            else [
                int(sid)
                for shop in shops[:3]
                if (sid := _shop_id(shop)) is not None
            ]
        )
        search_result = await _build_agent_search_result(user_text, shops, shown_ids)
        shops = search_result.get("shops", shops)
        flex_or_bundle = build_line_flex_message(
            shops=shops,
            recommended_shop_ids=recommended_ids if isinstance(recommended_ids, list) else None,
            answer=answer,
            public_web_url=settings.line_public_web_url,
            line_user_id=user_id,
        )
        if flex_or_bundle.get("type") == "_bundle":
            messages = flex_or_bundle.get("messages") or []
        else:
            messages = [flex_or_bundle]
        _save_line_recommendation_state(user_id, query=user_text, shown_shop_ids=shown_ids, shown_shops=shops)
        if messages:
            selected_shops = _shops_for_ids(shops, shown_ids)
            intro = _line_scope_expansion_intro_from_note(search_result.get("scope_note"))
            if not intro:
                intro = _line_scope_expansion_intro(user_text, selected_shops)
            if intro and messages[0].get("type") == "text":
                messages[0]["text"] = intro
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


def _zh_number_to_int(value: str) -> int | None:
    return zh_number_to_int(value)


def _line_booking_prefill_from_text(text: str) -> dict:
    return line_booking_prefill_from_text(text, today=taipei_today())


def _line_booking_followup_intent(text: str) -> bool:
    prefill = _line_booking_prefill_from_text(text)
    return bool(prefill.get("date") or prefill.get("time") or prefill.get("people") or _booking_selection_intent(text))


async def _build_line_booking_draft_confirmation(user_text: str, user_id: str) -> list[dict] | None:
    if not _booking_confirm_intent(user_text):
        return None
    draft = _load_line_booking_draft_state(user_id)
    if not draft:
        return None
    missing = _booking_draft_missing(draft)
    if missing:
        return [
            build_text_message(
                f"這筆訂位草稿還缺{'、'.join(missing)}。請直接補齊，例如「明天晚上7點 4人」。"
            )
        ]
    line_token = _line_token_for_user(user_id)
    result = await _reserve_line_booking(
        int(draft.get("shop_id")),
        int(draft.get("people")),
        str(draft.get("date")),
        str(draft.get("time")),
        str(draft.get("table_type") or "normal"),
        user_id,
        line_token,
    )
    if not result.get("success"):
        return [build_text_message(str(result.get("errorMsg") or "訂位暫時無法完成，請稍後再試。"))]
    booking = result.get("data") if isinstance(result.get("data"), dict) else {}
    _clear_line_booking_draft_state(user_id)
    _save_line_booking_state(user_id, booking, "created")
    return [_line_booking_flex_message(booking, "created", line_user_id=user_id)]


async def _build_line_booking_draft_update(user_text: str, user_id: str) -> list[dict] | None:
    if not _booking_draft_edit_intent(user_text):
        return None
    draft = _load_line_booking_draft_state(user_id)
    if not draft:
        return None
    if _same_day_datetime_request(user_text):
        return [build_text_message(_same_day_booking_policy_answer())]

    state = _load_line_recommendation_state(user_id)
    shown_ids = [
        int(shop_id)
        for shop_id in state.get("shown_shop_ids", [])
        if str(shop_id).isdigit()
    ]
    shown_shops = [
        shop
        for shop in state.get("shown_shops", [])
        if isinstance(shop, dict) and _shop_id(shop) in set(shown_ids)
    ]

    shop_id = int(draft.get("shop_id"))
    shop_name = str(draft.get("shop_name") or f"店家 {shop_id}")
    selected_shop = _recommended_shop_from_text(user_text, shown_shops) if shown_shops else None
    selected_shop_id = _shop_id(selected_shop or {})
    if selected_shop_id is not None:
        shop_id = selected_shop_id
        fetched = await _fetch_java_shop(shop_id)
        shop_name = str((fetched or selected_shop or {}).get("name") or f"店家 {shop_id}")

    prefill = _merge_booking_prefill(_line_booking_prefill_from_text(user_text), draft, override=True)
    updated = _booking_draft_payload(shop_id, shop_name, prefill)
    _save_line_booking_draft_state(user_id, updated)

    missing = _booking_draft_missing(updated)
    if missing:
        return [
            build_text_message(
                f"我已更新訂位草稿，還缺{'、'.join(missing)}。請補齊後我再給你確認卡。"
            )
        ]
    return [
        build_text_message(
            f"已更新成「{updated.get('shop_name')}」{updated.get('date')} {updated.get('time')}、{updated.get('people')} 人。請確認後再送出。"
        ),
        _line_booking_draft_flex_message(updated, line_user_id=user_id),
    ]


async def _build_line_booking_followup(user_text: str, user_id: str) -> list[dict] | None:
    if not _line_booking_followup_intent(user_text):
        return None
    if _same_day_datetime_request(user_text):
        return [build_text_message(_same_day_booking_policy_answer())]
    state = _load_line_recommendation_state(user_id)
    shown_ids = [
        int(shop_id)
        for shop_id in state.get("shown_shop_ids", [])
        if str(shop_id).isdigit()
    ]
    if not shown_ids:
        return None
    shown_shops = [
        shop
        for shop in state.get("shown_shops", [])
        if isinstance(shop, dict) and _shop_id(shop) in set(shown_ids)
    ]
    ordinal_index = _selection_index_from_text(user_text)
    if len(shown_ids) > 1 and ordinal_index is not None and 0 <= ordinal_index < len(shown_ids):
        shown_ids = [shown_ids[ordinal_index]]
    elif len(shown_ids) > 1 and shown_shops:
        selected_shop = _recommended_shop_from_text(user_text, shown_shops)
        selected_shop_id = _shop_id(selected_shop or {})
        if selected_shop_id is not None:
            shown_ids = [selected_shop_id]
    if len(shown_ids) > 1:
        return [build_text_message("我收到日期/時間了。請先回覆要訂哪一間店名，避免幫你訂錯餐廳。")]

    shop_id = shown_ids[0]
    saved_prefill = state.get("booking_prefill") if isinstance(state.get("booking_prefill"), dict) else {}
    prefill = _merge_booking_prefill(_line_booking_prefill_from_text(user_text), saved_prefill)
    people = prefill.get("people")
    shown_shop = next((shop for shop in shown_shops if _shop_id(shop) == shop_id), None)
    shop = await _fetch_java_shop(shop_id)
    shop_name = str((shop or shown_shop or {}).get("name") or f"店家 {shop_id}")
    missing = []
    if not prefill.get("date"):
        missing.append("日期")
    if not prefill.get("time"):
        missing.append("時間")
    if people is None:
        missing.append("人數")
    if missing:
        known = []
        if prefill.get("date"):
            known.append(str(prefill.get("date")))
        if prefill.get("time"):
            known.append(str(prefill.get("time")))
        known_text = f"，已先帶入{' '.join(known)}" if known else ""
        _save_line_recommendation_state(
            user_id,
            query=str(state.get("query") or user_text),
            shown_shop_ids=[shop_id],
            booking_prefill=prefill,
            shown_shops=shown_shops,
        )
        _save_line_booking_draft_state(user_id, _booking_draft_payload(shop_id, shop_name, prefill))
        return [
            build_text_message(
                f"我已鎖定「{shop_name}」{known_text}，還缺{'、'.join(missing)}。"
                "請直接回覆例如「下週五晚上7點 4人」，我再幫你整理確認卡。"
            )
        ]

    booking_date = str(prefill.get("date"))
    booking_time = str(prefill.get("time"))
    draft = _booking_draft_payload(shop_id, shop_name, {**prefill, "date": booking_date, "time": booking_time, "people": people})
    _save_line_booking_draft_state(user_id, draft)
    return [
        build_text_message(
            f"我已整理好「{shop_name}」{booking_date} {booking_time}、{people} 人的訂位草稿。請確認後再送出。"
        ),
        _line_booking_draft_flex_message(draft, line_user_id=user_id),
    ]


async def _build_line_exact_booking_request(user_text: str, user_id: str) -> list[dict] | None:
    if not _booking_intent(user_text) or _payment_intent(user_text):
        return None
    if _explicit_same_day_booking_request(user_text):
        return [build_text_message(_same_day_booking_policy_answer())]

    keyword = _specific_shop_keyword(user_text)
    if not keyword:
        return None

    try:
        shops = await _semantic_hits(keyword, top_k=30)
    except Exception:
        logger.exception("line_exact_booking_search_failed user_id=%s query=%s", user_id, keyword)
        return [build_text_message("我暫時無法確認這間店的訂位入口，請稍後再試一次。")]

    selected_shops = _exact_shop_matches(keyword, shops)
    if not selected_shops:
        return None

    shop_id = _shop_id(selected_shops[0])
    if shop_id is None:
        return None

    shop_name = str(selected_shops[0].get("name") or keyword)
    prefill = _line_booking_prefill_from_text(user_text)
    booking_date = str(prefill.get("date") or (taipei_today() + timedelta(days=1)).isoformat())
    booking_time = str(prefill.get("time") or "19:00")
    people = prefill.get("people")
    _save_line_recommendation_state(
        user_id,
        query=keyword,
        shown_shop_ids=[shop_id],
        booking_prefill=prefill,
        shown_shops=selected_shops,
    )

    missing = []
    if not prefill.get("date"):
        missing.append("日期")
    if not prefill.get("time"):
        missing.append("時間")
    if people is None:
        missing.append("人數")
    if missing:
        line_token = _line_token_for_user(user_id)
        booking_uri = _line_public_uri(
            f"/line/book/{shop_id}?date={quote_plus(booking_date)}&time={quote_plus(booking_time)}"
            f"&people={quote_plus(str(people or 2))}&lt={quote_plus(line_token)}"
        )
        _save_line_booking_draft_state(user_id, _booking_draft_payload(shop_id, shop_name, prefill))
        return [
            build_text_message(
                f"我已鎖定「{shop_name}」，還缺{'、'.join(missing)}。"
                f"你可以直接補齊，或先點這裡填表：{booking_uri}"
            )
        ]

    draft = _booking_draft_payload(shop_id, shop_name, {**prefill, "date": booking_date, "time": booking_time, "people": people})
    _save_line_booking_draft_state(user_id, draft)
    return [
        build_text_message(
            f"我已整理好「{shop_name}」{booking_date} {booking_time}、{people} 人的訂位草稿。請確認後再送出。"
        ),
        _line_booking_draft_flex_message(draft, line_user_id=user_id),
    ]


async def _build_line_booking_action(user_text: str, user_id: str) -> list[dict] | None:
    if not (
        _payment_intent(user_text)
        or _booking_status_intent(user_text)
        or _booking_cancel_intent(user_text)
        or _booking_cancel_confirmation_intent(user_text)
    ):
        return None

    state = _load_line_booking_state(user_id)
    booking = state.get("booking") if isinstance(state.get("booking"), dict) else {}
    if not booking:
        line_token = _line_token_for_user(user_id)
        return [
            build_text_message(
                "我目前找不到最近一筆訂位。你可以點這裡查看我的訂位："
                f"{_line_public_uri(f'/line/my-bookings?lt={quote_plus(line_token)}')}"
            )
        ]

    if _booking_cancel_confirmation_intent(user_text):
        requested_code = _booking_code_from_text(user_text)
        booking_code = str(booking.get("bookingCode") or "").upper()
        if requested_code and booking_code and requested_code != booking_code:
            return [
                build_text_message(
                    f"你提供的訂位編號 `{requested_code}` 和最近一筆 `{booking_code}` 不一致。"
                    "為避免取消錯訂位，請重新確認訂位編號。"
                )
            ]
        status = str(booking.get("status") or "")
        if status == "CANCELED":
            return [_line_booking_flex_message(booking, "canceled", line_user_id=user_id)]
        if status == "EXPIRED":
            return [build_text_message("這筆訂位保留已逾期，不需要取消。")]
        line_token = _line_token_for_user(user_id)
        result = await _cancel_line_booking(str(booking.get("bookingCode") or ""), user_id, line_token)
        if not result.get("success"):
            return [build_text_message(str(result.get("errorMsg") or "取消訂位暫時無法完成，請稍後再試。"))]
        canceled = result.get("data") if isinstance(result.get("data"), dict) else dict(booking)
        _save_line_booking_state(user_id, canceled, "canceled")
        return [_line_booking_flex_message(canceled, "canceled", line_user_id=user_id)]

    phase = str(state.get("phase") or "updated")
    return [_line_booking_flex_message(booking, phase, line_user_id=user_id)]


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

    booking_action_messages = await _build_line_booking_action(user_text, user_id)
    if booking_action_messages is not None:
        return booking_action_messages

    booking_draft_confirmation_messages = await _build_line_booking_draft_confirmation(user_text, user_id)
    if booking_draft_confirmation_messages is not None:
        return booking_draft_confirmation_messages

    booking_draft_update_messages = await _build_line_booking_draft_update(user_text, user_id)
    if booking_draft_update_messages is not None:
        return booking_draft_update_messages

    _reset_line_agent_context_for_fresh_query(user_id, effective_user_text)

    advice_messages = await _build_line_recommendation_advice(user_text, user_id)
    if advice_messages is not None:
        return advice_messages

    contextual_messages = await _build_line_contextual_followup(user_text, user_id)
    if contextual_messages is not None:
        return contextual_messages

    more_messages = await _build_line_more_recommendations(user_text, user_id)
    if more_messages is not None:
        return more_messages

    card_request_messages = await _build_line_card_request(user_text, user_id)
    if card_request_messages is not None:
        return card_request_messages

    named_selection_messages = await _build_line_named_selection_cards(user_text, user_id)
    if named_selection_messages is not None:
        return named_selection_messages

    recommendation_state = _load_line_recommendation_state(user_id)
    recommendation_shops = [
        shop
        for shop in recommendation_state.get("shown_shops", [])
        if isinstance(shop, dict)
    ]
    should_prioritize_booking_followup = (
        _selection_index_from_text(user_text) is not None
        or not _specific_shop_keyword(user_text)
        or (
            bool(recommendation_shops)
            and _recommended_shop_from_text(user_text, recommendation_shops) is not None
        )
    )

    if should_prioritize_booking_followup:
        booking_followup_messages = await _build_line_booking_followup(user_text, user_id)
        if booking_followup_messages is not None:
            return booking_followup_messages

    exact_booking_messages = await _build_line_exact_booking_request(user_text, user_id)
    if exact_booking_messages is not None:
        return exact_booking_messages

    if not should_prioritize_booking_followup:
        booking_followup_messages = await _build_line_booking_followup(user_text, user_id)
        if booking_followup_messages is not None:
            return booking_followup_messages

    clarification_messages = await _build_line_clarification_if_needed(effective_user_text, user_id)
    if clarification_messages is not None:
        return clarification_messages

    forced_card_messages = await _build_line_fallback_recommendation_cards(effective_user_text, user_id)
    if forced_card_messages is not None:
        return forced_card_messages

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
        if isinstance(data, dict) and data:
            return data
        return await _fetch_java_shop_by_fallback_name(shop_id)
    except Exception:
        logger.exception("line_shop_fetch_failed shop_id=%s", shop_id)
        return None


async def _fetch_java_shop_by_fallback_name(shop_id: int) -> dict | None:
    fallback_name = _LINE_SHOP_NAME_FALLBACKS.get(shop_id)
    if not fallback_name:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.java_backend_url}/api/shop/of/name",
                params={"name": fallback_name},
            )
        if response.status_code != 200:
            return None
        payload = response.json()
        data = payload.get("data")
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and int(item.get("id") or 0) == shop_id:
                    return item
            return data[0] if data and isinstance(data[0], dict) else None
        return data if isinstance(data, dict) and data else None
    except Exception:
        logger.exception("line_shop_fallback_fetch_failed shop_id=%s", shop_id)
        return None


def _line_shop_fallback_from_query(shop_id: int, name: str, district: str, mrt: str, avg_price: str) -> dict | None:
    shop_name = str(name or "").strip()
    if not shop_name:
        return None
    shop: dict[str, object] = {
        "id": shop_id,
        "name": shop_name,
        "district": str(district or "").strip(),
        "mrtStation": str(mrt or "").strip(),
    }
    try:
        if str(avg_price or "").strip():
            shop["avgPrice"] = int(float(str(avg_price).strip()))
    except ValueError:
        pass
    return shop


def _line_shop_fallback_from_media(shop_id: int) -> dict | None:
    manifest_shop = _line_media_shop(shop_id)
    if not manifest_shop:
        return None
    overview_raw = manifest_shop.get("overview") if isinstance(manifest_shop, dict) else {}
    overview = overview_raw if isinstance(overview_raw, dict) else {}
    name = _LINE_SHOP_NAME_FALLBACKS.get(shop_id) or str(overview.get("name") or "").strip()
    if not name:
        name = f"店家 {shop_id}"
    return {
        "id": shop_id,
        "name": name,
        "district": str(overview.get("district") or "台北").strip(),
        "mrtStation": str(overview.get("mrtStation") or overview.get("mrt_station") or "").strip(),
    }


def _line_shop_minimal_fallback(shop_id: int) -> dict:
    return {
        "id": shop_id,
        "name": f"店家 {shop_id}",
        "district": "台北",
        "mrtStation": "",
    }


def _line_auth_required_page(shop_id: int, line_token: str = "") -> HTMLResponse:
    detail_uri = _line_public_uri(f"/line/shop/{shop_id}?lt={quote_plus(line_token)}")
    return HTMLResponse(
        _line_html_page(
            "LINE 授權未帶入",
            "這個訂位連結缺少 LINE 授權。請回 LINE 聊天室，重新點推薦卡片裡的「填日期人數」。",
            [("查看店家資訊", detail_uri)],
        ),
        status_code=401,
    )


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


async def _fetch_java_nearby_parking(lng: object, lat: object, limit: int = 3) -> list[dict]:
    try:
        lng_value = float(lng) if lng is not None else None
        lat_value = float(lat) if lat is not None else None
    except (TypeError, ValueError):
        return []
    if lng_value is None or lat_value is None:
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.java_backend_url}/api/parking/nearby",
                params={"lng": lng_value, "lat": lat_value, "radius": 900, "limit": limit},
            )
        if response.status_code != 200:
            return []
        payload = response.json()
        data = payload.get("data")
        return data if isinstance(data, list) else []
    except Exception:
        logger.exception("line_parking_fetch_failed lng=%s lat=%s", lng, lat)
        return []


async def _fetch_line_display_name(line_user_id: str) -> str:
    user_id = str(line_user_id or "").strip()
    token = (settings.line_channel_access_token or "").strip()
    if not user_id or not token:
        return ""
    cached = _LINE_PROFILE_CACHE.get(user_id)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"https://api.line.me/v2/bot/profile/{quote_plus(user_id)}",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code != 200:
            logger.warning("line_profile_fetch_failed status=%s user=%s", response.status_code, user_id[:8])
            _LINE_PROFILE_CACHE[user_id] = ""
            return ""
        payload = response.json()
        display_name = str(payload.get("displayName") or "").strip()
        _LINE_PROFILE_CACHE[user_id] = display_name
        return display_name
    except Exception:
        logger.exception("line_profile_fetch_failed user=%s", user_id[:8])
        return ""


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


async def _reserve_line_booking(
    shop_id: int,
    people: int,
    booking_date: str,
    booking_time: str,
    table_type: str,
    line_user_id: str,
    line_action_token_value: str,
) -> dict:
    user_key = str(line_user_id or "anonymous").strip() or "anonymous"
    idempotency_key = f"line-form:{user_key}:{shop_id}:{people}:{booking_date}:{booking_time}:{table_type}"
    line_display_name = await _fetch_line_display_name(line_user_id)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{settings.java_backend_url}/api/booking/reserve",
                headers={"Content-Type": "application/json"},
                json={
                    "shopId": shop_id,
                    "people": people,
                    "date": booking_date,
                    "time": booking_time,
                    "tableType": table_type,
                    "lineUserId": line_user_id,
                    "lineActionToken": line_action_token_value,
                    "lineDisplayName": line_display_name,
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


async def _pay_line_booking(booking_code: str, line_user_id: str, line_action_token_value: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{settings.java_backend_url}/api/booking/pay-test",
                headers={"Content-Type": "application/json"},
                json={"bookingCode": booking_code, "lineUserId": line_user_id, "lineActionToken": line_action_token_value},
            )
    except Exception:
        logger.exception("line_booking_pay_failed booking_code=%s", booking_code)
        return {"success": False, "errorMsg": "後端付款服務暫時無法連線，請稍後再試。"}
    try:
        payload = response.json()
    except Exception:
        return {"success": False, "errorMsg": "後端付款服務回傳格式異常。"}
    if response.status_code >= 400:
        return {"success": False, "errorMsg": payload.get("errorMsg") or "訂金付款暫時無法完成。"}
    return payload


async def _cancel_line_booking(booking_code: str, line_user_id: str, line_action_token_value: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{settings.java_backend_url}/api/booking/{quote_plus(booking_code)}/cancel",
                headers={"Content-Type": "application/json"},
                json={"lineUserId": line_user_id, "lineActionToken": line_action_token_value},
            )
    except Exception:
        logger.exception("line_booking_cancel_failed booking_code=%s", booking_code)
        return {"success": False, "errorMsg": "後端取消訂位服務暫時無法連線，請稍後再試。"}
    try:
        payload = response.json()
    except Exception:
        return {"success": False, "errorMsg": "後端取消訂位服務回傳格式異常。"}
    if response.status_code >= 400:
        return {"success": False, "errorMsg": payload.get("errorMsg") or "取消訂位暫時無法完成。"}
    return payload


async def _update_line_parking_preference(
    booking_code: str,
    line_user_id: str,
    line_action_token_value: str,
    driving: bool = True,
) -> dict:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{settings.java_backend_url}/api/booking/{quote_plus(booking_code)}/parking-preference",
                headers={"Content-Type": "application/json"},
                json={
                    "drivingToBooking": bool(driving),
                    "parkingReminderEnabled": bool(driving),
                    "lineUserId": line_user_id,
                    "lineActionToken": line_action_token_value,
                },
            )
    except Exception:
        logger.exception("line_parking_preference_failed booking_code=%s", booking_code)
        return {"success": False, "errorMsg": "後端停車提醒服務暫時無法連線，請稍後再試。"}
    try:
        payload = response.json()
    except Exception:
        return {"success": False, "errorMsg": "後端停車提醒服務回傳格式異常。"}
    if response.status_code >= 400:
        return {"success": False, "errorMsg": payload.get("errorMsg") or "停車提醒暫時無法更新。"}
    return payload


async def _respond_line_incident_proposal(
    booking_code: str,
    incident_id: int,
    action: str,
    line_user_id: str,
    line_action_token_value: str,
) -> dict:
    if action not in {"accept", "decline"}:
        return {"success": False, "errorMsg": "不支援的提案回覆。"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{settings.java_backend_url}/api/booking/{quote_plus(booking_code)}/incidents/{incident_id}/proposal/{action}",
                headers={"Content-Type": "application/json"},
                json={
                    "lineUserId": line_user_id,
                    "lineActionToken": line_action_token_value,
                },
            )
    except Exception:
        logger.exception("line_incident_proposal_%s_failed booking_code=%s incident_id=%s", action, booking_code, incident_id)
        return {"success": False, "errorMsg": "後端救場提案服務暫時無法連線，請稍後再試。"}
    try:
        payload = response.json()
    except Exception:
        return {"success": False, "errorMsg": "後端救場提案服務回傳格式異常。"}
    if response.status_code >= 400:
        return {"success": False, "errorMsg": payload.get("errorMsg") or "救場提案暫時無法回覆。"}
    return payload


async def _fetch_line_bookings(line_user_id: str = "", line_action_token_value: str = "") -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            params = (
                {"lineUserId": line_user_id, "lineActionToken": line_action_token_value}
                if str(line_user_id or "").strip()
                else {}
            )
            response = await client.get(
                f"{settings.java_backend_url}/api/booking/my",
                params=params,
            )
    except Exception:
        logger.exception("line_booking_my_failed")
        return []
    try:
        payload = response.json()
    except Exception:
        return []
    if response.status_code >= 400 or not payload.get("success"):
        return []
    data = payload.get("data")
    return data if isinstance(data, list) else []


async def _fetch_line_booking(booking_code: str, line_user_id: str = "", line_action_token_value: str = "") -> dict | None:
    for booking in await _fetch_line_bookings(line_user_id, line_action_token_value):
        if str(booking.get("bookingCode") or "") == str(booking_code or ""):
            return booking
    return None


async def _create_line_availability_watch(
    shop_id: int,
    people: int,
    booking_date: str,
    booking_time: str,
    table_type: str,
    line_user_id: str,
    line_action_token_value: str,
) -> dict:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{settings.java_backend_url}/api/availability/watches",
                headers={"Content-Type": "application/json"},
                json={
                    "shopId": shop_id,
                    "people": people,
                    "date": booking_date,
                    "time": booking_time,
                    "tableType": table_type,
                    "lineUserId": line_user_id,
                    "lineActionToken": line_action_token_value,
                },
            )
    except Exception:
        logger.exception("line_availability_watch_failed shop_id=%s", shop_id)
        return {"success": False, "errorMsg": "後端空位通知服務暫時無法連線，請稍後再試。"}
    try:
        payload = response.json()
    except Exception:
        return {"success": False, "errorMsg": "後端空位通知服務回傳格式異常。"}
    if response.status_code >= 400:
        return {"success": False, "errorMsg": payload.get("errorMsg") or "空位通知暫時無法建立。"}
    return payload


async def _fetch_line_notifications() -> dict:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{settings.java_backend_url}/api/availability/notifications",
                headers={"X-Demo-Mode": "true"},
            )
    except Exception:
        logger.exception("line_notifications_fetch_failed")
        return {"unreadCount": 0, "items": []}
    try:
        payload = response.json()
    except Exception:
        return {"unreadCount": 0, "items": []}
    if response.status_code >= 400 or not payload.get("success"):
        return {"unreadCount": 0, "items": []}
    data = payload.get("data")
    return data if isinstance(data, dict) else {"unreadCount": 0, "items": []}


async def _push_line_availability_watch_created(line_user_id: str, watch: dict) -> None:
    user_id = str(line_user_id or "").strip()
    if not user_id or not watch:
        return
    result = await push_messages(
        user_id=user_id,
        messages=[_line_availability_watch_created_flex(watch, user_id)],
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled,
    )
    if not result.get("ok"):
        logger.warning("line_availability_watch_push_failed user_id=%s result=%s", user_id, result)


async def _push_line_booking_update(line_user_id: str, booking: dict, phase: str) -> None:
    user_id = str(line_user_id or "").strip()
    if not user_id or not booking:
        return
    result = await push_messages(
        user_id=user_id,
        messages=[_line_booking_flex_message(booking, phase, line_user_id=user_id)],
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled,
    )
    if not result.get("ok"):
        logger.warning("line_booking_push_failed user_id=%s result=%s", user_id, result)


def _line_booking_flex_message(booking: dict, phase: str, line_user_id: str = "") -> dict:
    shop_id = int(booking.get("shopId") or 0)
    booking_code = str(booking.get("bookingCode") or "")
    status = str(booking.get("status") or "CONFIRMED")
    needs_deposit = bool(booking.get("needsDeposit"))
    line_token = _line_token_for_user(line_user_id) if line_user_id else ""
    title = "訂位保留成功，待付訂金" if status == "PENDING_PAYMENT" else "訂位已完成"
    if phase == "paid":
        title = "訂金付款成功，訂位完成"
    if phase == "rescheduled":
        title = "訂位已更新"
    if phase == "canceled" or status == "CANCELED":
        title = "訂位已取消"
    line_query = f"&lt={quote_plus(line_token)}" if line_token else ""
    status_uri = _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(booking_code)}{line_query}")
    pay_uri = _line_public_uri(f"/line/book/{shop_id}/pay?bookingCode={quote_plus(booking_code)}{line_query}")
    cancel_uri = _line_public_uri(f"/line/book/{shop_id}/cancel?bookingCode={quote_plus(booking_code)}{line_query}")
    parking_uri = _line_public_uri(
        f"/line/book/{shop_id}/parking?bookingCode={quote_plus(booking_code)}&driving=true{line_query}"
    )
    rows = [
        ("店家", str(booking.get("shopName") or f"店家 {shop_id}")),
        ("日期時間", f"{booking.get('date') or '-'} {booking.get('time') or ''}".strip()),
        ("人數", f"{booking.get('people') or '-'} 人"),
        ("狀態", _line_booking_status_label(status)),
    ]
    if needs_deposit:
        rows.append(("訂金", f"NT$ {booking.get('depositTotal') or 0}"))
    if booking.get("paymentTransId"):
        rows.append(("交易編號", str(booking.get("paymentTransId"))))
    buttons = []
    if status == "PENDING_PAYMENT" and needs_deposit:
        buttons.append(
            {
                "type": "button",
                "style": "primary",
                "height": "sm",
                "action": {"type": "uri", "label": "立即繳訂金", "uri": pay_uri},
            }
        )
    buttons.append(
        {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {"type": "uri", "label": "查看訂位狀態", "uri": status_uri},
        }
    )
    if status in {"PENDING_PAYMENT", "PAID", "CONFIRMED"}:
        buttons.append(
            {
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {"type": "uri", "label": "我會開車，提醒停車", "uri": parking_uri},
            }
        )
        buttons.append(
            {
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {"type": "uri", "label": "取消訂位", "uri": cancel_uri},
            }
        )
    return {
        "type": "flex",
        "altText": title,
        "contents": {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "BYTEBITES BOOKING", "size": "xs", "color": "#16833a", "weight": "bold"},
                    {"type": "text", "text": title, "size": "lg", "weight": "bold", "wrap": True},
                    {"type": "text", "text": f"訂位編號 {booking_code}", "size": "sm", "color": "#666666", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "margin": "md",
                        "contents": [_line_booking_flex_row(label, value) for label, value in rows],
                    },
                    {
                        "type": "text",
                        "text": _line_booking_deposit_text(booking),
                        "size": "xs",
                        "color": "#777777",
                        "wrap": True,
                        "margin": "md",
                    },
                ],
            },
            "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
        },
    }


def _line_booking_incident_flex_message(incident: dict, line_user_id: str = "") -> dict:
    booking = incident.get("booking") if isinstance(incident.get("booking"), dict) else {}
    shop_id = int(incident.get("shopId") or booking.get("shopId") or 0)
    shop_name = str(incident.get("shopName") or booking.get("shopName") or f"店家 {shop_id}")
    booking_code = str(incident.get("bookingCode") or booking.get("bookingCode") or "")
    incident_type = str(incident.get("incidentType") or "")
    title = str(incident.get("title") or "訂位現場狀況更新")
    message = str(incident.get("customerMessage") or "")
    action_label = str(incident.get("actionLabel") or "已為你保留狀態")
    date = str(incident.get("date") or booking.get("date") or "")
    original_time = str(incident.get("originalTime") or incident.get("time") or booking.get("time") or "")
    adjusted_time = str(incident.get("adjustedTime") or "")
    people = str(incident.get("people") or booking.get("people") or "")
    line_token = _line_token_for_user(line_user_id) if line_user_id else ""
    line_query = f"&lt={quote_plus(line_token)}" if line_token else ""
    status_uri = _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(booking_code)}{line_query}")
    rows = [
        ("店家", shop_name),
        ("訂位", f"{date or '-'} {original_time or ''}".strip()),
        ("人數", f"{people or '-'} 人"),
    ]
    if adjusted_time:
        rows.append(("新預估", adjusted_time))
    rows.append(("處理", action_label))
    alt_text = "訂位現場狀況更新"
    if incident_type == "RESTAURANT_DELAY":
        alt_text = f"{shop_name} 入座時間更新"
    elif incident_type == "CUSTOMER_LATE":
        alt_text = "已通知店家你會晚到"
    return {
        "type": "flex",
        "altText": alt_text,
        "contents": {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "BYTEBITES RESCUE", "size": "xs", "color": "#16833a", "weight": "bold"},
                    {"type": "text", "text": title, "size": "lg", "weight": "bold", "wrap": True},
                    {"type": "text", "text": f"訂位編號 {booking_code}", "size": "sm", "color": "#666666", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "margin": "md",
                        "contents": [_line_booking_flex_row(label, value) for label, value in rows],
                    },
                    {
                        "type": "text",
                        "text": message or "系統已記錄此現場狀況，並保留後續處理狀態。",
                        "size": "xs",
                        "color": "#555555",
                        "wrap": True,
                        "margin": "md",
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {"type": "uri", "label": "查看訂位狀態", "uri": status_uri},
                    }
                ],
            },
        },
    }


def _line_booking_incident_proposal_flex_message(incident: dict, line_user_id: str = "") -> dict:
    booking = incident.get("booking") if isinstance(incident.get("booking"), dict) else {}
    proposal = incident.get("proposedChange") if isinstance(incident.get("proposedChange"), dict) else {}
    shop_id = int(incident.get("shopId") or booking.get("shopId") or 0)
    shop_name = str(incident.get("shopName") or booking.get("shopName") or f"店家 {shop_id}")
    booking_code = str(incident.get("bookingCode") or booking.get("bookingCode") or "")
    incident_id = str(incident.get("id") or "")
    date = str(incident.get("bookingDate") or incident.get("date") or booking.get("date") or "")
    original_time = str(incident.get("bookingTime") or incident.get("originalTime") or incident.get("time") or booking.get("time") or "")
    proposed_date = str(proposal.get("date") or date)
    proposed_time = str(proposal.get("time") or "")
    proposed_people = str(proposal.get("people") or incident.get("people") or booking.get("people") or "")
    expires_at = str(proposal.get("expiresAt") or "")
    message = str(proposal.get("message") or "店家提出替代時段，請確認是否接受。")
    line_token = _line_token_for_user(line_user_id) if line_user_id else ""
    line_query = f"&lt={quote_plus(line_token)}" if line_token else ""
    status_uri = _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(booking_code)}{line_query}")
    accept_uri = _line_public_uri(
        f"/line/book/{shop_id}/incident-proposal/accept?bookingCode={quote_plus(booking_code)}&incidentId={quote_plus(incident_id)}{line_query}"
    )
    decline_uri = _line_public_uri(
        f"/line/book/{shop_id}/incident-proposal/decline?bookingCode={quote_plus(booking_code)}&incidentId={quote_plus(incident_id)}{line_query}"
    )
    rows = [
        ("店家", shop_name),
        ("原訂位", f"{date or '-'} {original_time or ''}".strip()),
        ("建議改到", f"{proposed_date or '-'} {proposed_time or ''}".strip()),
        ("人數", f"{proposed_people or '-'} 人"),
    ]
    if expires_at:
        rows.append(("有效至", expires_at))
    buttons = [
        {
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {"type": "uri", "label": "接受改時段", "uri": accept_uri},
        },
        {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {"type": "uri", "label": "拒絕提案", "uri": decline_uri},
        },
        {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {"type": "uri", "label": "查看訂位", "uri": status_uri},
        },
    ]
    return {
        "type": "flex",
        "altText": f"{shop_name} 提出替代時段",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "BYTEBITES RESCUE", "size": "xs", "color": "#16833a", "weight": "bold"},
                    {"type": "text", "text": "店家提出替代時段", "size": "lg", "weight": "bold", "wrap": True},
                    {"type": "text", "text": f"訂位編號 {booking_code}", "size": "sm", "color": "#666666", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "margin": "md",
                        "contents": [_line_booking_flex_row(label, value) for label, value in rows],
                    },
                    {
                        "type": "text",
                        "text": message,
                        "size": "xs",
                        "color": "#555555",
                        "wrap": True,
                        "margin": "md",
                    },
                ],
            },
            "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
        },
    }


def _line_refund_operations_digest_flex_message(report: dict) -> dict:
    shop_id = int(report.get("shopId") or 0)
    shop_name = str(report.get("shopName") or f"店家 {shop_id}")
    headline = str(report.get("headline") or "退款營運摘要")
    status = str(report.get("status") or "CLEAR")
    action = str(report.get("recommendedAction") or "NO_REFUND_ACTION")
    pending_count = _line_report_int(report.get("pendingEscalationCount"))
    escalated_count = _line_report_int(report.get("escalatedCount"))
    failed_count = _line_report_int(report.get("failedCount"))
    stuck_count = _line_report_int(report.get("stuckProcessingCount"))
    action_label = {
        "ESCALATE_FAILED_REFUNDS": "先升級失敗退款",
        "ESCALATE_STUCK_REFUNDS": "先升級逾時退款",
        "FOLLOW_UP_ESCALATED_REFUNDS": "追蹤已升級退款",
        "NO_REFUND_ACTION": "無需跟進",
    }.get(action, action or "無需跟進")
    rows = [
        ("店家", shop_name),
        ("建議動作", action_label),
        ("未升級", f"{pending_count} 件"),
        ("已升級", f"{escalated_count} 件"),
        ("失敗 / 逾時", f"{failed_count} / {stuck_count} 件"),
    ]
    pending_items = report.get("pendingEscalationItems") if isinstance(report.get("pendingEscalationItems"), list) else []
    item_blocks = []
    for item in pending_items[:2]:
        if not isinstance(item, dict):
            continue
        booking_code = str(item.get("bookingCode") or "-")
        reason = _line_refund_reason_label(str(item.get("slaReason") or ""))
        amount = _line_report_int(item.get("settlementAmount") or abs(_line_report_int(item.get("deltaAmount"))))
        requested_at = str(item.get("settlementRequestedAt") or "")
        item_blocks.append(
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "xs",
                "contents": [
                    {"type": "text", "text": booking_code, "size": "sm", "weight": "bold", "wrap": True},
                    {
                        "type": "text",
                        "text": f"{reason} · NT$ {amount:,}" + (f" · {requested_at}" if requested_at else ""),
                        "size": "xs",
                        "color": "#666666",
                        "wrap": True,
                    },
                ],
            }
        )
    if not item_blocks:
        item_blocks.append(
            {
                "type": "text",
                "text": "目前沒有未升級退款；請追蹤已升級項目或維持監控。",
                "size": "xs",
                "color": "#555555",
                "wrap": True,
            }
        )
    merchant_uri = _line_public_uri("/merchant")
    title = "退款營運摘要"
    if status == "ACTION_REQUIRED":
        title = "退款需要升級處理"
    elif status == "FOLLOW_UP":
        title = "退款已升級待追蹤"
    return {
        "type": "flex",
        "altText": f"{shop_name} 退款營運摘要",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "BYTEBITES OPS", "size": "xs", "color": "#16833a", "weight": "bold"},
                    {"type": "text", "text": title, "size": "lg", "weight": "bold", "wrap": True},
                    {"type": "text", "text": headline, "size": "sm", "color": "#666666", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "margin": "md",
                        "contents": [_line_booking_flex_row(label, value) for label, value in rows],
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "margin": "md",
                        "contents": item_blocks,
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "action": {"type": "uri", "label": "開啟商家後台", "uri": merchant_uri},
                    }
                ],
            },
        },
    }


def _line_report_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _line_refund_reason_label(reason: str) -> str:
    if reason == "FAILED_REFUND":
        return "退款失敗"
    if reason == "STUCK_PROCESSING":
        return "逾時未回寫"
    return "退款注意"


def _line_booking_draft_flex_message(draft: dict, line_user_id: str = "") -> dict:
    shop_id = int(draft.get("shop_id") or 0)
    shop_name = str(draft.get("shop_name") or f"店家 {shop_id}")
    booking_date = str(draft.get("date") or "")
    booking_time = str(draft.get("time") or "")
    people = int(draft.get("people") or 0)
    table_type = str(draft.get("table_type") or "normal")
    line_token = _line_token_for_user(line_user_id) if line_user_id else ""
    line_query = f"&lt={quote_plus(line_token)}" if line_token else ""
    confirm_uri = _line_public_uri(
        f"/line/book/{shop_id}/confirm?date={quote_plus(booking_date)}&time={quote_plus(booking_time)}"
        f"&people={quote_plus(str(people))}&tableType={quote_plus(table_type)}{line_query}"
    )
    edit_uri = _line_public_uri(
        f"/line/book/{shop_id}?date={quote_plus(booking_date)}&time={quote_plus(booking_time)}"
        f"&people={quote_plus(str(people or 2))}&tableType={quote_plus(table_type)}{line_query}"
    )
    rows = [
        ("店家", shop_name),
        ("日期時間", f"{booking_date or '-'} {booking_time or ''}".strip()),
        ("人數", f"{people or '-'} 人"),
        ("座位", {"normal": "一般座位", "bar": "吧台", "private": "包廂"}.get(table_type, "一般座位")),
    ]
    return {
        "type": "flex",
        "altText": f"確認訂位：{shop_name}",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "BYTEBITES DRAFT", "size": "xs", "color": "#16833a", "weight": "bold"},
                    {"type": "text", "text": "確認訂位內容", "size": "lg", "weight": "bold", "wrap": True},
                    {
                        "type": "text",
                        "text": "確認後才會送出訂位；你也可以直接回「沒問題」或「確認訂位」。",
                        "size": "xs",
                        "color": "#666666",
                        "wrap": True,
                    },
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "margin": "md",
                        "contents": [_line_booking_flex_row(label, value) for label, value in rows],
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "action": {"type": "uri", "label": "確認送出訂位", "uri": confirm_uri},
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {"type": "uri", "label": "修改日期人數", "uri": edit_uri},
                    },
                ],
            },
        },
    }


def _line_booking_flex_row(label: str, value: str) -> dict:
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {"type": "text", "text": label, "size": "xs", "color": "#777777", "flex": 2},
            {"type": "text", "text": value or "-", "size": "xs", "color": "#222222", "wrap": True, "flex": 5},
        ],
    }


def _line_booking_status_label(status: str) -> str:
    return {
        "PENDING_PAYMENT": "待付訂金",
        "PAID": "已付款，訂位完成",
        "CONFIRMED": "訂位完成",
        "CANCELED": "已取消",
        "EXPIRED": "保留逾期",
    }.get(str(status or ""), str(status or "未知"))


def _line_booking_deposit_text(booking: dict) -> str:
    status = str(booking.get("status") or "")
    if booking.get("needsDeposit"):
        amount = booking.get("depositTotal") or 0
        if status == "PENDING_PAYMENT":
            expires = booking.get("holdExpiresAt")
            return f"需繳訂金 NT$ {amount}。座位已先保留，請在期限內付款。" + (f" 保留至 {expires}。" if expires else "")
        if status == "PAID":
            return f"訂金 NT$ {amount} 已完成付款，訂位已成立。"
        return f"需訂金 NT$ {amount}。"
    return "免訂金，訂位建立後即成立。"


def _line_parking_reminder_flex_message(payload: dict) -> dict:
    shop_id = int(payload.get("shopId") or 0)
    shop_name = str(payload.get("shopName") or f"店家 {shop_id}")
    booking_code = str(payload.get("bookingCode") or "")
    date = str(payload.get("date") or "")
    time = str(payload.get("time") or "")
    lots = payload.get("parkingLots") if isinstance(payload.get("parkingLots"), list) else []
    line_user_id = str(payload.get("lineUserId") or "")
    line_token = _line_token_for_user(line_user_id) if line_user_id else ""
    status_uri = _line_public_uri(f"/line/book/{shop_id}/status?bookingCode={quote_plus(booking_code)}&lt={quote_plus(line_token)}")
    first_navigation = ""
    reserve_uri = ""
    lot_blocks = []
    for index, lot in enumerate(lots[:3]):
        if not isinstance(lot, dict):
            continue
        name = str(lot.get("name") or "停車場")
        distance = _line_parking_distance(lot.get("distanceMeters"))
        spaces = _line_parking_spaces(lot)
        updated_at = str(lot.get("updatedAt") or "").strip()
        if not first_navigation:
            first_navigation = str(lot.get("navigationUrl") or "").strip()
        if not reserve_uri:
            reserve_uri = _line_public_uri(
                f"/line/book/{shop_id}/parking-reserve?bookingCode={quote_plus(booking_code)}&lot={index}&lt={quote_plus(line_token)}"
            )
        subtitle = " · ".join(part for part in [distance, spaces, f"更新 {updated_at}" if updated_at else ""] if part)
        lot_blocks.append(
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "xs",
                "contents": [
                    {"type": "text", "text": name, "size": "sm", "weight": "bold", "wrap": True},
                    {"type": "text", "text": subtitle or "車位資料更新中", "size": "xs", "color": "#666666", "wrap": True},
                ],
            }
        )
    if not lot_blocks:
        lot_blocks.append(
            {
                "type": "text",
                "text": "目前抓不到附近停車場剩餘車位，建議提早出發並使用地圖查詢。",
                "size": "sm",
                "color": "#555555",
                "wrap": True,
            }
        )
    footer = []
    if reserve_uri:
        footer.append(
            {
                "type": "button",
                "style": "primary",
                "height": "sm",
                "action": {"type": "uri", "label": "保留最近車位", "uri": reserve_uri},
            }
        )
    if first_navigation:
        footer.append(
            {
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {"type": "uri", "label": "導航到最近停車場", "uri": first_navigation},
            }
        )
    footer.append(
        {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {"type": "uri", "label": "查看訂位", "uri": status_uri},
        }
    )
    return {
        "type": "flex",
        "altText": f"{shop_name} 附近停車提醒",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "BYTEBITES PARKING", "size": "xs", "color": "#16833a", "weight": "bold"},
                    {"type": "text", "text": "出發前停車提醒", "size": "lg", "weight": "bold", "wrap": True},
                    {"type": "text", "text": shop_name, "size": "md", "weight": "bold", "wrap": True},
                    {"type": "text", "text": f"{date} {time} · 訂位編號 {booking_code}", "size": "xs", "color": "#666666", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "margin": "md",
                        "contents": lot_blocks,
                    },
                    {
                        "type": "text",
                        "text": "車位來自台北市即時剩餘車位資料，可能快速變動，請以到場狀況為準。",
                        "size": "xs",
                        "color": "#777777",
                        "wrap": True,
                        "margin": "md",
                    },
                ],
            },
            "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": footer},
        },
    }


def _line_parking_reservation_flex_message(reservation: dict) -> dict:
    lot_name = str(reservation.get("lotName") or "停車場")
    shop_name = str(reservation.get("shopName") or "餐廳")
    floor = str(reservation.get("floor") or "")
    zone = str(reservation.get("zone") or "")
    stall = str(reservation.get("stall") or "")
    hold_until = str(reservation.get("holdUntil") or "入場前 15 分鐘")
    booking_code = str(reservation.get("bookingCode") or "")
    navigation_url = str(reservation.get("navigationUrl") or "").strip()
    body_contents = [
        {"type": "text", "text": "BYTEBITES PARKING", "size": "xs", "color": "#16833a", "weight": "bold"},
        {"type": "text", "text": "已保留車位", "size": "lg", "weight": "bold", "wrap": True},
        {"type": "text", "text": lot_name, "size": "md", "weight": "bold", "wrap": True},
        {"type": "text", "text": f"{floor} · {zone} · {stall}", "size": "xl", "weight": "bold", "color": "#171512", "wrap": True},
        {"type": "separator", "margin": "md"},
        {"type": "text", "text": f"餐廳：{shop_name}", "size": "sm", "wrap": True, "margin": "md"},
        {"type": "text", "text": f"訂位編號：{booking_code}", "size": "xs", "color": "#666666", "wrap": True},
        {"type": "text", "text": f"保留至：{hold_until}", "size": "sm", "weight": "bold", "wrap": True},
        {
            "type": "text",
            "text": "抵達後請依現場停車場指示入場。此為 ByteBites 展示保留流程，不會向停車場業者送出正式交易。",
            "size": "xs",
            "color": "#777777",
            "wrap": True,
            "margin": "md",
        },
    ]
    footer = []
    if navigation_url:
        footer.append(
            {
                "type": "button",
                "style": "primary",
                "height": "sm",
                "action": {"type": "uri", "label": "導航到停車場", "uri": navigation_url},
            }
        )
    contents = {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
        },
    }
    if footer:
        contents["footer"] = {"type": "box", "layout": "vertical", "spacing": "sm", "contents": footer}
    return {
        "type": "flex",
        "altText": f"{lot_name} 已保留車位 {floor} {zone} {stall}",
        "contents": contents,
    }


def _line_booking_deposit_note(status: str, needs_deposit: bool, deposit_total, hold_expires_at: str) -> str:
    booking = {
        "status": status,
        "needsDeposit": needs_deposit,
        "depositTotal": deposit_total,
        "holdExpiresAt": hold_expires_at,
    }
    return f"<p>{_html_escape(_line_booking_deposit_text(booking))}</p>"


def _line_availability_watch_created_flex(watch: dict, line_user_id: str = "") -> dict:
    shop_id = int(watch.get("shopId") or watch.get("shop_id") or 0)
    date = str(watch.get("date") or "")
    time = str(watch.get("time") or "")
    people = str(watch.get("people") or "")
    status_uri = _line_public_uri("/line/notifications")
    return {
        "type": "flex",
        "altText": "已設定空位通知",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "BYTEBITES WATCH", "size": "xs", "color": "#16833a", "weight": "bold"},
                    {"type": "text", "text": "已設定空位通知", "size": "lg", "weight": "bold", "wrap": True},
                    {"type": "text", "text": str(watch.get("shopName") or f"店家 {shop_id}"), "size": "sm", "color": "#333333", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "text",
                        "text": f"{date} {time} · {people} 人。若此時段釋出足夠座位，我會主動通知你。",
                        "size": "sm",
                        "color": "#555555",
                        "wrap": True,
                        "margin": "md",
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {"type": "uri", "label": "查看通知", "uri": status_uri},
                    }
                ],
            },
        },
    }


def _line_availability_flex_message(payload: dict) -> dict:
    shop_id = int(payload.get("shopId") or 0)
    shop_name = str(payload.get("shopName") or f"店家 {shop_id}")
    date = str(payload.get("date") or "")
    time = str(payload.get("time") or "")
    table_type = str(payload.get("tableType") or "normal")
    people = str(payload.get("people") or "2")
    line_user_id = str(payload.get("lineUserId") or "")
    line_token = _line_token_for_user(line_user_id) if line_user_id else ""
    booking_uri = _line_public_uri(
        f"/line/book/{shop_id}?people={quote_plus(people)}&date={quote_plus(date)}&time={quote_plus(time)}&tableType={quote_plus(table_type)}&lt={quote_plus(line_token)}"
    )
    notifications_uri = _line_public_uri("/line/notifications")
    return {
        "type": "flex",
        "altText": f"{shop_name} 有空位了",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "BYTEBITES ALERT", "size": "xs", "color": "#16833a", "weight": "bold"},
                    {"type": "text", "text": "有空位了", "size": "lg", "weight": "bold", "wrap": True},
                    {"type": "text", "text": shop_name, "size": "md", "weight": "bold", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "text",
                        "text": f"{date} {time} 可訂 {people} 人。座位可能很快被訂走，建議立即確認。",
                        "size": "sm",
                        "color": "#444444",
                        "wrap": True,
                        "margin": "md",
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "action": {"type": "uri", "label": "立即訂位", "uri": booking_uri},
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {"type": "uri", "label": "查看通知", "uri": notifications_uri},
                    },
                ],
            },
        },
    }


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
    shops = _line_media_payload().get("shops") or {}
    shop = shops.get(str(shop_id))
    if not isinstance(shop, dict):
        shop = shops.get(str(_LINE_MEDIA_ALIASES.get(shop_id, shop_id)))
    return shop if isinstance(shop, dict) else {}


def _line_display_rating(raw) -> str:
    return line_display_rating(raw)


def _line_business_hours(shop: dict, metadata: dict) -> list[str]:
    raw_candidates = [
        metadata.get("openingHours"),
        metadata.get("businessHours"),
        shop.get("businessHours"),
        shop.get("business_hours"),
        shop.get("openHours"),
        shop.get("open_hours"),
    ]
    for raw in raw_candidates:
        hours = _line_parse_hours(raw)
        if hours:
            return hours
    return []


def _line_parse_hours(raw) -> list[str]:
    return line_parse_hours(raw)


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


def _line_detail_image_uri(shop_id: int) -> str:
    candidates = _line_photo_candidates(shop_id)
    return candidates[0] if candidates else ""


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
    rating_label = _line_display_rating(rating)
    if rating_label and comments:
        basis.append(f"Google 評分 {rating_label}，累積 {comments} 則評論，可作為穩定度參考。")
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
    return line_review_rating(review)


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
    return line_review_card_html(label, review)


def _line_bullet_html(items: list[str]) -> str:
    return line_bullet_html(items)


def _line_pills_html(items: list[str]) -> str:
    return line_pills_html(items)


def _line_hours_html(hours: list[str]) -> str:
    return line_hours_html(hours)


def _parking_reservation_key(booking_code: str, lot: dict) -> str:
    lot_identity = str(lot.get("id") or lot.get("name") or lot.get("address") or "parking").strip()
    return f"{booking_code}:{lot_identity}"


def _mock_parking_reservation(booking: dict, shop: dict, lot: dict) -> dict:
    booking_code = str(booking.get("bookingCode") or "")
    key = _parking_reservation_key(booking_code, lot)
    if key in _PARKING_RESERVATIONS:
        return _PARKING_RESERVATIONS[key]

    seed = hashlib.sha256(
        "|".join(
            [
                booking_code,
                str((shop or {}).get("id") or (shop or {}).get("shopId") or ""),
                str(lot.get("id") or lot.get("name") or ""),
            ]
        ).encode("utf-8")
    ).hexdigest()
    zones = ("A 區", "B 區", "C 區", "D 區")
    floors = ("B1", "B2", "B3", "B4")
    zone = zones[int(seed[0:2], 16) % len(zones)]
    floor = floors[int(seed[2:4], 16) % len(floors)]
    stall_number = int(seed[4:8], 16) % 48 + 1
    booking_date = str(booking.get("date") or "")
    booking_time = str(booking.get("time") or "")
    hold_until = _parking_hold_until_label(booking_date, booking_time)
    reservation = {
        "bookingCode": booking_code,
        "shopId": (shop or {}).get("id") or (shop or {}).get("shopId"),
        "shopName": (shop or {}).get("name") or booking.get("shopName") or "",
        "lotName": lot.get("name") or "停車場",
        "lotAddress": lot.get("address") or "",
        "floor": floor,
        "zone": zone,
        "stall": f"{zone[0]}-{stall_number:02d}",
        "holdUntil": hold_until,
        "navigationUrl": lot.get("navigationUrl") or "",
        "reservedAt": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
    }
    _PARKING_RESERVATIONS[key] = reservation
    return reservation


def _parking_hold_until_label(booking_date: str, booking_time: str) -> str:
    try:
        reservation_at = datetime.fromisoformat(f"{booking_date}T{booking_time}")
    except ValueError:
        return "入場前 15 分鐘"
    hold_until = reservation_at - timedelta(minutes=15)
    return hold_until.strftime("%m/%d %H:%M")


def _parking_lot_after_reservation(lot: dict, reservation: dict | None = None) -> dict:
    adjusted = dict(lot)
    available = adjusted.get("availableCar")
    if isinstance(available, int):
        adjusted["availableCar"] = max(0, available - 1)
    if reservation:
        adjusted["reservedFloor"] = reservation.get("floor")
        adjusted["reservedZone"] = reservation.get("zone")
        adjusted["reservedStall"] = reservation.get("stall")
    return adjusted


async def _push_line_parking_reservation(line_user_id: str, reservation: dict) -> None:
    result = await push_messages(
        user_id=line_user_id,
        messages=[_line_parking_reservation_flex_message(reservation)],
        channel_access_token=settings.line_channel_access_token,
        enabled=settings.line_reply_enabled,
    )
    if not result.get("ok"):
        logger.warning("line_parking_reservation_push_failed user_id=%s result=%s", line_user_id[:8], result)


def _line_parking_html(
    lots: list[dict],
    shop_id: int | None = None,
    booking_code: str = "",
    line_token: str = "",
    reserve: bool = False,
) -> str:
    if not lots:
        return ""
    cards: list[str] = []
    for index, lot in enumerate(lots[:3]):
        reservation = _PARKING_RESERVATIONS.get(_parking_reservation_key(booking_code, lot)) if booking_code else None
        display_lot = _parking_lot_after_reservation(lot, reservation) if reservation else lot
        name = _html_escape(str(display_lot.get("name") or "停車場"))
        area = _html_escape(str(display_lot.get("area") or ""))
        address = _html_escape(str(display_lot.get("address") or ""))
        distance = _line_parking_distance(display_lot.get("distanceMeters"))
        spaces = _line_parking_spaces(display_lot)
        pay_text = _html_escape(str(display_lot.get("payText") or ""))
        service_time = _html_escape(str(display_lot.get("serviceTime") or ""))
        navigation_url = _html_escape(str(display_lot.get("navigationUrl") or ""))
        details = " · ".join(part for part in [area, distance, spaces] if part)
        address_html = f"<p>{address}</p>" if address else ""
        pay_html = f"<p>收費：{pay_text}</p>" if pay_text else ""
        service_html = f"<p>服務：{service_time}</p>" if service_time else ""
        navigation_html = f'<a href="{navigation_url}">導航到停車場</a>' if navigation_url else ""
        reserve_html = ""
        if reserve and shop_id and booking_code:
            reserve_url = _line_public_uri(
                f"/line/book/{shop_id}/parking-reserve?bookingCode={quote_plus(booking_code)}&lot={index}&lt={quote_plus(line_token)}"
            )
            reserve_html = f'<a class="parking-reserve" href="{reserve_url}">保留車位</a>'
        reserved_detail = " · ".join(
            str(display_lot.get(key) or "")
            for key in ("reservedFloor", "reservedZone", "reservedStall")
            if str(display_lot.get(key) or "").strip()
        )
        reserved_html = f"<p><strong>保留車格：{_html_escape(reserved_detail)}</strong></p>" if reserved_detail else ""
        cards.append(
            f"""
            <div class="parking-card">
              <strong>{name}</strong>
              <p>{_html_escape(details)}</p>
              {reserved_html}
              {address_html}
              {pay_html}
              {service_html}
              {reserve_html}
              {navigation_html}
            </div>
            """
        )
    return f"""
        <section id="parking">
          <h2>附近停車場</h2>
          <p>依店家座標排序，車位以台北市公開即時資料為準。</p>
          <div class="parking-list">{''.join(cards)}</div>
        </section>
    """


def _line_parking_distance(value: object) -> str:
    return line_parking_distance(value)


def _line_parking_spaces(lot: dict) -> str:
    return line_parking_spaces(lot)


def _line_public_uri(path: str) -> str:
    return line_public_uri(settings.line_public_web_url, path)


def _line_booking_path(
    shop_id: int,
    line_token: str = "",
    name: str = "",
    district: str = "",
    mrt: str = "",
    avg_price: str = "",
) -> str:
    return line_booking_path(shop_id, line_token, name, district, mrt, avg_price)


def _line_google_maps_uri(name: str, address: str) -> str:
    return line_google_maps_uri(name, address)


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
        "international": "異國料理",
        "vegetarian": "蔬食",
        "cafe": "咖啡甜點",
    }.get(slug or "", "")


def _dedupe_text(items: list[str]) -> list[str]:
    return dedupe_text(items)


def _truncate_words(text: str, max_length: int) -> str:
    return truncate_words(text, max_length)


def _line_shell(title: str, body: str) -> str:
    return line_shell(title, body)


def _line_html_page(title: str, message: str, links: list[tuple[str, str]]) -> str:
    return line_html_page(title, message, links)


def _html_escape(value: str) -> str:
    return html_escape(value)


@app.delete("/api/ai/session/{session_id}")
async def clear_chat_session(session_id: str):
    """清除 Redis 對話歷史。"""
    session_store.clear_session(session_id)
    return {"success": True, "session_id": session_id}
