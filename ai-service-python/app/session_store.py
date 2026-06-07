"""Redis-backed chat session store."""
import json
import os
from typing import Any, List

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL = 1800   # 30 分鐘
MAX_TURNS = 10       # 保留最後 10 輪（20 條 message）

_client = None


def client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def session_key(session_id: str) -> str:
    return f"chat:session:{session_id}"


def load_history(session_id: str) -> List[dict]:
    """從 Redis 讀對話歷史，回 [{"role": "user"|"model", "content": "..."}]。"""
    if not session_id:
        return []
    raw = client().get(session_key(session_id))
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
    client().setex(
        session_key(session_id),
        SESSION_TTL,
        json.dumps(trimmed, ensure_ascii=False),
    )


def clear_session(session_id: str) -> None:
    if session_id:
        client().delete(session_key(session_id))
