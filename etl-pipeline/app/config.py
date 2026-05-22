from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


DISTRICTS = {
    "信義": (25.0330, 121.5654),
    "中山": (25.0635, 121.5258),
    "大安": (25.0265, 121.5436),
    "中正": (25.0322, 121.5180),
    "松山": (25.0500, 121.5774),
}

RADIUS = 1000
INCLUDED_TYPES = ["restaurant"]
MAX_RESULTS = 20

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"


class Settings(BaseSettings):
    google_places_api_key: str = ""
    places_api_base: str = "https://places.googleapis.com/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
