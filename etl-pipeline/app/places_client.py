from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import INCLUDED_TYPES, MAX_RESULTS, settings


class PlacesClient:
    def __init__(self) -> None:
        self.base_url = settings.places_api_base.rstrip("/")
        self.api_key = settings.google_places_api_key
        self.timeout = 20.0

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
        }

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        try:
            detail = response.text
        except Exception:
            detail = "<no response body>"
        raise httpx.HTTPStatusError(
            f"{response.status_code} for {response.request.url}: {detail}",
            request=response.request,
            response=response,
        )

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True,
    )
    def search_nearby(
        self, lat: float, lng: float, radius: int = 1000, max_results: int = MAX_RESULTS
    ) -> list[dict[str, Any]]:
        body = {
            "includedTypes": INCLUDED_TYPES,
            "maxResultCount": max_results,
            "languageCode": "zh-TW",
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius),
                }
            },
        }
        headers = {
            **self.headers,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.userRatingCount,"
                "places.priceLevel,places.primaryType,places.types"
            ),
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/places:searchNearby",
                headers=headers,
                json=body,
            )
            if response.is_error:
                self._raise(response)
            payload = response.json()
            return payload.get("places", [])

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True,
    )
    def search_text(
        self,
        text_query: str,
        lat: float | None = None,
        lng: float | None = None,
        radius: int = 5000,
        max_results: int = MAX_RESULTS,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {
            "textQuery": text_query,
            "includedType": "restaurant",
            "maxResultCount": max_results,
            "languageCode": "zh-TW",
            "regionCode": "TW",
        }
        if lat is not None and lng is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius),
                }
            }

        headers = {
            **self.headers,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.userRatingCount,"
                "places.priceLevel,places.primaryType,places.types"
            ),
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/places:searchText",
                headers=headers,
                json=body,
            )
            if response.is_error:
                self._raise(response)
            payload = response.json()
            return payload.get("places", [])

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True,
    )
    def get_place_details(self, place_id: str) -> dict[str, Any]:
        headers = {
            **self.headers,
            "X-Goog-FieldMask": (
                "id,displayName,formattedAddress,location,rating,userRatingCount,"
                "priceLevel,primaryType,types,reviews,internationalPhoneNumber,"
                "regularOpeningHours"
            ),
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/places/{place_id}?languageCode=zh-TW",
                headers=headers,
            )
            if response.is_error:
                self._raise(response)
            return response.json()
