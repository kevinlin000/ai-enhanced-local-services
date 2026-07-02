from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Callable


def decode_urlsafe(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def line_user_id_from_token_with_secret(token: str, secret: bytes) -> str:
    normalized = str(token or "").strip()
    if not normalized:
        return ""
    try:
        parts = normalized.split(".")
        if len(parts) != 3 or parts[0] != "v1":
            return ""
        payload_b64 = parts[1]
        expected_sig = base64.urlsafe_b64encode(
            hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8").rstrip("=")
        if not hmac.compare_digest(expected_sig, parts[2]):
            return ""
        payload = decode_urlsafe(payload_b64).decode("utf-8")
        line_user_id, scope, expires_at = payload.split("|", 2)
        if scope != "line_action":
            return ""
        if int(time.time()) > int(expires_at):
            return ""
        return line_user_id.strip()
    except Exception:
        return ""


def line_user_id_from_unsigned_legacy_token(token: str) -> str:
    normalized = str(token or "").strip()
    try:
        parts = normalized.split(".")
        if len(parts) != 3 or parts[0] != "v1":
            return ""
        payload = decode_urlsafe(parts[1]).decode("utf-8")
        line_user_id, scope, expires_at = payload.split("|", 2)
        user_id = line_user_id.strip()
        if not user_id or len(user_id) > 128:
            return ""
        if scope != "line_action":
            return ""
        if int(time.time()) > int(expires_at):
            return ""
        return user_id
    except Exception:
        return ""


def resolve_line_context(
    lt: str,
    legacy_line_user_id: str,
    *,
    action_secret: bytes,
    legacy_channel_secret: str,
    token_for_user: Callable[[str], str],
) -> tuple[str, str]:
    token = str(lt or "").strip()
    resolved_user_id = line_user_id_from_token_with_secret(token, action_secret)
    if resolved_user_id:
        return resolved_user_id, token
    legacy_secret = str(legacy_channel_secret or "").strip()
    if legacy_secret:
        legacy_user_id = line_user_id_from_token_with_secret(token, legacy_secret.encode("utf-8"))
        if legacy_user_id:
            return legacy_user_id, token_for_user(legacy_user_id)
    legacy_user_id = line_user_id_from_unsigned_legacy_token(token)
    if legacy_user_id:
        return legacy_user_id, token_for_user(legacy_user_id)
    fallback_user_id = str(legacy_line_user_id or "").strip()
    if fallback_user_id and len(fallback_user_id) <= 128:
        return fallback_user_id, token_for_user(fallback_user_id)
    return "", ""
