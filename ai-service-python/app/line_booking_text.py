from __future__ import annotations

import re
from datetime import date, timedelta


def zh_number_to_int(value: str) -> int | None:
    digits = re.sub(r"\D", "", value)
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None

    mapping = {
        "一": 1,
        "二": 2,
        "兩": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if value == "十":
        return 10
    if value.startswith("十") and len(value) == 2:
        return 10 + mapping.get(value[1], 0)
    if value.endswith("十") and len(value) == 2:
        return mapping.get(value[0], 0) * 10
    if "十" in value and len(value) == 3:
        return mapping.get(value[0], 0) * 10 + mapping.get(value[2], 0)
    return mapping.get(value)


def weekday_booking_date_from_text(text: str, today: date) -> str:
    normalized = str(text or "").strip()
    match = re.search(r"(?P<prefix>下|這|本)?(?:週|星期|禮拜)(?P<day>[一二三四五六日天])", normalized)
    if not match:
        return ""

    weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    target_weekday = weekday_map.get(match.group("day"))
    if target_weekday is None:
        return ""

    prefix = match.group("prefix") or ""
    current_weekday = today.weekday()
    if prefix == "下":
        days_until_next_monday = 7 - current_weekday
        return (today + timedelta(days=days_until_next_monday + target_weekday)).isoformat()

    days_until = target_weekday - current_weekday
    if days_until <= 0:
        days_until += 7
    return (today + timedelta(days=days_until)).isoformat()


def explicit_booking_date_from_text(text: str, today: date) -> str:
    normalized = str(text or "").strip()
    full_date = re.search(
        r"(?P<year>20\d{2})\s*[年/\-.]\s*(?P<month>1[0-2]|0?[1-9])\s*[月/\-.]\s*(?P<day>3[01]|[12]\d|0?[1-9])\s*日?",
        normalized,
    )
    if full_date:
        try:
            return date(
                int(full_date.group("year")),
                int(full_date.group("month")),
                int(full_date.group("day")),
            ).isoformat()
        except ValueError:
            return ""

    month_day = re.search(r"(?P<month>1[0-2]|0?[1-9])\s*月\s*(?P<day>3[01]|[12]\d|0?[1-9])\s*日?", normalized)
    if not month_day:
        return ""

    try:
        parsed = date(today.year, int(month_day.group("month")), int(month_day.group("day")))
    except ValueError:
        return ""
    if parsed <= today:
        parsed = date(today.year + 1, parsed.month, parsed.day)
    return parsed.isoformat()


def line_booking_prefill_from_text(text: str, today: date) -> dict:
    normalized = str(text or "").strip()
    booking_date = ""
    if "後天" in normalized:
        booking_date = (today + timedelta(days=2)).isoformat()
    elif "明天" in normalized or "明晚" in normalized:
        booking_date = (today + timedelta(days=1)).isoformat()
    else:
        booking_date = weekday_booking_date_from_text(normalized, today)
        if not booking_date:
            booking_date = explicit_booking_date_from_text(normalized, today)

    booking_time = ""
    explicit_time = re.search(r"([0-2]?\d)[:：]([0-5]\d)", normalized)
    if explicit_time:
        hour = int(explicit_time.group(1))
        minute = int(explicit_time.group(2))
        booking_time = f"{hour:02d}:{minute:02d}"
    else:
        hour_match = re.search(r"([0-2]?\d)\s*點\s*(半)?", normalized)
        if hour_match:
            hour = int(hour_match.group(1))
            if hour <= 11 and any(token in normalized for token in ("晚", "晚上", "晚餐")):
                hour += 12
            minute = 30 if hour_match.group(2) else 0
            booking_time = f"{hour:02d}:{minute:02d}"
        elif any(token in normalized for token in ("晚上", "晚餐", "明晚")):
            booking_time = "19:00"
        elif any(token in normalized for token in ("中午", "午餐")):
            booking_time = "12:00"

    people = None
    people_match = re.search(r"([一二兩三四五六七八九十\d]{1,3})\s*(個)?[人位]", normalized)
    if people_match:
        people = zh_number_to_int(people_match.group(1))
        if people is not None:
            people = min(12, max(1, people))

    return {"date": booking_date, "time": booking_time, "people": people}
