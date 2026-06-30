from __future__ import annotations

import json
import logging

from app import session_store

logger = logging.getLogger("bytebites.ai")


def line_recommendation_state_key(user_id: str) -> str:
    return f"line:recommendation:{user_id}"


def line_booking_state_key(user_id: str) -> str:
    return f"line:booking:{user_id}"


def line_booking_draft_state_key(user_id: str) -> str:
    return f"line:booking-draft:{user_id}"


def line_location_state_key(user_id: str) -> str:
    return f"line:location:{user_id}"


def load_json_state(key: str, log_name: str, user_id: str) -> dict:
    try:
        raw = session_store.client().get(key)
    except Exception:
        logger.exception("%s user_id=%s", log_name, user_id)
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def clear_state_key(key: str, log_name: str, user_id: str) -> None:
    try:
        session_store.client().delete(key)
    except Exception:
        logger.exception("%s user_id=%s", log_name, user_id)


def save_json_state(key: str, ttl_seconds: int, payload: dict, log_name: str, user_id: str) -> None:
    try:
        session_store.client().setex(
            key,
            ttl_seconds,
            json.dumps(payload, ensure_ascii=False),
        )
    except Exception:
        logger.exception("%s user_id=%s", log_name, user_id)
