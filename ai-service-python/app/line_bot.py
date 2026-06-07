"""LINE Messaging API helpers for ByteBites AI."""
import base64
import hashlib
import hmac
import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("bytebites.line")

LINE_REPLY_ENDPOINT = "https://api.line.me/v2/bot/message/reply"
LINE_PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"
LINE_LOADING_ENDPOINT = "https://api.line.me/v2/bot/chat/loading/start"
MAX_LINE_MESSAGES = 5
MAX_FLEX_CARDS = 3
LINE_PHOTO_VERSION = "20260607b"

_SHOP_MEDIA_CACHE: dict[str, Any] | None = None
_COVER_INDEX_OVERRIDES: dict[int, int] = {
    10100: 0,
    10104: 0,
    10108: 2,
    10111: 2,
    10112: 0,
    10115: 1,
    10127: 1,
    10131: 3,
    10147: 3,
    10149: 2,
    10152: 0,
    10158: 4,
    10169: 3,
    10171: 4,
}


def verify_line_signature(
    body_bytes: bytes,
    signature: str | None,
    channel_secret: str,
    enabled: bool = True,
) -> bool:
    if not enabled:
        return True
    secret = (channel_secret or "").strip()
    if not secret or secret.startswith("your_") or not signature:
        return False

    digest = hmac.new(
        secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def build_text_message(text: str) -> dict[str, Any]:
    return {
        "type": "text",
        "text": (text or "目前沒有可回覆的內容。")[:5000],
    }


def build_line_flex_message(
    shops: list[dict],
    recommended_shop_ids: list[int] | None,
    answer: str,
    public_web_url: str,
) -> dict[str, Any]:
    ordered = _select_recommended_shops(shops, recommended_shop_ids)
    bubbles = [
        _build_shop_bubble(shop, rank=index + 1, public_web_url=public_web_url, answer=answer)
        for index, shop in enumerate(ordered[:MAX_FLEX_CARDS])
    ]
    names = "、".join(str(shop.get("name") or "餐廳") for shop in ordered[:MAX_FLEX_CARDS])
    alt_text = f"ByteBites 推薦：{names}" if names else "ByteBites 餐廳推薦"

    messages: list[dict[str, Any]] = []
    messages.append(build_text_message(_line_recommendation_intro(len(bubbles))))
    if bubbles:
        messages.append(
            {
                "type": "flex",
                "altText": alt_text[:400],
                "contents": {
                    "type": "carousel",
                    "contents": bubbles,
                },
            }
        )
    return messages[0] if len(messages) == 1 else {"type": "_bundle", "messages": messages}


async def reply_messages(
    reply_token: str,
    messages: list[dict[str, Any]],
    channel_access_token: str,
    enabled: bool,
) -> dict[str, Any]:
    normalized = _normalize_messages(messages)
    if not normalized:
        return {"ok": True, "skipped": True, "reason": "No LINE messages"}

    token = (channel_access_token or "").strip()
    if not enabled or not token or token.startswith("your_"):
        return {
            "ok": True,
            "skipped": True,
            "reason": "LINE reply disabled or channel access token missing",
            "messages_preview": normalized,
        }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            LINE_REPLY_ENDPOINT,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "replyToken": reply_token,
                "messages": normalized[:MAX_LINE_MESSAGES],
            },
        )

    if response.status_code >= 400:
        logger.warning("line_reply_failed status=%s body=%s", response.status_code, response.text)
        return {
            "ok": False,
            "status_code": response.status_code,
            "response_text": response.text,
        }
    return {"ok": True, "status_code": response.status_code}


async def push_messages(
    user_id: str,
    messages: list[dict[str, Any]],
    channel_access_token: str,
    enabled: bool,
) -> dict[str, Any]:
    normalized_user_id = (user_id or "").strip()
    normalized = _normalize_messages(messages)
    if not normalized_user_id:
        return {"ok": False, "skipped": True, "reason": "No LINE user id"}
    if not normalized:
        return {"ok": True, "skipped": True, "reason": "No LINE messages"}

    token = (channel_access_token or "").strip()
    if not enabled or not token or token.startswith("your_"):
        return {
            "ok": True,
            "skipped": True,
            "reason": "LINE push disabled or channel access token missing",
            "messages_preview": normalized,
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                LINE_PUSH_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "to": normalized_user_id,
                    "messages": normalized[:MAX_LINE_MESSAGES],
                },
            )
    except Exception as exc:
        logger.warning("line_push_request_failed error=%s", exc)
        return {"ok": False, "skipped": True, "reason": str(exc)}

    if response.status_code >= 400:
        logger.warning("line_push_failed status=%s body=%s", response.status_code, response.text)
        return {
            "ok": False,
            "status_code": response.status_code,
            "response_text": response.text,
        }
    return {"ok": True, "status_code": response.status_code}


