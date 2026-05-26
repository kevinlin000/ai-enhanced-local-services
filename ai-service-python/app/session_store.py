"""Redis-backed chat session store."""
import json
import os
from typing import List

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


def save_history(session_id: str, history: List[dict]) -> None:
    """寫回 Redis，trimmed to last MAX_TURNS * 2 entries, TTL reset。"""
    if not session_id:
        return
    trimmed = history[-(MAX_TURNS * 2):]
    client().setex(
        session_key(session_id),
        SESSION_TTL,
        json.dumps(trimmed, ensure_ascii=False),
    )


def clear_session(session_id: str) -> None:
    if session_id:
        client().delete(session_key(session_id))
