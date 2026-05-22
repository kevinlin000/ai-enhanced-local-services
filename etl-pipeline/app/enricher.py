import time

import structlog

from app.places_client import PlacesClient

logger = structlog.get_logger(__name__)


class Enricher:
    def __init__(self, client: PlacesClient):
        self.client = client

    def enrich(self, places: list[dict]) -> list[dict]:
        """對每家店打 get_place_details、補完整資料"""
        enriched: list[dict] = []
        for i, place in enumerate(places):
            try:
                details = self.client.get_place_details(place["place_id"])
                reviews = [
                    {
                        "author": review.get("authorAttribution", {}).get("displayName"),
                        "rating": review.get("rating"),
                        "text": review.get("text", {}).get("text"),
                        "publish_time": review.get("publishTime"),
                        "relative_time": review.get("relativePublishTimeDescription"),
                    }
                    for review in details.get("reviews", [])
                ]
                enriched_place = {
                    **place,
                    "phone": details.get("internationalPhoneNumber"),
                    "opening_hours": details.get("regularOpeningHours", {}).get(
                        "weekdayDescriptions"
                    ),
                    "reviews": reviews,
                    "full_address": details.get("formattedAddress"),
                }
                enriched.append(enriched_place)
                logger.info(
                    "enriched",
                    idx=i + 1,
                    total=len(places),
                    name=place["display_name"],
                    review_count=len(reviews),
                )
                time.sleep(0.1)
            except Exception as exc:
                logger.error(
                    "enrich_failed",
                    place_id=place["place_id"],
                    error=str(exc),
                )
                continue
        return enriched
