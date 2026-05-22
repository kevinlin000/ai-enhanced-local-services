ACCEPTABLE_PRICE_LEVELS = {
    "PRICE_LEVEL_MODERATE",
    "PRICE_LEVEL_EXPENSIVE",
    "PRICE_LEVEL_VERY_EXPENSIVE",
}


def filter_quality_shops(places: list[dict]) -> list[dict]:
    """篩選符合中高價定位的店家"""

    EXCLUDED_TYPES = {
        "fast_food_restaurant",
        "convenience_store",
        "meal_takeaway",
        "hotel",
        "department_store",
    }

    filtered = []
    for place in places:
        if place.get("primary_type") in EXCLUDED_TYPES:
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