async def show_loading_animation(
    user_id: str | None,
    channel_access_token: str,
    enabled: bool,
    loading_seconds: int = 20,
) -> dict[str, Any]:
    normalized_user_id = (user_id or "").strip()
    token = (channel_access_token or "").strip()
    if not normalized_user_id:
        return {"ok": True, "skipped": True, "reason": "No LINE user id"}
    if not enabled or not token or token.startswith("your_"):
        return {"ok": True, "skipped": True, "reason": "LINE reply disabled or token missing"}

    seconds = min(60, max(5, int(loading_seconds)))
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                LINE_LOADING_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"chatId": normalized_user_id, "loadingSeconds": seconds},
            )
    except Exception as exc:
        logger.info("line_loading_failed error=%s", exc)
        return {"ok": False, "skipped": True, "reason": str(exc)}

    if response.status_code >= 400:
        return {"ok": False, "status_code": response.status_code, "response_text": response.text}
    return {"ok": True, "status_code": response.status_code, "loading_seconds": seconds}


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("type") == "_bundle":
            normalized.extend(_normalize_messages(message.get("messages") or []))
            continue
        if message.get("type") in {"text", "flex"}:
            normalized.append(message)
    return normalized[:MAX_LINE_MESSAGES]


def _select_recommended_shops(
    shops: list[dict],
    recommended_shop_ids: list[int] | None,
) -> list[dict]:
    def dedupe_brand(items: list[dict]) -> list[dict]:
        selected: list[dict] = []
        seen: set[str] = set()
        for shop in items:
            key = _brand_key(str(shop.get("name") or ""))
            if key in seen:
                continue
            seen.add(key)
            selected.append(shop)
        return selected

    if not recommended_shop_ids:
        return dedupe_brand(shops)[:MAX_FLEX_CARDS]
    by_id = {int(shop.get("shop_id")): shop for shop in shops if shop.get("shop_id") is not None}
    selected = dedupe_brand([by_id[int(shop_id)] for shop_id in recommended_shop_ids if int(shop_id) in by_id])
    return selected or dedupe_brand(shops)[:MAX_FLEX_CARDS]


def best_shop_photo_url(shop_id: int) -> str | None:
    return _best_shop_photo(shop_id)


def _build_shop_bubble(shop: dict, rank: int, public_web_url: str, answer: str) -> dict[str, Any]:
    shop_id = int(shop.get("shop_id") or 0)
    name = str(shop.get("name") or "未命名餐廳")
    district = str(shop.get("district") or "")
    mrt = str(shop.get("mrt_station") or "")
    price = str(shop.get("price_per_person") or (f"NT$ {shop.get('avg_price')}" if shop.get("avg_price") else "價位未標示"))
    summary = _recommendation_reason_for_shop(shop, answer)
    decision_points = _line_decision_points(shop)
    match_chips = _line_match_chips(shop)
    detail_uri = _web_uri(public_web_url, f"/line/shop/{shop_id}") if shop_id else _web_uri(public_web_url, "/line/shop")
    reserve_uri = _web_uri(public_web_url, f"/line/book/{shop_id}") if shop_id else detail_uri
    image_uri = _shop_image_uri(shop_id, public_web_url)

    body_contents: list[dict[str, Any]] = [
        {"type": "text", "text": f"BYTEBITES PICK {rank}", "size": "xs", "color": "#16833a", "weight": "bold"},
        {"type": "text", "text": _truncate(name, 46), "size": "lg", "weight": "bold", "wrap": True},
        {
            "type": "text",
            "text": " · ".join(part for part in [district, f"捷運{mrt}" if mrt else ""] if part) or "台北餐廳",
            "size": "sm",
            "color": "#666666",
            "wrap": True,
            "margin": "sm",
        },
    ]

    if match_chips:
        body_contents.append(
            {
                "type": "box",
                "layout": "horizontal",
                "spacing": "xs",
                "margin": "md",
                "contents": [_line_chip(label) for label in match_chips[:3]],
            }
        )

    body_contents.extend(
        [
            {"type": "separator", "margin": "md"},
            {"type": "text", "text": "為什麼適合你", "size": "sm", "weight": "bold", "margin": "md"},
            {"type": "text", "text": _truncate(summary, 120), "size": "sm", "color": "#333333", "wrap": True},
        ]
    )

    if decision_points:
        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "xs",
                "margin": "md",
                "contents": [_line_decision_row(point) for point in decision_points[:2]],
            }
        )

    body_contents.append(
        {
            "type": "text",
            "text": f"{price}。完整評論、電話與營業時間在詳情頁。",
            "size": "xs",
            "color": "#777777",
            "wrap": True,
            "margin": "md",
        }
    )

    bubble: dict[str, Any] = {
        "type": "bubble",
        "size": "mega",
        "styles": {
            "footer": {"separator": True},
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
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
                    "action": {"type": "uri", "label": "看完整分析", "uri": detail_uri},
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {"type": "uri", "label": "填日期人數", "uri": reserve_uri},
                },
            ],
        },
    }
    if image_uri:
        bubble["hero"] = {
            "type": "image",
            "url": image_uri,
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
            "action": {"type": "uri", "uri": detail_uri},
        }
    return bubble


