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

from app.config import (  # noqa: F401 — re-export 保持 app.main.* 相容
    Settings,
    settings,
    _agent_auth_token,
    ai_requests,
    ai_latency,
    ai_tokens,
    call_llm,
    generate,
    get_gemini,
    get_qdrant,
    logger,
)
from app.retrieval import (  # noqa: F401 — re-export 保持 app.main.* 相容
    LEGACY_SEED_SHOP_IDS,
    PREMIUM_HOTPOT_SUPPLEMENT_IDS,
    _LINE_SHOP_NAME_FALLBACKS,
    _QUERY_EMBEDDING_CACHE,
    _QUERY_EMBEDDING_CACHE_MAX,
    _agent_java_auth_headers,
    _burger_supplements,
    _dedupe_search_hits,
    _fetch_all_shops_fallback,
    _fetch_hot_seat_vouchers,
    _fetch_java_ai_metadata,
    _fetch_java_shop,
    _fetch_java_shop_by_fallback_name,
    _is_legacy_seed_hit,
    _java_shop_name_supplements,
    _prefer_rich_hits,
    _premium_hotpot_supplements,
    _query_embedding,
    _semantic_hits,
    _shop_has_rich_context,
    _steak_supplements,
)
from app.agent import (  # noqa: F401 — re-export 保持 app.main.* 相容
    AGENT_SYSTEM_PROMPT,
    AgentRecommendationDecision,
    AgentToolState,
    TOOL_DISPATCH,
    ToolGuardResult,
    _LINE_MEDIA_ALIASES,
    _LINE_MEDIA_CACHE,
    _adjust_selected_ids_for_private_memory,
    _after_tool_call,
    _agent_booking_action_from_history,
    _agent_booking_followup_from_history,
    _agent_booking_idempotency_key,
    _agent_booking_status_for_query,
    _agent_comparison_best_for,
    _agent_comparison_booking_status,
    _agent_comparison_feature,
    _agent_comparison_meta,
    _agent_comparison_rows,
    _agent_concierge_narrative,
    _agent_constraint_bullets,
    _agent_context_best_for_label,
    _agent_display_shop_name,
    _agent_distinct_context_label,
    _agent_exact_booking_from_query,
    _agent_exact_shop_from_query,
    _agent_initial_backup_viable,
    _agent_manifest_price_label,
    _agent_missing_booking_fields,
    _agent_more_recommendations_from_history,
    _agent_price_label,
    _agent_query_basis_label,
    _agent_query_context_labels,
    _agent_recommendation_advice_from_history,
    _agent_recommendation_cta,
    _agent_response_contract,
    _agent_shop_best_for,
    _agent_shop_feature,
    _agent_shop_markdown_line,
    _agent_shop_match_reason,
    _agent_should_force_search,
    _agent_sorting_label,
    _agent_story_frame,
    _agent_system_prompt,
    _annotate_private_ai_offers,
    _annotate_private_memory,
    _apply_hard_constraints_to_recommendations,
    _apply_private_memory_to_recommendations,
    _before_tool_call,
    _booking_branch_clarification_from_search,
    _booking_branch_clarification_from_tool_call,
    _booking_cancel_confirmation_intent,
    _booking_cancel_confirmation_mismatch,
    _booking_cancel_intent,
    _booking_cancel_not_allowed_narrative,
    _booking_cancel_prompt,
    _booking_code_from_text,
    _booking_confirm_intent,
    _booking_confirmation_narrative,
    _booking_draft_edit_intent,
    _booking_duplicate_narrative,
    _booking_followup_cta_from_context,
    _booking_incident_action,
    _booking_incident_intent,
    _booking_incident_type_from_text,
    _booking_intent,
    _booking_key,
    _booking_key_from_tool_args,
    _booking_payment_not_needed_narrative,
    _booking_reschedule_action,
    _booking_reschedule_intent,
    _booking_selection_intent,
    _booking_status_intent,
    _booking_status_narrative,
    _booking_table_type_from_text,
    _booking_transaction_after_cancel,
    _booking_transaction_after_incident,
    _booking_transaction_after_payment,
    _booking_transaction_after_reschedule,
    _branch_clarification_text,
    _brand_matches_query,
    _budget_summary_for_query,
    _budget_summary_for_shops,
    _build_agent_recommendation_decision,
    _build_agent_search_result,
    _build_booking_transaction,
    _category_label_for_constraints,
    _compact_tool_context,
    _complete_fresh_restaurant_query,
    _constraint_strategy_line,
    _contextual_shop_choice_score,
    _decision_payload,
    _dedupe_shops_by_brand,
    _delay_minutes_from_text,
    _dish_has_meat,
    _dish_has_obvious_shellfish,
    _effective_agent_query,
    _enrich_agent_search_result,
    _exact_shop_matches_for_keyword,
    _expand_initial_recommendations,
    _explicit_price_label_from_text,
    _explicit_same_day_booking_request,
    _fallback_agent_decision,
    _fetch_private_ai_offers,
    _fetch_private_dining_memory,
    _find_duplicate_booking_transaction,
    _find_shop_from_tool_result,
    _fresh_restaurant_query_signal_count,
    _fresh_restaurant_recommendation_request,
    _hard_constraint_candidate_ids,
    _history_to_contents,
    _hydrate_agent_search_shops,
    _last_clarified_restaurant_query,
    _latest_booking_context_kind,
    _latest_booking_draft,
    _latest_booking_transaction,
    _latest_recommendation_context,
    _latest_successful_booking_transaction,
    _line_booking_prefill_from_text,
    _line_card_has_rich_context,
    _line_card_request_intent,
    _line_media_payload,
    _line_media_shop,
    _line_merge_followup_query,
    _line_more_recommendation_intent,
    _line_should_force_recommendation_cards,
    _negative_selection_intent,
    _parse_agent_decision,
    _payment_intent,
    _pending_booking_expired,
    _prioritize_contextual_recommended_ids,
    _private_ai_offer_trigger,
    _private_memory_avoid_shop_ids,
    _private_memory_by_shop,
    _query_budget_range,
    _query_has_executive_context,
    _query_has_meat_lovers,
    _query_has_shellfish_allergy,
    _query_is_clarification_followup,
    _query_mentions_unique_branch,
    _recommendation_advice_answer,
    _recommendation_advice_intent,
    _recommendation_context_for_selection,
    _recommendation_context_from_tool_result,
    _recommendation_dimension,
    _recommendation_followup_reference,
    _recommended_shop_from_text,
    _restaurant_clarification_known_context,
    _restaurant_clarification_text,
    _restaurant_need_clarification,
    _run_agent_turn,
    _run_agent_turn_stream,
    _same_day_booking_policy_answer,
    _same_day_datetime_request,
    _search_scope_note,
    _selected_agent_response_shops,
    _selection_index_from_text,
    _shop_advice_text,
    _shop_branch_label,
    _shop_brand_key,
    _shop_budget_text,
    _shop_concierge_fit,
    _shop_dimension_score,
    _shop_id,
    _shop_matches_budget_ceiling,
    _shop_menu_dishes_for_query,
    _shop_menu_items,
    _shop_menu_suggestion,
    _shop_price_bounds,
    _shop_role_for_advice,
    _shop_watchout_text,
    _shops_for_ids,
    _short_agent_text,
    _should_expand_initial_recommendations,
    _tool_result_summary,
    _validate_agent_decision,
    _zh_number_to_int,
    tool_cancel_booking,
    tool_create_booking,
    tool_create_booking_incident,
    tool_create_hot_seat_order,
    tool_pay_booking_with_test_card,
    tool_search_by_mrt,
    tool_semantic_search,
    tool_update_booking,
)
from app.line_routes import (  # noqa: F401 — re-export 保持 app.main.* 相容
    LINE_ACTION_TOKEN_TTL_SECONDS,
    LINE_BOOKING_TTL_SECONDS,
    LINE_LOCATION_TTL_SECONDS,
    LINE_RECOMMENDATION_TTL_SECONDS,
    _LINE_PAYMENT_METHOD_LABELS,
    _LINE_PROFILE_CACHE,
    _PARKING_RESERVATIONS,
    _build_line_agent_recommendation_messages,
    _build_line_booking_action,
    _build_line_booking_draft_confirmation,
    _build_line_booking_draft_update,
    _build_line_booking_followup,
    _build_line_card_request,
    _build_line_cards_for_query,
    _build_line_clarification_if_needed,
    _build_line_contextual_followup,
    _build_line_exact_booking_request,
    _build_line_fallback_recommendation_cards,
    _build_line_more_recommendations,
    _build_line_named_selection_cards,
    _build_line_recommendation_advice,
    _build_line_reply_messages,
    _cancel_line_booking,
    _category_from_shop,
    _clear_line_booking_draft_state,
    _clear_line_recommendation_state,
    _create_line_availability_watch,
    _dedupe_text,
    _demo_story_recommended_shop_ids,
    _exact_shop_matches,
    _fetch_java_booking_policy,
    _fetch_java_nearby_parking,
    _fetch_line_booking,
    _fetch_line_bookings,
    _fetch_line_display_name,
    _fetch_line_notifications,
    _html_escape,
    _line_action_secret,
    _line_adjustment_intent,
    _line_auth_required_page,
    _line_availability_flex_message,
    _line_availability_watch_created_flex,
    _line_booking_deposit_note,
    _line_booking_deposit_text,
    _line_booking_draft_flex_message,
    _line_booking_draft_state_key,
    _line_booking_flex_message,
    _line_booking_flex_row,
    _line_booking_followup_intent,
    _line_booking_incident_flex_message,
    _line_booking_incident_proposal_flex_message,
    _line_booking_path,
    _line_booking_payment_page,
    _line_booking_result_page,
    _line_booking_state_key,
    _line_booking_status_label,
    _line_bullet_html,
    _line_business_hours,
    _line_cancel_context_intent,
    _line_context,
    _line_deposit_summary,
    _line_detail_image_uri,
    _line_detail_summary,
    _line_display_rating,
    _line_effective_text_with_location,
    _line_google_maps_uri,
    _line_hours_html,
    _line_html_page,
    _line_incident_proposal_html,
    _line_incident_proposal_response_page,
    _line_location_state_key,
    _line_location_text,
    _line_parking_distance,
    _line_parking_html,
    _line_parking_preference_page,
    _line_parking_reminder_flex_message,
    _line_parking_reservation_confirm_page,
    _line_parking_reservation_flex_message,
    _line_parking_reservation_success_page,
    _line_parking_spaces,
    _line_parse_hours,
    _line_payment_method_from_request,
    _line_payment_method_label,
    _line_photo_candidates,
    _line_pills_html,
    _line_plain_text,
    _line_public_uri,
    _line_recommendation_basis,
    _line_recommendation_shop_snapshots,
    _line_recommendation_state_key,
    _line_refund_operations_digest_flex_message,
    _line_refund_reason_label,
    _line_report_int,
    _line_review_card_html,
    _line_review_groups,
    _line_review_html,
    _line_review_rating,
    _line_scope_expansion_intro,
    _line_scope_expansion_intro_from_note,
    _line_selection_token,
    _line_shell,
    _line_shop_fallback_from_media,
    _line_shop_fallback_from_query,
    _line_shop_matches_selection,
    _line_shop_minimal_fallback,
    _line_should_reset_agent_context_for_query,
    _line_should_start_background_recommendation,
    _line_status_intent,
    _line_text_has_explicit_location,
    _line_token_for_user,
    _load_line_booking_draft_state,
    _load_line_booking_state,
    _load_line_location_state,
    _load_line_recommendation_state,
    _mock_parking_reservation,
    _parking_hold_until_label,
    _parking_lot_after_reservation,
    _parking_reservation_key,
    _pay_line_booking,
    _push_line_availability_watch_created,
    _push_line_parking_reservation,
    _reserve_line_booking,
    _reset_line_agent_context_for_fresh_query,
    _respond_line_incident_proposal,
    _run_line_background_recommendation,
    _save_line_booking_draft_state,
    _save_line_booking_state,
    _save_line_location_state,
    _save_line_recommendation_state,
    _start_line_background_recommendation,
    _truncate_words,
    _update_line_parking_preference,
    _validate_line_booking,
    _verify_internal_line_secret,
    internal_line_availability_released,
    internal_line_booking_incident,
    internal_line_booking_incident_proposal,
    internal_line_booking_updated,
    internal_line_parking_reminder,
    internal_line_refund_operations_digest,
    line_booking_cancel,
    line_booking_confirm,
    line_booking_entry,
    line_booking_incident_proposal_accept,
    line_booking_incident_proposal_decline,
    line_booking_parking_preference,
    line_booking_parking_reserve,
    line_booking_pay,
    line_booking_pay_confirm,
    line_booking_status,
    line_create_availability_watch,
    line_my_bookings,
    line_notifications,
    line_shop_detail,
    line_shop_photo,
    line_webhook,
    line_webhook_check,
    router as _line_router,
)










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


app = FastAPI(title="ByteBites AI Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(_line_router)








def _decode_urlsafe(value: str) -> bytes:
    return decode_urlsafe(value)


def _line_user_id_from_token_with_secret(token: str, secret: bytes) -> str:
    return line_user_id_from_token_with_secret(token, secret)


def _line_user_id_from_token(token: str) -> str:
    return _line_user_id_from_token_with_secret(token, _line_action_secret())


def _line_user_id_from_unsigned_legacy_token(token: str) -> str:
    return line_user_id_from_unsigned_legacy_token(token)




































































































































































































































































































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




































































































@app.delete("/api/ai/session/{session_id}")
async def clear_chat_session(session_id: str):
    """清除 Redis 對話歷史。"""
    session_store.clear_session(session_id)
    return {"success": True, "session_id": session_id}
