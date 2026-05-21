"""
One-shot ingest: pull all shops from Java backend,
embed name + area + address + district + mrt_station via Gemini,
upsert into Qdrant.
"""

import asyncio

import httpx
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from tenacity import retry, stop_after_attempt, wait_exponential

from app.main import settings


def get_embedding_text(shop: dict) -> str:
    parts = [
        shop.get("name", ""),
        shop.get("area", ""),
        shop.get("address", ""),
        shop.get("district", ""),
        shop.get("mrtStation", ""),
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
    seen = {}
    for shop in shops:
        seen[shop["id"]] = shop
    return list(seen.values())


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
                    "price_range": shop.get("priceRange"),
                    "score": shop.get("score"),
                    "embed_text": text,
                },
            )
        )

    qdrant_client.upsert(collection_name=settings.qdrant_collection, points=points)
    print(f"upserted {len(points)} points")


if __name__ == "__main__":
    asyncio.run(run())