def _line_chip(label: str) -> dict[str, Any]:
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": "#e9f6ee",
        "cornerRadius": "md",
        "paddingAll": "6px",
        "contents": [
            {
                "type": "text",
                "text": _truncate(label, 12),
                "size": "xs",
                "color": "#16833a",
                "weight": "bold",
                "align": "center",
                "wrap": True,
            }
        ],
    }


def _line_decision_row(text: str) -> dict[str, Any]:
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
            {"type": "text", "text": "✓", "size": "xs", "color": "#16833a", "flex": 0},
            {
                "type": "text",
                "text": _truncate(text, 52),
                "size": "xs",
                "color": "#444444",
                "wrap": True,
                "flex": 1,
            },
        ],
    }


def _line_match_chips(shop: dict) -> list[str]:
    chips: list[str] = []
    district = str(shop.get("district") or "").strip()
    mrt = str(shop.get("mrt_station") or "").strip()
    category = _category_label(str(shop.get("category") or shop.get("category_slug") or "").strip())
    avg_price = _numeric_price(shop)

    if district:
        chips.append(district)
    if category:
        chips.append(category)
    if avg_price >= 1000:
        chips.append("高級路線")
    elif avg_price and avg_price <= 500:
        chips.append("好入手")
    if mrt and len(chips) < 3:
        chips.append(f"{mrt}旁")
    return _dedupe_labels(chips)


def _line_decision_points(shop: dict) -> list[str]:
    dishes = [str(dish).strip() for dish in (shop.get("signature_dishes") or []) if str(dish).strip()]
    tags = [str(tag).strip() for tag in (shop.get("atmosphere_tags") or []) if str(tag).strip()]
    points: list[str] = []

    if dishes:
        points.append("招牌重點：" + "、".join(dishes[:2]))
    if tags:
        points.append("用餐情境：" + "、".join(tags[:2]))

    rating = shop.get("rating")
    comments = shop.get("comments") or shop.get("review_count")
    if rating and comments:
        points.append(f"Google {rating} 分，累積 {comments} 則評論")
    elif rating:
        points.append(f"Google {rating} 分，可先看詳情比較評論")

    return _dedupe_labels(points)


def _numeric_price(shop: dict) -> int:
    for key in ("avg_price", "price"):
        value = shop.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    text = str(shop.get("price_per_person") or "")
    match = re.search(r"\d[\d,]*", text)
    if not match:
        return 0
    return int(match.group(0).replace(",", ""))


