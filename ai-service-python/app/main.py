import httpx
from fastapi import FastAPI, HTTPException
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    java_backend_url: str = "http://localhost:8081"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "shops"
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
app = FastAPI(title="ByteBites AI Service", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bytebites-ai"}


@app.get("/api/ai/ping-java")
async def ping_java():
    """Verify connectivity to Java backend."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{settings.java_backend_url}/api/category/list")
            return {
                "java_backend": "reachable",
                "java_status": resp.status_code,
                "java_categories_count": len(resp.json().get("data", [])),
            }
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Java backend unreachable: {exc}") from exc
