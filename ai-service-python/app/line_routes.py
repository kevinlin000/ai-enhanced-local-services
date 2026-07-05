"""LINE webhook、內部通知與 LINE 內嵌 HTML 頁（自 main.py 機械搬出，行為不變）。"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import httpx
import json
import re

from fastapi import APIRouter

from app import (
    session_store,
)
from app.agent import (
    _agent_query_context_labels,
    _booking_cancel_confirmation_intent,
    _booking_cancel_intent,
    _booking_code_from_text,
    _booking_confirm_intent,
    _booking_draft_edit_intent,
    _booking_intent,
    _booking_selection_intent,
    _booking_status_intent,
    _build_agent_search_result,
    _complete_fresh_restaurant_query,
    _dedupe_shops_by_brand,
    _exact_shop_matches_for_keyword,
    _explicit_same_day_booking_request,
    _line_booking_prefill_from_text,
    _line_card_request_intent,
    _line_media_shop,
    _line_merge_followup_query,
    _line_more_recommendation_intent,
    _line_should_force_recommendation_cards,
    _payment_intent,
    _query_is_clarification_followup,
    _recommendation_advice_answer,
    _recommendation_advice_intent,
    _recommendation_followup_reference,
    _recommended_shop_from_text,
    _restaurant_clarification_text,
    _restaurant_need_clarification,
    _run_agent_turn,
    _same_day_booking_policy_answer,
    _same_day_datetime_request,
    _search_scope_note,
    _selection_index_from_text,
    _shop_brand_key,
    _shop_id,
    _shops_for_ids,
)
from app.booking_draft import (
    booking_draft_missing as _booking_draft_missing,
    booking_draft_payload as _booking_draft_payload,
    compact_booking_prefill as _compact_booking_prefill,
    merge_booking_prefill as _merge_booking_prefill,
)
from app.config import (
    logger,
    settings,
)
from app.guardrail import (
    GuardrailViolation,
    check_input,
)
from app.line_auth import (
    resolve_line_context,
)
from app.line_bot import (
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
from app.ranking import (
    TYPE_ID_TO_CATEGORY,
    _extract_query_constraints,
    _parse_json_list,
    _specific_shop_keyword,
    taipei_today,
)
from app.retrieval import (
    _LINE_SHOP_NAME_FALLBACKS,
    _fetch_java_ai_metadata,
    _fetch_java_shop,
    _semantic_hits,
)
from datetime import (
    date as date_cls,
    datetime,
    timedelta,
)
from fastapi import (
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import (
    HTMLResponse,
)
from urllib.parse import (
    parse_qs,
    quote_plus,
)
from zoneinfo import (
    ZoneInfo,
)

router = APIRouter()

LINE_RECOMMENDATION_TTL_SECONDS = 1800


LINE_LOCATION_TTL_SECONDS = 1800


LINE_BOOKING_TTL_SECONDS = 1800


LINE_ACTION_TOKEN_TTL_SECONDS = 60 * 60 * 24


_LINE_PROFILE_CACHE: dict[str, str] = {}


_PARKING_RESERVATIONS: dict[str, dict] = {}


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


def _line_context(lt: str = "", line_user_id: str = "") -> tuple[str, str]:
    return resolve_line_context(
        lt,
        line_user_id,
        action_secret=_line_action_secret(),
        legacy_channel_secret=settings.line_channel_secret,
        token_for_user=_line_token_for_user,
    )


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


def _exact_shop_matches(query: str, shops: list[dict]) -> list[dict]:
    return _exact_shop_matches_for_keyword(_specific_shop_keyword(query), shops)


@router.get("/api/line/webhook")
@router.get("/line/webhook")
async def line_webhook_check():
    return {
        "status": "ok",
        "service": "bytebites-line-bot",
        "reply_enabled": settings.line_reply_enabled,
    }


@router.post("/api/line/webhook")
@router.post("/line/webhook")
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


@router.post("/internal/line/availability-released")
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


@router.post("/internal/line/booking-updated")
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


@router.post("/internal/line/booking-incident")
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


@router.post("/internal/line/booking-incident-proposal")
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


@router.post("/internal/line/refund-operations-digest")
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


@router.post("/internal/line/parking-reminder")
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


@router.get("/line/photo/{shop_id}")
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


@router.get("/line/shop/{shop_id}", response_class=HTMLResponse)
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


@router.get("/line/book/{shop_id}", response_class=HTMLResponse)
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


@router.get("/line/book/{shop_id}/confirm", response_class=HTMLResponse)
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


@router.get("/line/book/{shop_id}/pay", response_class=HTMLResponse)
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


@router.post("/line/book/{shop_id}/pay/confirm", response_class=HTMLResponse)
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


@router.get("/line/book/{shop_id}/status", response_class=HTMLResponse)
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


@router.get("/line/book/{shop_id}/incident-proposal/accept", response_class=HTMLResponse)
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


@router.get("/line/book/{shop_id}/incident-proposal/decline", response_class=HTMLResponse)
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


@router.get("/line/book/{shop_id}/parking", response_class=HTMLResponse)
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


@router.get("/line/book/{shop_id}/parking-reserve", response_class=HTMLResponse)
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


@router.get("/line/book/{shop_id}/cancel", response_class=HTMLResponse)
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


@router.get("/line/my-bookings", response_class=HTMLResponse)
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


@router.get("/line/availability/watch", response_class=HTMLResponse)
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


@router.get("/line/notifications", response_class=HTMLResponse)
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