def _dedupe_labels(labels: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for label in labels:
        normalized = _plain_line_text(label)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _shop_image_uri(shop_id: int, public_web_url: str) -> str | None:
    if not shop_id or not public_web_url.startswith("https://"):
        return None
    raw_url = _best_shop_photo(shop_id)
    if not raw_url:
        return None
    return _web_uri(public_web_url, f"/line/photo/{shop_id}?v={LINE_PHOTO_VERSION}")


def _best_shop_photo(shop_id: int) -> str | None:
    payload = _load_shop_media()
    shop = (payload.get("shops") or {}).get(str(shop_id))
    if not isinstance(shop, dict):
        return None
    urls = _dedupe_urls([url for url in [*(shop.get("galleryUrls") or []), *(shop.get("photoUrls") or [])] if url])
    override_index = _COVER_INDEX_OVERRIDES.get(shop_id)
    if override_index is not None and override_index < len(urls):
        return urls[override_index]
    cover_url = shop.get("coverUrl")
    if isinstance(cover_url, str) and cover_url.strip():
        return cover_url.strip()
    if not urls:
        return None
    return sorted(urls, key=_photo_score, reverse=True)[0]


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        normalized = str(url).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _photo_score(url: str) -> int:
    score = 0
    size = re.search(r"=w(\d+)-h(\d+)-", url)
    if size:
        width = int(size.group(1))
        height = int(size.group(2))
        if width > height:
            score += 6
        if width / max(height, 1) >= 1.3:
            score += 4
        if width >= 600:
            score += 2
    return score


def _load_shop_media() -> dict[str, Any]:
    global _SHOP_MEDIA_CACHE
    if _SHOP_MEDIA_CACHE is not None:
        return _SHOP_MEDIA_CACHE
    path = Path(__file__).resolve().parents[2] / "web" / "data" / "shop-media.json"
    try:
        _SHOP_MEDIA_CACHE = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _SHOP_MEDIA_CACHE = {}
    return _SHOP_MEDIA_CACHE


def _web_uri(public_web_url: str, path: str) -> str:
    base = (public_web_url or "http://localhost:3000").rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def _compact_answer_for_line(answer: str) -> str:
    kept: list[str] = []
    for raw_line in (answer or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "|" in line:
            continue
        if set(line.replace(" ", "")) <= {"-", ":"}:
            continue
        kept.append(line)
    cleaned = _plain_line_text(" ".join(kept))
    if not cleaned:
        return "我先幫你整理 3 間符合需求的餐廳，請左右滑動查看卡片。"
    return _truncate(cleaned, 180)


def _line_recommendation_intro(count: int) -> str:
    if count <= 0:
        return "我需要再多一點條件，才能幫你推薦餐廳。"
    return f"我先幫你整理 {count} 間符合需求的餐廳。請左右滑動查看卡片，點「查看詳情」看店家資訊，點「直接訂位」填寫人數與時間。"


def _recommendation_reason_for_shop(shop: dict, answer: str) -> str:
    summary = str(shop.get("ai_summary") or "").strip()
    if summary:
        return _truncate(_plain_line_text(summary), 140)

    tags = [str(tag) for tag in (shop.get("atmosphere_tags") or [])[:2]]
    dishes = [str(dish) for dish in (shop.get("signature_dishes") or [])[:2]]
    price = str(shop.get("price_per_person") or "").strip()
    highlights = [*dishes, *tags]
    if dishes and tags:
        return _truncate(f"主打{ '、'.join(dishes[:2]) }，適合{ '、'.join(tags[:2]) }。", 140)
    if dishes:
        return _truncate(f"招牌包含{ '、'.join(dishes[:3]) }，可先看詳情確認菜單與評價。", 140)
    if tags:
        return _truncate(f"評論標籤偏向{ '、'.join(tags[:2]) }，適合先看詳情比較用餐情境。", 140)
    if price:
        return _truncate(f"人均約{price}，適合先看詳情確認菜色、評論與用餐氛圍。", 140)
    if highlights:
        return _truncate("符合本次需求，亮點包含" + "、".join(highlights[:3]) + "。", 140)

    district = str(shop.get("district") or "").strip()
    category = _category_label(str(shop.get("category") or "").strip())
    return _truncate(f"{district or '台北'}{category or '餐廳'}候選，詳情頁會整理菜色、電話、評論與訂位資訊。", 140)


def _category_label(category: str) -> str:
    return {
        "hotpot": "火鍋",
        "yakiniku": "燒肉",
        "izakaya": "居酒屋",
        "japanese": "日式料理",
        "american": "美式餐廳",
        "euro": "義法料理",
        "chinese": "中式餐廳",
        "korean": "韓式餐廳",
        "vegetarian": "蔬食餐廳",
        "fine-dining": "高級餐廳",
        "cafe": "咖啡甜點",
    }.get(category, category)


def _brand_key(name: str) -> str:
    normalized = name.strip()
    for sep in ("｜", "|", " ", "　", "-", "－", "("):
        if sep in normalized:
            prefix = normalized.split(sep, 1)[0].strip()
            if prefix and prefix not in {"店家", "餐廳"}:
                normalized = prefix
            break
    return normalized.strip().lower() or name.strip().lower()


def _plain_line_text(text: str) -> str:
    cleaned = str(text or "").replace("**", "").replace("__", "")
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max(0, max_length - 1)].rstrip() + "…"
