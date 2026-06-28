from __future__ import annotations

from app.taxonomy import extract_avg_price

MISSING_PRICE_LABELS = {"未提及", "未知", "未公開價位"}


def manifest_price_overview(media: dict | None) -> str | None:
    overview = (media or {}).get("overview") or {}
    price = overview.get("price_overview")
    return str(price).strip() if price else None


def ai_price_per_person(shop: dict) -> str | None:
    ai = shop.get("ai_extracted", {}) or {}
    price = str(ai.get("price_per_person") or "").strip()
    if not price or price in MISSING_PRICE_LABELS:
        return None
    return price


def resolved_price_label(
    shop: dict,
    media: dict | None,
    price_level_to_label: dict[str, str],
) -> str | None:
    return (
        ai_price_per_person(shop)
        or manifest_price_overview(media)
        or price_level_to_label.get(shop.get("price_level"))
    )


def resolved_avg_price(
    shop: dict,
    media: dict | None,
    price_level_to_avg: dict[str, int],
) -> int | None:
    return (
        extract_avg_price(ai_price_per_person(shop))
        or extract_avg_price(manifest_price_overview(media))
        or price_level_to_avg.get(shop.get("price_level"))
    )
