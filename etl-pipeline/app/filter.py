ACCEPTABLE_PRICE_LEVELS = {
    "PRICE_LEVEL_MODERATE",
    "PRICE_LEVEL_EXPENSIVE",
    "PRICE_LEVEL_VERY_EXPENSIVE",
}

EXCLUDED_NAME_KEYWORDS = {
    "ktv",
    "don don donki",
    "月子餐",
    "烘焙diy",
    "生態館",
    "無訂位",
    "不接受訂位",
    "沒有接受訂位",
    "現場為主",
    "便所",
    "電競",
    "雞排",
}

EXCLUDED_TYPES = {
    "amusement_center",
    "fast_food_restaurant",
    "convenience_store",
    "meal_takeaway",
    "hotel",
    "department_store",
    "supermarket",
}

HARD_EXCLUDED_TYPES = {
    "amusement_center",
    "convenience_store",
    "department_store",
    "supermarket",
}


def is_recommendation_suitable(place: dict) -> bool:
    """Keep venues that make sense for a restaurant recommendation and booking flow."""

    name = (place.get("display_name") or place.get("name") or "").lower()
    if any(keyword in name for keyword in EXCLUDED_NAME_KEYWORDS):
        return False

    address = place.get("formatted_address") or place.get("address") or ""
    if "台北" not in address and "臺北" not in address:
        return False

    primary_type = place.get("primary_type")
    if primary_type in EXCLUDED_TYPES:
        return False

    types = set(place.get("types") or [])
    if types & HARD_EXCLUDED_TYPES:
        return False

    return True


def filter_quality_shops(places: list[dict]) -> list[dict]:
    """篩選符合中高價定位的店家"""

    filtered = []
    for place in places:
        if not is_recommendation_suitable(place):
            continue

        rating = place.get("rating") or 0
        count = place.get("user_rating_count") or 0
        if rating < 3.8 or count < 50:
            continue

        price = place.get("price_level")
        if price == "PRICE_LEVEL_INEXPENSIVE":
            continue

        if price in ACCEPTABLE_PRICE_LEVELS:
            filtered.append(place)
            continue

        if price is None and rating >= 4.3 and count >= 1000:
            filtered.append(place)

    return filtered
