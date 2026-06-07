"""LINE Messaging API helpers for ByteBites AI."""
import base64
import hashlib
import hmac
import json
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("bytebites.line")

LINE_REPLY_ENDPOINT = "https://api.line.me/v2/bot/message/reply"
LINE_LOADING_ENDPOINT = "https://api.line.me/v2/bot/chat/loading/start"
MAX_LINE_MESSAGES = 5
MAX_FLEX_CARDS = 3

_SHOP_MEDIA_CACHE: dict[str, Any] | None = None


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
    intro = _compact_answer_for_line(answer)
    if intro:
        messages.append(build_text_message(intro))
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
    if not recommended_shop_ids:
        return shops[:MAX_FLEX_CARDS]
    by_id = {int(shop.get("shop_id")): shop for shop in shops if shop.get("shop_id") is not None}
    selected = [by_id[int(shop_id)] for shop_id in recommended_shop_ids if int(shop_id) in by_id]
    return selected or shops[:MAX_FLEX_CARDS]


def best_shop_photo_url(shop_id: int) -> str | None:
    return _best_shop_photo(shop_id)


def _build_shop_bubble(shop: dict, rank: int, public_web_url: str, answer: str) -> dict[str, Any]:
    shop_id = int(shop.get("shop_id") or 0)
    name = str(shop.get("name") or "未命名餐廳")
    district = str(shop.get("district") or "")
    mrt = str(shop.get("mrt_station") or "")
    price = str(shop.get("price_per_person") or (f"NT$ {shop.get('avg_price')}" if shop.get("avg_price") else "價位未標示"))
    booking = str(shop.get("booking_difficulty") or "可查看訂位狀態")
    summary = _recommendation_reason_for_shop(shop, answer)
    tags = [str(tag) for tag in (shop.get("atmosphere_tags") or [])[:2]]
    dishes = [str(dish) for dish in (shop.get("signature_dishes") or [])[:2]]
    detail_uri = _web_uri(public_web_url, f"/line/shop/{shop_id}") if shop_id else _web_uri(public_web_url, "/line/shop")
    reserve_uri = _web_uri(public_web_url, f"/line/book/{shop_id}") if shop_id else detail_uri
    image_uri = _shop_image_uri(shop_id, public_web_url)

    body_contents: list[dict[str, Any]] = [
        {"type": "text", "text": f"No.{rank}", "size": "xs", "color": "#16833a", "weight": "bold"},
        {"type": "text", "text": _truncate(name, 46), "size": "lg", "weight": "bold", "wrap": True},
        {
            "type": "text",
            "text": " · ".join(part for part in [district, f"捷運{mrt}" if mrt else ""] if part) or "台北餐廳",
            "size": "sm",
            "color": "#666666",
            "wrap": True,
            "margin": "sm",
        },
        {"type": "text", "text": price, "size": "sm", "color": "#666666", "wrap": True},
        {"type": "text", "text": booking, "size": "sm", "color": "#666666", "wrap": True},
        {"type": "separator", "margin": "md"},
        {"type": "text", "text": "推薦理由", "size": "sm", "weight": "bold", "margin": "md"},
        {"type": "text", "text": _truncate(summary, 140), "size": "sm", "color": "#333333", "wrap": True},
    ]
    highlights = [*dishes, *tags]
    if highlights:
        body_contents.append(
            {
                "type": "text",
                "text": "亮點：" + "、".join(highlights[:3]),
                "size": "xs",
                "color": "#16833a",
                "wrap": True,
                "margin": "md",
            }
        )

    bubble: dict[str, Any] = {
        "type": "bubble",
        "size": "mega",
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
                    "action": {"type": "uri", "label": "查看詳情", "uri": detail_uri},
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {"type": "uri", "label": "直接訂位", "uri": reserve_uri},
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


def _shop_image_uri(shop_id: int, public_web_url: str) -> str | None:
    if not shop_id or not public_web_url.startswith("https://"):
        return None
    raw_url = _best_shop_photo(shop_id)
    if not raw_url:
        return None
    return _web_uri(public_web_url, f"/line/photo/{shop_id}")


def _best_shop_photo(shop_id: int) -> str | None:
    payload = _load_shop_media()
    shop = (payload.get("shops") or {}).get(str(shop_id))
    if not isinstance(shop, dict):
        return None
    urls = [url for url in [*(shop.get("galleryUrls") or []), *(shop.get("photoUrls") or [])] if url]
    return urls[0] if urls else None


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
    cleaned = " ".join(kept)
    if not cleaned:
        return "我先幫你整理 3 間符合需求的餐廳，請左右滑動查看卡片。"
    return _truncate(cleaned, 180)


def _recommendation_reason_for_shop(shop: dict, answer: str) -> str:
    name = str(shop.get("name") or "")
    aliases = [name]
    if " " in name:
        aliases.append(name.split(" ", 1)[0])
    if "｜" in name:
        aliases.append(name.split("｜", 1)[0])
    if "|" in name:
        aliases.append(name.split("|", 1)[0])

    for raw_line in (answer or "").splitlines():
        line = raw_line.strip()
        if "|" not in line:
            continue
        cells = [cell.strip(" -:") for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if any(alias and alias in cells[0] for alias in aliases):
            reason = cells[1]
            if reason and "推薦理由" not in reason:
                return _truncate(reason, 140)

    summary = str(shop.get("ai_summary") or "").strip()
    if summary:
        return _truncate(summary, 140)

    tags = [str(tag) for tag in (shop.get("atmosphere_tags") or [])[:2]]
    dishes = [str(dish) for dish in (shop.get("signature_dishes") or [])[:2]]
    highlights = [*dishes, *tags]
    if highlights:
        return _truncate("符合本次需求，亮點包含" + "、".join(highlights[:3]) + "。", 140)

    return "符合你這次的地點與餐廳類型需求，建議查看詳情後再確認可訂時段。"


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max(0, max_length - 1)].rstrip() + "…"
