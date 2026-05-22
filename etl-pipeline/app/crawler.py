import json
from collections import Counter
from datetime import datetime

import structlog

from app.config import DISTRICTS, MAX_RESULTS, RADIUS, RAW_DIR, settings
from app.filter import filter_quality_shops
from app.normalizer import normalize_place
from app.places_client import PlacesClient

logger = structlog.get_logger(__name__)


def run() -> dict:
    if (
        not settings.google_places_api_key
        or settings.google_places_api_key.startswith("your_")
        or "你的" in settings.google_places_api_key
    ):
        raise SystemExit("GOOGLE_PLACES_API_KEY not set in .env")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    client = PlacesClient()
    district_counts: Counter[str] = Counter()
    deduped: dict[str, dict] = {}
    filtered_counts: Counter[str] = Counter()
    excluded_primary_types: Counter[str] = Counter()
    raw_batches: list[dict] = []

    for district, (lat, lng) in DISTRICTS.items():
        places = client.search_nearby(lat=lat, lng=lng, radius=RADIUS, max_results=MAX_RESULTS)
        district_counts[district] = len(places)
        logger.info("district_fetched", district=district, count=len(places))

        normalized_places = [normalize_place(place, district) for place in places]
        raw_batches.append(
            {
                "district": district,
                "center": {"lat": lat, "lng": lng},
                "count": len(normalized_places),
                "places": [item.model_dump(mode="json") for item in normalized_places],
            }
        )

        for item in normalized_places:
            if item.place_id:
                deduped[item.place_id] = item.model_dump(mode="json")

    deduped_places = list(deduped.values())
    filtered_places = filter_quality_shops(deduped_places)
    filtered_ids = {place["place_id"] for place in filtered_places}
    filtered_out_places = [
        place for place in deduped_places if place["place_id"] not in filtered_ids
    ]

    for place in deduped_places:
        if place["place_id"] in filtered_ids:
            filtered_counts[place["district"]] += 1
        else:
            excluded_primary_types[place.get("primary_type") or "UNKNOWN"] += 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        "timestamp": timestamp,
        "radius": RADIUS,
        "max_results_per_district": MAX_RESULTS,
        "district_counts": dict(district_counts),
        "filtered_counts": dict(filtered_counts),
        "deduped_total": len(deduped),
        "filtered_total": len(filtered_places),
        "excluded_primary_types": dict(excluded_primary_types),
        "results": raw_batches,
    }
    output_path = RAW_DIR / f"places_search_{timestamp}.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    for district in DISTRICTS:
        print(f"{district}: {district_counts[district]} 家")
    print(f"篩選前 {len(deduped_places)} 家、篩選後 {len(filtered_places)} 家")
    print("被過濾掉的店家:")
    for place in filtered_out_places:
        print(
            "- "
            f"{place.get('display_name') or place.get('name')} | "
            f"{place.get('primary_type')} | "
            f"rating={place.get('rating')} | "
            f"user_rating_count={place.get('user_rating_count')} | "
            f"price_level={place.get('price_level')}"
        )
    print("排除的店家類型分佈:")
    for primary_type, count in excluded_primary_types.most_common():
        print(f"- {primary_type}: {count}")
    print(f"總計 {sum(district_counts.values())} 家（去重後 {len(deduped)} 家）")
    print(f"raw json: {output_path}")

    return output


if __name__ == "__main__":
    run()
