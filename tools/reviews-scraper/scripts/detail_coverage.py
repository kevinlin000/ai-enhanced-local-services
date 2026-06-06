#!/usr/bin/env python3
"""Audit detailed scraper coverage against active shop inventory.

The Places crawler can grow tb_shop quickly, but rich UI data comes from this
scraper's SQLite/Mongo outputs. This script makes that gap explicit.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymysql
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


ROOT = Path(__file__).resolve().parents[3]
SCRAPER_DIR = ROOT / "tools" / "reviews-scraper"
SQLITE_DB = SCRAPER_DIR / "reviews.db"
MEDIA_MANIFEST = ROOT / "web" / "data" / "shop-media.json"


@dataclass(frozen=True)
class Shop:
    id: int
    place_id: str
    name: str
    address: str
    rating: float | None
    comments: int | None
    category: str | None
    area: str | None


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_env() -> None:
    for rel in (".env", "backend-java/.env", "etl-pipeline/.env", "tools/reviews-scraper/.env"):
        load_env_file(ROOT / rel)


def env_first(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return default


def mysql_config() -> dict[str, Any]:
    return {
        "host": env_first("MYSQL_HOST", "DB_HOST", default="localhost"),
        "port": int(env_first("MYSQL_PORT", "DB_PORT", default="3306")),
        "user": env_first("MYSQL_USERNAME", "MYSQL_USER", "DB_USER", default="root"),
        "password": env_first("MYSQL_PASSWORD", "DB_PASSWORD", default=""),
        "database": env_first("MYSQL_DATABASE", "MYSQL_DB", "DB_NAME", default="hmdp"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }


def active_shops() -> list[Shop]:
    conn = pymysql.connect(**mysql_config())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  s.id,
                  s.place_id,
                  s.name,
                  s.address,
                  s.comments,
                  s.score AS rating,
                  t.name AS category,
                  COALESCE(s.district, s.area) AS area
                FROM tb_shop s
                LEFT JOIN tb_shop_type t ON s.type_id = t.id
                WHERE s.is_active = 1
                ORDER BY s.id
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    shops: list[Shop] = []
    for row in rows:
        shops.append(
            Shop(
                id=int(row["id"]),
                place_id=str(row.get("place_id") or ""),
                name=str(row.get("name") or ""),
                address=str(row.get("address") or ""),
                rating=float(row["rating"]) if row.get("rating") is not None else None,
                comments=int(row["comments"]) if row.get("comments") is not None else None,
                category=str(row.get("category") or "") or None,
                area=str(row.get("area") or "") or None,
            )
        )
    return shops


def sqlite_overview() -> dict[int, dict[str, Any]]:
    if not SQLITE_DB.exists():
        return {}
    conn = sqlite3.connect(SQLITE_DB)
    try:
        cur = conn.cursor()
        cur.execute("SELECT overview_metadata FROM places WHERE overview_metadata IS NOT NULL")
        out: dict[int, dict[str, Any]] = {}
        for (raw,) in cur.fetchall():
            try:
                data = json.loads(raw) if isinstance(raw, str) else {}
                shop_id = int(data.get("shop_id") or 0)
            except Exception:
                continue
            if shop_id:
                out[shop_id] = data
        return out
    finally:
        conn.close()


def mongo_review_shop_ids() -> tuple[set[int], str | None]:
    uri = env_first("MONGO_URI", "MONGODB_URI", default="mongodb://localhost:27017")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        ids = {
            int(shop_id)
            for shop_id in client["bytebites_reviews"]["google_reviews"].distinct("shop_id")
            if shop_id is not None
        }
        client.close()
        return ids, None
    except (PyMongoError, ServerSelectionTimeoutError, OSError) as exc:
        return set(), f"{exc.__class__.__name__}: {exc}"


def media_shop_ids() -> tuple[set[int], set[int], set[int]]:
    if not MEDIA_MANIFEST.exists():
        return set(), set(), set()
    try:
        data = json.loads(MEDIA_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return set(), set(), set()
    shops_data = data.get("shops", data) if isinstance(data, dict) else {}

    all_ids: set[int] = set()
    photo_ids: set[int] = set()
    review_ids: set[int] = set()
    for raw_id, value in shops_data.items():
        try:
            shop_id = int(raw_id)
        except ValueError:
            continue
        all_ids.add(shop_id)
        if not isinstance(value, dict):
            continue
        photos = value.get("photoUrls") or value.get("galleryUrls") or value.get("photos") or value.get("coverUrl")
        if photos:
            photo_ids.add(shop_id)
        reviews = value.get("reviews")
        if isinstance(reviews, list) and reviews:
            review_ids.add(shop_id)
    return all_ids, photo_ids, review_ids


def summarize(limit: int) -> dict[str, Any]:
    shops = active_shops()
    shop_ids = {shop.id for shop in shops}
    overview = sqlite_overview()
    mongo_ids, mongo_error = mongo_review_shop_ids()
    media_ids, media_photo_ids, media_review_ids = media_shop_ids()

    overview_ids = set(overview)
    overview_photo_ids = {
        shop_id
        for shop_id, data in overview.items()
        if data.get("overview_photo_urls") or data.get("overview_cover_url")
    }
    overview_price_ids = {
        shop_id
        for shop_id, data in overview.items()
        if data.get("price_overview") or data.get("price_buckets")
    }

    missing_overview = [shop for shop in shops if shop.id not in overview_ids]
    missing_media = [shop for shop in shops if shop.id not in media_ids]
    missing_reviews = [shop for shop in shops if shop.id not in mongo_ids] if not mongo_error else []
    missing_manifest_reviews = [shop for shop in shops if shop.id not in media_review_ids]

    return {
        "shops_active": len(shops),
        "sqlite_places_rows": len(overview),
        "sqlite_overview_shops": len(overview_ids & shop_ids),
        "sqlite_overview_with_photos": len(overview_photo_ids & shop_ids),
        "sqlite_overview_with_price": len(overview_price_ids & shop_ids),
        "mongo_available": mongo_error is None,
        "mongo_error": mongo_error,
        "mongo_review_shops": len(mongo_ids & shop_ids),
        "media_manifest_shops": len(media_ids & shop_ids),
        "media_with_photos": len(media_photo_ids & shop_ids),
        "media_with_reviews": len(media_review_ids & shop_ids),
        "missing_overview_sample": [(s.id, s.name, s.area, s.category) for s in missing_overview[:limit]],
        "missing_media_sample": [(s.id, s.name, s.area, s.category) for s in missing_media[:limit]],
        "missing_reviews_sample": [(s.id, s.name, s.area, s.category) for s in missing_reviews[:limit]],
        "missing_manifest_reviews_sample": [(s.id, s.name, s.area, s.category) for s in missing_manifest_reviews[:limit]],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    load_env()
    print(json.dumps(summarize(args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
