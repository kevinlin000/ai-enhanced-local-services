"""Redis-backed chat session store."""
import json
import os
import time
from typing import Any, List

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL = 1800   # 30 分鐘
MAX_TURNS = 10       # 保留最後 10 輪（20 條 message）

_client = None
_memory_store: dict[str, tuple[str, float]] = {}


def client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def session_key(session_id: str) -> str:
    return f"chat:session:{session_id}"


def _memory_get(key: str) -> str | None:
    item = _memory_store.get(key)
    if not item:
        return None
    raw, expires_at = item
    if expires_at <= time.time():
        _memory_store.pop(key, None)
        return None
    return raw


def _load_raw(key: str) -> str | None:
    try:
        return client().get(key)
    except (redis.RedisError, OSError):
        return _memory_get(key)


def _save_raw(key: str, raw: str) -> None:
    try:
        client().setex(key, SESSION_TTL, raw)
    except (redis.RedisError, OSError):
        _memory_store[key] = (raw, time.time() + SESSION_TTL)


def _delete_raw(key: str) -> None:
    try:
        client().delete(key)
    except (redis.RedisError, OSError):
        pass
    _memory_store.pop(key, None)


def load_history(session_id: str) -> List[dict]:
    """從 Redis 讀對話歷史，回 [{"role": "user"|"model", "content": "..."}]。"""
    if not session_id:
        return []
    raw = _load_raw(session_key(session_id))
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def _compact_turn(turn: dict[str, Any]) -> dict[str, Any] | None:
    role = turn.get("role")
    content = str(turn.get("content") or "").strip()
    if role not in {"user", "model"} or not content:
        return None

    compacted: dict[str, Any] = {
        "role": role,
        "content": content[:4000],
    }

    transaction = turn.get("transaction")
    if isinstance(transaction, dict):
        compacted["transaction"] = {
            key: transaction.get(key)
            for key in (
                "kind",
                "success",
                "status",
                "shop_id",
                "shop_name",
                "booking_code",
                "people",
                "date",
                "time",
                "table_type",
                "needs_deposit",
                "deposit_total",
                "hold_expires_at",
                "hold_minutes",
                "rec_trade_id",
                "payment_amount",
                "payment_note",
                "error",
            )
            if key in transaction
        }

    recommendation = turn.get("recommendation")
    if isinstance(recommendation, dict):
        shops = recommendation.get("shops")
        if isinstance(shops, list):
            compact_shops = []
            for shop in shops[:3]:
                if not isinstance(shop, dict) or not shop.get("shop_id"):
                    continue
                compact_shop = {
                    "shop_id": shop.get("shop_id"),
                    "name": str(shop.get("name") or "")[:120],
                }
                for key, limit in (
                    ("district", 40),
                    ("category", 80),
                    ("price_per_person", 80),
                    ("ai_summary", 500),
                    ("booking_difficulty", 160),
                ):
                    value = str(shop.get(key) or "").strip()
                    if value:
                        compact_shop[key] = value[:limit]
                if shop.get("avg_price") is not None:
                    compact_shop["avg_price"] = shop.get("avg_price")
                for key, limit in (("signature_dishes", 80), ("atmosphere_tags", 40)):
                    values = [
                        str(item)[:limit]
                        for item in (shop.get(key) or [])[:5]
                        if item
                    ]
                    if values:
                        compact_shop[key] = values
                compact_shops.append(compact_shop)
            compacted["recommendation"] = {
                "query": str(recommendation.get("query") or "")[:500],
                "shops": compact_shops,
            }

    booking_draft = turn.get("booking_draft")
    if isinstance(booking_draft, dict):
        compact_draft = {}
        for key in ("shop_id", "shop_name", "date", "time", "people", "table_type"):
            value = booking_draft.get(key)
            if value not in (None, ""):
                compact_draft[key] = value
        if compact_draft:
            compacted["booking_draft"] = compact_draft

    clarification_query = str(turn.get("clarification_query") or "").strip()
    if clarification_query:
        compacted["clarification_query"] = clarification_query[:500]

    return compacted


def compact_history(history: List[dict]) -> List[dict]:
    """Keep recent visible turns and booking continuity facts only."""
    compacted: list[dict] = []
    for turn in history:
        if not isinstance(turn, dict):
            continue
        compact_turn = _compact_turn(turn)
        if compact_turn:
            compacted.append(compact_turn)
    return compacted[-(MAX_TURNS * 2):]


def save_history(session_id: str, history: List[dict]) -> None:
    """寫回 Redis，trimmed to last MAX_TURNS * 2 entries, TTL reset。"""
    if not session_id:
        return
    trimmed = compact_history(history)
    _save_raw(session_key(session_id), json.dumps(trimmed, ensure_ascii=False))


def clear_session(session_id: str) -> None:
    if session_id:
        _delete_raw(session_key(session_id))
