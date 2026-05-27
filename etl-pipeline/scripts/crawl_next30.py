from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
import os
from pathlib import Path

import pymysql
import structlog
from dotenv import load_dotenv

from app.config import RAW_DIR, settings
from app.enricher import Enricher
from app.filter import filter_quality_shops
from app.normalizer import normalize_place
from app.places_client import PlacesClient

log = structlog.get_logger()

EXPANDED_DISTRICTS = {
    "大同": (25.0631, 121.5130),
    "士林": (25.0928, 121.5251),
    "內湖": (25.0830, 121.5860),
    "南港": (25.0547, 121.6066),
    "萬華": (25.0325, 121.4998),
    "文山": (24.9889, 121.5705),
}

RADIUS = 1800
MAX_RESULTS = 20
TARGET_COUNT = 30


def fetch_existing_place_ids() -> set[str]:
    load_dotenv(".env")
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT place_id FROM tb_shop WHERE place_id IS NOT NULL AND place_id <> ''")
            return {row[0] for row in cur.fetchall() if row[0]}
    finally:
        conn.close()


def sort_key(place: dict) -> tuple[float, int]:
    return (place.get("rating") or 0, place.get("user_rating_count") or 0)


def main() -> None:
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

    for district, (lat, lng) in EXPANDED_DISTRICTS.items():
        places = client.search_nearby(lat=lat, lng=lng, radius=RADIUS, max_results=MAX_RESULTS)
        district_counts[district] = len(places)
        log.info("district_fetched", district=district, count=len(places))

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
    existing_place_ids = fetch_existing_place_ids()
    new_places = [place for place in filtered_places if place["place_id"] not in existing_place_ids]
    new_places = sorted(new_places, key=sort_key, reverse=True)
    selected_places = new_places[:TARGET_COUNT]
    enriched_places = Enricher(client).enrich(selected_places)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    search_output_path = RAW_DIR / f"places_search_next30_{timestamp}.json"
    search_output_path.write_text(
        json.dumps(
            {
                "timestamp": timestamp,
                "radius": RADIUS,
                "max_results_per_district": MAX_RESULTS,
                "district_counts": dict(district_counts),
                "deduped_total": len(deduped_places),
                "filtered_total": len(filtered_places),
                "new_total": len(new_places),
                "selected_total": len(selected_places),
                "results": raw_batches,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    enriched_output_path = RAW_DIR / f"places_enriched_next30_{timestamp}.json"
    enriched_output_path.write_text(json.dumps(enriched_places, ensure_ascii=False, indent=2))

    log.info(
        "selected_places",
        names=[place.get("display_name") or place.get("name") for place in selected_places],
    )
    print(f"deduped: {len(deduped_places)}")
    print(f"filtered: {len(filtered_places)}")
    print(f"new_candidates: {len(new_places)}")
    print(f"selected: {len(selected_places)}")
    print(f"search raw json: {search_output_path}")
    print(f"enriched raw json: {enriched_output_path}")


if __name__ == "__main__":
    main()
