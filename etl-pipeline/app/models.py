from typing import Any

from pydantic import BaseModel, Field


class ShopRaw(BaseModel):
    place_id: str
    display_name: str | None = None
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    price_level: str | None = None
    primary_type: str | None = None
    types: list[str] = Field(default_factory=list)
    district: str
    source_payload: dict[str, Any]


class ShopClean(BaseModel):
    place_id: str
    name: str | None = None
    address: str | None = None
    district: str
    lat: float | None = None
    lng: float | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    price_level: str | None = None
    primary_type: str | None = None
    types: list[str] = Field(default_factory=list)
