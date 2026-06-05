#!/usr/bin/env python3
"""Repair MongoDB review sync from the scraper SQLite database.

Use this when a scrape wrote reviews to SQLite but MongoDB missed the write
(for example local disk pressure or a stopped MongoDB process). Re-running the
scrape may still skip MongoDB because the SQLite rows are now unchanged; this
script intentionally performs a full upsert for selected shops.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pymongo import MongoClient, UpdateOne

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.review_db import ReviewDB  # noqa: E402
from modules.scraper import GoogleReviewsScraper  # noqa: E402


@dataclass(frozen=True)
class Target:
    shop_id: int
    name: str | None = None


def parse_targets(path: Path) -> list[Target]:
    targets: list[Target] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 2)
        try:
            shop_id = int(parts[0])
        except ValueError as exc:
            raise SystemExit(f"invalid shop_id at {path}:{line_no}: {raw_line}") from exc
        targets.append(Target(shop_id=shop_id, name=parts[1].strip() if len(parts) > 1 else None))
    return targets


def unique_targets(targets: Iterable[Target]) -> list[Target]:
    seen: set[int] = set()
    out: list[Target] = []
    for target in targets:
        if target.shop_id in seen:
            continue
        seen.add(target.shop_id)
        out.append(target)
    return out


def load_shop_place_index(db: ReviewDB) -> dict[int, list[dict]]:
    rows = db.backend.fetchall(
        "SELECT place_id, place_name, overview_metadata FROM places "
        "WHERE overview_metadata IS NOT NULL AND overview_metadata != ''"
    )
    index: dict[int, list[dict]] = {}
    for row in rows:
        try:
            metadata = json.loads(row["overview_metadata"] or "{}")
            shop_id = int(metadata.get("shop_id") or 0)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if shop_id:
            index.setdefault(shop_id, []).append(dict(row))
    return index


def build_mongo_docs(db: ReviewDB, target: Target, place: dict) -> dict[str, dict]:
    docs: dict[str, dict] = {}
    now = datetime.now(timezone.utc)
    company = target.name or (place.get("place_name") or "").replace(" - Google 地圖", "").strip()
    for row in db.get_reviews(place["place_id"], include_deleted=True):
        doc = GoogleReviewsScraper._db_review_to_legacy(row)
        review_id = doc.get("review_id")
        if not review_id:
            continue
        doc["shop_id"] = target.shop_id
        doc["company"] = company
        doc["sync_source"] = "sqlite_mongo_repair"
        doc["mongo_repaired_at"] = now
        docs[review_id] = doc
    return docs


def upsert_docs(collection, docs: dict[str, dict]) -> tuple[int, int]:
    if not docs:
        return (0, 0)
    operations = [
        UpdateOne({"review_id": doc["review_id"]}, {"$set": doc}, upsert=True)
        for doc in docs.values()
    ]
    result = collection.bulk_write(operations, ordered=False)
    return (result.upserted_count, result.modified_count)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="target file: shop_id|name|address")
    parser.add_argument("--shop-id", type=int, action="append", default=[], help="shop id to repair")
    parser.add_argument("--db-path", type=Path, default=ROOT / "reviews.db")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    parser.add_argument("--mongo-db", default="bytebites_reviews")
    parser.add_argument("--mongo-collection", default="google_reviews")
    args = parser.parse_args()

    targets: list[Target] = []
    if args.input:
        targets.extend(parse_targets(args.input))
    targets.extend(Target(shop_id=shop_id) for shop_id in args.shop_id)
    targets = unique_targets(targets)
    if not targets:
        raise SystemExit("provide --input or --shop-id")

    db = ReviewDB(str(args.db_path))
    client = MongoClient(args.mongo_uri, connectTimeoutMS=5000)
    client.admin.command("ping")
    collection = client[args.mongo_db][args.mongo_collection]
    index = load_shop_place_index(db)

    failures: list[int] = []
    for target in targets:
        places = index.get(target.shop_id, [])
        if not places:
            print(f"{target.shop_id}: no SQLite place with matching overview_metadata.shop_id")
            failures.append(target.shop_id)
            continue

        docs: dict[str, dict] = {}
        for place in places:
            docs.update(build_mongo_docs(db, target, place))

        before = collection.count_documents({"shop_id": target.shop_id})
        upserted, modified = upsert_docs(collection, docs)
        after = collection.count_documents({"shop_id": target.shop_id})
        print(
            f"{target.shop_id}: sqlite_reviews={len(docs)} mongo_before={before} "
            f"upserted={upserted} modified={modified} mongo_after={after}"
        )
        if docs and after == 0:
            failures.append(target.shop_id)

    db.close()
    client.close()
    if failures:
        print("failed_shop_ids=" + ",".join(str(shop_id) for shop_id in failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
