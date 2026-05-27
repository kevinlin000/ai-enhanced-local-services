import argparse
import json
from pathlib import Path
import sys
import sqlite3

import pymongo
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.pipeline import _review_has_meaningful_content


def load_config(config_path: Path) -> dict:
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def prune_json(config: dict, apply: bool) -> tuple[int, int]:
    json_path = Path(config.get("json_path", "google_reviews.json"))
    if not json_path.exists():
        return 0, 0

    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return 0, 0

    kept = [doc for doc in data if _review_has_meaningful_content(doc, config)]
    dropped = len(data) - len(kept)
    if apply and dropped:
        json_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(data), dropped


def prune_mongo(config: dict, apply: bool) -> tuple[int, int]:
    mongodb = config.get("mongodb", {}) or {}
    uri = mongodb.get("uri")
    database = mongodb.get("database")
    collection_name = mongodb.get("collection")
    if not uri or not database or not collection_name:
        return 0, 0

    client = pymongo.MongoClient(uri)
    try:
        collection = client[database][collection_name]
        docs = list(collection.find({}, {"_id": 1, "review_id": 1, "description": 1, "owner_responses": 1, "user_images": 1, "sub_ratings": 1}))
        bad_ids = [doc["_id"] for doc in docs if not _review_has_meaningful_content(doc, config)]
        if apply and bad_ids:
            collection.delete_many({"_id": {"$in": bad_ids}})
        return len(docs), len(bad_ids)
    finally:
        client.close()


def _safe_json_load(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def prune_sqlite(config: dict, apply: bool) -> tuple[int, int]:
    db_path = Path(config.get("db_path", "reviews.db"))
    if not db_path.exists():
        return 0, 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT review_id, place_id, review_text, owner_responses, user_images, sub_ratings
            FROM reviews
            """
        ).fetchall()

        to_delete: list[tuple[str, str]] = []
        for row in rows:
            doc = {
                "review_id": row["review_id"],
                "description": _safe_json_load(row["review_text"], {}),
                "owner_responses": _safe_json_load(row["owner_responses"], {}),
                "user_images": _safe_json_load(row["user_images"], []),
                "sub_ratings": _safe_json_load(row["sub_ratings"], {}),
            }
            if not _review_has_meaningful_content(doc, config):
                to_delete.append((row["review_id"], row["place_id"]))

        if apply and to_delete:
            conn.executemany(
                "DELETE FROM reviews WHERE review_id = ? AND place_id = ?",
                to_delete,
            )
            conn.commit()
            conn.execute("VACUUM")

        return len(rows), len(to_delete)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    json_total, json_dropped = prune_json(config, apply=args.apply)
    mongo_total, mongo_dropped = prune_mongo(config, apply=args.apply)
    sqlite_total, sqlite_dropped = prune_sqlite(config, apply=args.apply)

    mode = "APPLY" if args.apply else "DRY_RUN"
    print(
        json.dumps(
            {
                "mode": mode,
                "json_total": json_total,
                "json_dropped": json_dropped,
                "mongo_total": mongo_total,
                "mongo_dropped": mongo_dropped,
                "sqlite_total": sqlite_total,
                "sqlite_dropped": sqlite_dropped,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
