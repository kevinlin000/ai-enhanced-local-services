from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import Counter
from datetime import datetime
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

TAIPEI_DISTRICTS = {
    "信義": (25.0330, 121.5654),
    "大安": (25.0265, 121.5436),
    "中山": (25.0635, 121.5258),
    "松山": (25.0500, 121.5774),
    "中正": (25.0322, 121.5180),
    "萬華": (25.0325, 121.4998),
    "大同": (25.0631, 121.5130),
    "士林": (25.0928, 121.5251),
    "內湖": (25.0830, 121.5860),
    "南港": (25.0547, 121.6066),
    "文山": (24.9889, 121.5705),
    "北投": (25.1320, 121.5010),
}


def fetch_existing_state() -> tuple[int, set[str]]:
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
            cur.execute("SELECT COUNT(*) FROM tb_shop WHERE source='google_places' AND is_active=1")
            active_count = int(cur.fetchone()[0])
            cur.execute("SELECT place_id FROM tb_shop WHERE place_id IS NOT NULL AND place_id <> ''")
            place_ids = {row[0] for row in cur.fetchall() if row[0]}
            return active_count, place_ids
    finally:
        conn.close()


def sort_key(place: dict) -> tuple[float, int]:
    return (place.get("rating") or 0, place.get("user_rating_count") or 0)


def grid_points(lat: float, lng: float, rings: int, step_km: float) -> list[tuple[float, float]]:
    # Approximate Taipei-scale offsets; precise geodesy is unnecessary for search tiling.
    lat_step = step_km / 111.0
    lng_step = step_km / (111.0 * math.cos(math.radians(lat)))
    points: list[tuple[float, float]] = []
    for dy in range(-rings, rings + 1):
        for dx in range(-rings, rings + 1):
            points.append((lat + dy * lat_step, lng + dx * lng_step))
    # Center first, then closer rings, so early stop returns denser commercial areas.
    return sorted(points, key=lambda point: abs(point[0] - lat) + abs(point[1] - lng))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-active", type=int, default=400)
    parser.add_argument("--max-new", type=int, default=320)
    parser.add_argument("--rings", type=int, default=2)
    parser.add_argument("--step-km", type=float, default=1.1)
    parser.add_argument("--radius", type=int, default=850)
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    args = parser.parse_args()

    if (
        not settings.google_places_api_key
        or settings.google_places_api_key.startswith("your_")
        or "你的" in settings.google_places_api_key
    ):
        raise SystemExit("GOOGLE_PLACES_API_KEY not set in .env")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    active_count, existing_place_ids = fetch_existing_state()
    target_new = max(0, min(args.max_new, args.target_active - active_count))
    if target_new == 0:
        print(f"already at target: active_count={active_count}, target={args.target_active}")
        return

    client = PlacesClient()
    raw_batches: list[dict] = []
    deduped: dict[str, dict] = {}
    district_counts: Counter[str] = Counter()

    for district, (lat, lng) in TAIPEI_DISTRICTS.items():
        for point_lat, point_lng in grid_points(lat, lng, rings=args.rings, step_km=args.step_km):
            places = client.search_nearby(
                lat=point_lat,
                lng=point_lng,
                radius=args.radius,
                max_results=args.max_results,
            )
            district_counts[district] += len(places)
            normalized_places = [normalize_place(place, district) for place in places]
            raw_batches.append(
                {
                    "district": district,
                    "center": {"lat": point_lat, "lng": point_lng},
                    "count": len(normalized_places),
                    "places": [item.model_dump(mode="json") for item in normalized_places],
                }
            )
            for item in normalized_places:
                if item.place_id:
                    deduped[item.place_id] = item.model_dump(mode="json")

            candidate_count = sum(1 for place_id in deduped if place_id not in existing_place_ids)
            log.info(
                "search_progress",
                district=district,
                raw=len(places),
                deduped=len(deduped),
                new_candidates=candidate_count,
            )
            time.sleep(args.sleep_seconds)

    deduped_places = list(deduped.values())
    filtered_places = filter_quality_shops(deduped_places)
    new_places = [place for place in filtered_places if place["place_id"] not in existing_place_ids]
    selected_places = sorted(new_places, key=sort_key, reverse=True)[:target_new]
    enriched_places = Enricher(client).enrich(selected_places)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    search_output_path = RAW_DIR / f"places_search_target{args.target_active}_{timestamp}.json"
    search_output_path.write_text(
        json.dumps(
            {
                "timestamp": timestamp,
                "target_active": args.target_active,
                "existing_active": active_count,
                "target_new": target_new,
                "rings": args.rings,
                "step_km": args.step_km,
                "radius": args.radius,
                "max_results": args.max_results,
                "district_counts": dict(district_counts),
                "deduped_total": len(deduped_places),
                "filtered_total": len(filtered_places),
                "new_total": len(new_places),
                "selected_total": len(selected_places),
                "enriched_total": len(enriched_places),
                "results": raw_batches,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    enriched_output_path = RAW_DIR / f"places_enriched_target{args.target_active}_{timestamp}.json"
    enriched_output_path.write_text(json.dumps(enriched_places, ensure_ascii=False, indent=2))

    print(f"existing_active: {active_count}")
    print(f"target_new: {target_new}")
    print(f"deduped: {len(deduped_places)}")
    print(f"filtered: {len(filtered_places)}")
    print(f"new_candidates: {len(new_places)}")
    print(f"selected: {len(selected_places)}")
    print(f"enriched: {len(enriched_places)}")
    print(f"search raw json: {search_output_path}")
    print(f"enriched raw json: {enriched_output_path}")


if __name__ == "__main__":
    main()
