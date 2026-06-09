"""
One-shot ingest: pull all shops from Java backend,
embed shop core fields + AI metadata via Gemini,
upsert into Qdrant.
"""

import asyncio
import json

import httpx
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from tenacity import retry, stop_after_attempt, wait_exponential

from app.main import settings
from app.taxonomy import get_slug_by_type_id


def _category_slug_for_type(type_id: int | None) -> str | None:
    if type_id is None:
        return None
    try:
        return get_slug_by_type_id(int(type_id))
    except (TypeError, ValueError):
        return None


def _parse_json_list(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, list):
                return [str(item) for item in loaded if item]
        except Exception:
            return [raw]
    return []


def get_embedding_text(shop: dict) -> str:
    parts = [
        shop.get("name", ""),
        f"分類: {shop.get('categoryName', '')}" if shop.get("categoryName") else "",
        f"類別代碼: {shop.get('categorySlug', '')}" if shop.get("categorySlug") else "",
        shop.get("address", ""),
        shop.get("district", ""),
        shop.get("mrtStation", ""),
        f"價位: NT$ {shop.get('avgPrice')}" if shop.get("avgPrice") else "",
        shop.get("aiSummary", ""),
        f"招牌菜: {', '.join(_parse_json_list(shop.get('signatureDishes')))}" if shop.get("signatureDishes") else "",
        f"氛圍: {', '.join(_parse_json_list(shop.get('atmosphereTags')))}" if shop.get("atmosphereTags") else "",
        f"預約難度: {shop.get('bookingDifficulty')}" if shop.get("bookingDifficulty") else "",
        f"參考價位區間: {shop.get('pricePerPerson')}" if shop.get("pricePerPerson") else "",
    ]
    return " | ".join(part for part in parts if part)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def embed(client: genai.Client, text: str, dim: int = 768) -> list[float]:
    """Use Gemini embedding. Output dim default 768 (cheaper, faster than 3072)."""
    resp = client.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=dim,
        ),
    )
    return resp.embeddings[0].values


async def fetch_all_shops() -> list[dict]:
    shops = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        category_resp = await client.get(f"{settings.java_backend_url}/api/category/list")
        categories = category_resp.json().get("data", [])
        for category in categories:
            slug = category.get("slug")
            if not slug:
                continue
            resp = await client.get(
                f"{settings.java_backend_url}/api/category/{slug}/shops",
                params={"page": 1, "size": 50},
            )
            shops.extend(resp.json().get("data", []))
        deduped: dict[int, dict] = {}
        for shop in shops:
            deduped[shop["id"]] = shop

        enriched = []
        for shop in deduped.values():
            category_slug = _category_slug_for_type(shop.get("typeId"))
            try:
                meta_resp = await client.get(f"{settings.java_backend_url}/api/shop/{shop['id']}/ai-metadata")
                metadata = meta_resp.json().get("data") if meta_resp.status_code == 200 else None
            except Exception:
                metadata = None
            enriched.append(
                {
                    **shop,
                    "categoryName": category_slug or shop.get("typeName") or shop.get("categoryName"),
                    "categorySlug": category_slug,
                    "aiSummary": metadata.get("aiSummary") if metadata else None,
                    "signatureDishes": metadata.get("signatureDishes") if metadata else None,
                    "atmosphereTags": metadata.get("atmosphereTags") if metadata else None,
                    "bookingDifficulty": metadata.get("bookingDifficulty") if metadata else None,
                    "pricePerPerson": metadata.get("pricePerPerson") if metadata else None,
                }
            )
    return enriched


def ensure_collection(client: QdrantClient, name: str, dim: int):
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"created collection: {name} (dim={dim})")
    else:
        print(f"collection exists: {name}")


async def run():
    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY not set in .env")

    embed_client = genai.Client(api_key=settings.gemini_api_key)
    qdrant_client = QdrantClient(url=settings.qdrant_url)

    shops = await fetch_all_shops()
    print(f"fetched {len(shops)} shops")

    if not shops:
        raise SystemExit("no shops fetched, abort")

    sample_vec = embed(embed_client, get_embedding_text(shops[0]))
    dim = len(sample_vec)
    ensure_collection(qdrant_client, settings.qdrant_collection, dim)

    points = []
    for shop in shops:
        text = get_embedding_text(shop)
        vec = embed(embed_client, text)
        points.append(
            PointStruct(
                id=shop["id"],
                vector=vec,
                payload={
                    "shop_id": shop["id"],
                    "name": shop.get("name"),
                    "district": shop.get("district"),
                    "mrt_station": shop.get("mrtStation"),
                    "type_id": shop.get("typeId"),
                    "category": shop.get("categoryName"),
                    "category_slug": shop.get("categorySlug"),
                    "price_range": shop.get("priceRange"),
                    "avg_price": shop.get("avgPrice"),
                    "score": shop.get("score"),
                    "ai_summary": shop.get("aiSummary"),
                    "signature_dishes": _parse_json_list(shop.get("signatureDishes")),
                    "atmosphere_tags": _parse_json_list(shop.get("atmosphereTags")),
                    "booking_difficulty": shop.get("bookingDifficulty"),
                    "price_per_person": shop.get("pricePerPerson"),
                    "embed_text": text,
                },
            )
        )

    qdrant_client.upsert(collection_name=settings.qdrant_collection, points=points)
    print(f"upserted {len(points)} points")


if __name__ == "__main__":
    asyncio.run(run())
