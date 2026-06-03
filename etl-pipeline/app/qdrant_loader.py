import os
import json
import time
import argparse
from pathlib import Path
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance
import pymysql
import structlog

log = structlog.get_logger()

EMBEDDING_DIM = 768
COLLECTION = os.getenv("QDRANT_COLLECTION", "bytebites_shops")
DEFAULT_EMBED_SLEEP_SECONDS = float(os.getenv("QDRANT_EMBED_SLEEP_SECONDS", "0.3"))


def _load_category_slugs() -> dict[int, str]:
    taxonomy_path = Path(__file__).resolve().parents[2] / "shared" / "taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text())
    return {category["type_id"]: category["slug"] for category in taxonomy.get("categories", [])}


CATEGORY_SLUG_BY_TYPE_ID = _load_category_slugs()


def fetch_shops_from_db():
    """從 MySQL 撈所有 active 店家含 ai_metadata"""
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
    )
    sql = """
    SELECT
        s.id, s.name, s.district, s.address, s.score, s.comments, s.avg_price,
        s.x, s.y, s.type_id, t.name as category_name,
        m.ai_summary, m.signature_dishes, m.atmosphere_tags,
        m.booking_difficulty, m.price_per_person
    FROM tb_shop s
    JOIN tb_shop_type t ON s.type_id = t.id
    LEFT JOIN tb_shop_ai_metadata m ON s.id = m.shop_id
    WHERE s.source='google_places' AND s.is_active=1
    """
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    conn.close()
    return rows


def build_embed_text(shop):
    """拼接給 embedding 的文字"""
    parts = [shop["name"]]
    if shop.get("category_name"):
        parts.append(f"分類: {shop['category_name']}")
    if shop.get("ai_summary"):
        parts.append(shop["ai_summary"])
    if shop.get("signature_dishes"):
        dishes = json.loads(shop["signature_dishes"]) if isinstance(shop["signature_dishes"], str) else shop["signature_dishes"]
        if dishes:
            parts.append(f"招牌: {', '.join(dishes[:5])}")
    if shop.get("atmosphere_tags"):
        tags = json.loads(shop["atmosphere_tags"]) if isinstance(shop["atmosphere_tags"], str) else shop["atmosphere_tags"]
        if tags:
            parts.append(f"氛圍: {', '.join(tags)}")
    if shop.get("district"):
        parts.append(shop["district"])
    return " | ".join(parts)


def embed_text(client, text):
    """打 Gemini embedding、768 維"""
    result = client.models.embed_content(
        model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBEDDING_DIM,
        ),
    )
    return result.embeddings[0].values


def main(embed_sleep_seconds: float = DEFAULT_EMBED_SLEEP_SECONDS):
    shops = fetch_shops_from_db()
    log.info("fetched_from_db", count=len(shops), embed_sleep_seconds=embed_sleep_seconds)

    gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))

    # 1. 重建 collection
    try:
        qdrant.delete_collection(COLLECTION)
        log.info("deleted_old_collection", name=COLLECTION)
    except Exception as e:
        log.info("no_old_collection", error=str(e))

    qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    log.info("created_collection", name=COLLECTION)

    # 2. embed + upsert
    points = []
    for i, shop in enumerate(shops):
        text = build_embed_text(shop)
        try:
            vector = embed_text(gemini, text)
            payload = {
                "shop_id": shop["id"],
                "name": shop["name"],
                "district": shop["district"],
                "category": shop["category_name"],
                "category_slug": CATEGORY_SLUG_BY_TYPE_ID.get(shop["type_id"]),
                "type_id": shop["type_id"],
                "score": shop["score"],
                "avg_price": shop["avg_price"],
                "lat": shop["y"],
                "lng": shop["x"],
                "booking_difficulty": shop.get("booking_difficulty"),
            }
            points.append(PointStruct(id=shop["id"], vector=vector, payload=payload))
            log.info("embedded", idx=i+1, total=len(shops), name=shop["name"], text_preview=text[:80])
            if embed_sleep_seconds > 0:
                time.sleep(embed_sleep_seconds)
        except Exception as e:
            log.error("embed_failed", name=shop["name"], error=str(e))

    # 3. 批次 upsert
    if points:
        qdrant.upsert(collection_name=COLLECTION, points=points)
        log.info("upserted", count=len(points))

    # 4. 驗證
    info = qdrant.get_collection(COLLECTION)
    log.info("collection_info", points_count=info.points_count)


def sync_payloads_only():
    """Update Qdrant filter payloads without re-embedding, useful after metadata fixes."""
    shops = fetch_shops_from_db()
    log.info("fetched_from_db_for_payload_sync", count=len(shops))

    qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    synced = 0

    for shop in shops:
        payload = {
            "shop_id": shop["id"],
            "name": shop["name"],
            "district": shop["district"],
            "category": shop["category_name"],
            "category_slug": CATEGORY_SLUG_BY_TYPE_ID.get(shop["type_id"]),
            "type_id": shop["type_id"],
            "score": shop["score"],
            "avg_price": shop["avg_price"],
            "lat": shop["y"],
            "lng": shop["x"],
            "booking_difficulty": shop.get("booking_difficulty"),
        }
        qdrant.set_payload(collection_name=COLLECTION, payload=payload, points=[shop["id"]])
        synced += 1
        log.info("payload_synced", idx=synced, total=len(shops), shop_id=shop["id"], name=shop["name"])

    info = qdrant.get_collection(COLLECTION)
    log.info("payload_sync_done", synced=synced, points_count=info.points_count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-payloads", action="store_true", help="sync Qdrant payload metadata without re-embedding")
    parser.add_argument(
        "--embed-sleep-seconds",
        type=float,
        default=DEFAULT_EMBED_SLEEP_SECONDS,
        help="delay between Gemini embedding calls during full rebuild",
    )
    args = parser.parse_args()

    if args.sync_payloads:
        sync_payloads_only()
    else:
        main(embed_sleep_seconds=args.embed_sleep_seconds)
