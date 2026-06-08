from app.models import ShopClean, ShopRaw

TAIPEI_DISTRICTS = (
    "中正",
    "大同",
    "中山",
    "松山",
    "大安",
    "萬華",
    "信義",
    "士林",
    "北投",
    "內湖",
    "南港",
    "文山",
)


def extract_district_from_address(address: str | None, fallback: str | None = None) -> str:
    """Prefer the real Google address district; crawler target district is only fallback."""
    text = address or ""
    for district in TAIPEI_DISTRICTS:
        simplified_name = (
            district
            .replace("萬", "万")
            .replace("華", "华")
            .replace("義", "义")
            .replace("內", "内")
        )
        if (
            f"{district}區" in text
            or f"{district}区" in text
            or f"{simplified_name}区" in text
        ):
            return district
    return fallback or ""


def normalize_place(place: dict, district: str) -> ShopRaw:
    location = place.get("location") or {}
    display_name = place.get("displayName") or {}
    formatted_address = place.get("formattedAddress")
    resolved_district = extract_district_from_address(formatted_address, district)
    return ShopRaw(
        place_id=place.get("id", ""),
        display_name=display_name.get("text"),
        formatted_address=formatted_address,
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        rating=place.get("rating"),
        user_rating_count=place.get("userRatingCount"),
        price_level=place.get("priceLevel"),
        primary_type=place.get("primaryType"),
        types=place.get("types") or [],
        district=resolved_district,
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
