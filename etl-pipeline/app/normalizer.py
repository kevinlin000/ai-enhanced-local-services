from app.models import ShopClean, ShopRaw


def normalize_place(place: dict, district: str) -> ShopRaw:
    location = place.get("location") or {}
    display_name = place.get("displayName") or {}
    return ShopRaw(
        place_id=place.get("id", ""),
        display_name=display_name.get("text"),
        formatted_address=place.get("formattedAddress"),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        rating=place.get("rating"),
        user_rating_count=place.get("userRatingCount"),
        price_level=place.get("priceLevel"),
        primary_type=place.get("primaryType"),
        types=place.get("types") or [],
        district=district,
        source_payload=place,
    )


def to_clean(raw: ShopRaw) -> ShopClean:
    return ShopClean(
        place_id=raw.place_id,
        name=raw.display_name,
        address=raw.formatted_address,
        district=raw.district,
        lat=raw.latitude,
        lng=raw.longitude,
        rating=raw.rating,
        user_rating_count=raw.user_rating_count,
        price_level=raw.price_level,
        primary_type=raw.primary_type,
        types=raw.types,
    )
