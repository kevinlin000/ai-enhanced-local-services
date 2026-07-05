"""Agent 迴圈、工具呼叫與推薦決策（自 main.py 機械搬出，行為不變）。"""
from __future__ import annotations

import httpx
import json
import re

from app import (
    session_store,
)
from app.booking_draft import (
    booking_draft_confirmation_answer as _booking_draft_confirmation_answer,
    booking_draft_payload as _booking_draft_payload,
    merge_booking_prefill as _merge_booking_prefill,
)
from app.config import (
    generate,
    logger,
    settings,
)
from app.guardrail import (
    filter_output,
)
from app.line_booking_text import (
    line_booking_prefill_from_text,
    zh_number_to_int,
)
from app.ranking import (
    CONTEXT_INTENT_RULES,
    TOOLS,
    _booking_shop_keyword,
    _context_intent_bonus,
    _district_matches,
    _extract_query_constraints,
    _has_steak_semantics,
    _is_burger_hit,
    _is_restaurant_clarification_response,
    _normalized_name,
    _parse_json_list,
    _payload_text,
    _private_ai_offer_is_off_peak_time,
    _query_requests_steak,
    _recommended_shop_name_score,
    _restaurant_clarification_gaps,
    _search_category_match,
    _semantic_category_slug,
    _specific_shop_keyword,
    _station_proximity_score,
    taipei_today,
)
from app.retrieval import (
    _agent_java_auth_headers,
    _fetch_java_ai_metadata,
    _semantic_hits,
    _shop_has_rich_context,
)
from dataclasses import (
    dataclass,
    field,
)
from datetime import (
    date as date_cls,
    datetime,
    timedelta,
)
from fastapi import (
    HTTPException,
)
from google.genai import (
    types,
)
from pathlib import (
    Path,
)
from pydantic import (
    BaseModel,
    Field,
)
from typing import (
    AsyncIterator,
)
from urllib.parse import (
    quote_plus,
)

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


def _line_booking_prefill_from_text(text: str) -> dict:
    return line_booking_prefill_from_text(text, today=taipei_today())


_LINE_MEDIA_CACHE: dict | None = None


_LINE_MEDIA_ALIASES: dict[int, int] = {
    10009: 10550,
}


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


def _line_card_request_intent(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    return bool(normalized) and any(
        phrase in normalized
        for phrase in ("圖卡", "卡片", "給我卡", "給我圖", "用卡片", "出卡", "flex")
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
