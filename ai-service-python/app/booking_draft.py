from __future__ import annotations

import re


def compact_booking_prefill(prefill: dict | None) -> dict:
    if not isinstance(prefill, dict):
        return {}
    compact: dict = {}
    for key in ("date", "time", "table_type"):
        value = str(prefill.get(key) or "").strip()
        if value:
            compact[key] = value
    people = prefill.get("people")
    try:
        if people is not None:
            compact["people"] = int(people)
    except (TypeError, ValueError):
        pass
    return compact


def merge_booking_prefill(current: dict, draft: dict | None, *, override: bool = False) -> dict:
    if override and isinstance(draft, dict):
        merged = compact_booking_prefill(draft)
        for key in ("date", "time", "people", "table_type"):
            if current.get(key) not in (None, ""):
                merged[key] = current.get(key)
        return merged
    merged = dict(current or {})
    if not isinstance(draft, dict):
        return merged
    for key in ("date", "time", "people", "table_type"):
        if merged.get(key) in (None, "") and draft.get(key) not in (None, ""):
            merged[key] = draft.get(key)
    return merged


def booking_draft_payload(shop_id: int, shop_name: str, prefill: dict | None) -> dict:
    draft = {
        "shop_id": int(shop_id),
        "shop_name": str(shop_name or f"店家 {shop_id}"),
    }
    draft.update(compact_booking_prefill(prefill))
    return draft


def booking_draft_missing(draft: dict) -> list[str]:
    missing = []
    if not draft.get("date"):
        missing.append("日期")
    if not draft.get("time"):
        missing.append("時間")
    if not draft.get("people"):
        missing.append("人數")
    return missing


def booking_draft_confirmation_answer(draft: dict, query: str = "") -> str:
    missing = booking_draft_missing(draft)
    shop_name = str(draft.get("shop_name") or f"店家 {draft.get('shop_id')}")
    if missing:
        return f"我已鎖定「{shop_name}」，還缺{'、'.join(missing)}。請補齊後我再幫你整理確認。"
    normalized = re.sub(r"\s+", "", str(query or ""))
    if any(token in normalized for token in ("改成", "改到", "晚點", "主管", "大老闆", "老闆", "總共")):
        return (
            f"我已沿用上一輪選定的「{shop_name}」，並套用最新變更："
            f"{draft.get('date')} {draft.get('time')}、{draft.get('people')} 人。\n"
            "請確認後再送出；送出時會即時檢查店家容量並扣位，若額滿就改開候位 / 空位通知。"
        )
    return (
        "我幫你整理好訂位內容了，請確認後我再送出。\n"
        f"- 店家：{shop_name}\n"
        f"- 日期：{draft.get('date')}\n"
        f"- 時間：{draft.get('time')}\n"
        f"- 人數：{draft.get('people')} 人\n"
        "確認無誤後，可以點下方確認卡，或直接回「確認訂位」。"
    )
