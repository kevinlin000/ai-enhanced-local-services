import json
from collections import Counter
from datetime import datetime

import structlog

from app.config import DISTRICTS, MAX_RESULTS, RADIUS, RAW_DIR, settings
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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        "timestamp": timestamp,
        "radius": RADIUS,
        "max_results_per_district": MAX_RESULTS,
        "district_counts": dict(district_counts),
        "deduped_total": len(deduped),
        "results": raw_batches,
    }
    output_path = RAW_DIR / f"places_search_{timestamp}.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    for district in DISTRICTS:
        print(f"{district}: {district_counts[district]} 家")
    print(f"總計 {sum(district_counts.values())} 家（去重後 {len(deduped)} 家）")
    print(f"raw json: {output_path}")

    return output


if __name__ == "__main__":
    run()
