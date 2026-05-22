def filter_quality_shops(places: list[dict]) -> list[dict]:
    """篩選符合中高價定位的店家"""

    EXCLUDED_TYPES = {
        "fast_food_restaurant",
        "convenience_store",
        "meal_takeaway",
    }

    ACCEPTABLE_PRICE_LEVELS = {
        "PRICE_LEVEL_MODERATE",
        "PRICE_LEVEL_EXPENSIVE",
        "PRICE_LEVEL_VERY_EXPENSIVE",
    }

    filtered = []
    for place in places:
        if place.get("price_level") not in ACCEPTABLE_PRICE_LEVELS:
            continue
        if (place.get("user_rating_count") or 0) < 50:
            continue
        if (place.get("rating") or 0) < 3.8:
            continue
        if place.get("primary_type") in EXCLUDED_TYPES:
            continue
        filtered.append(place)
    return filtered
