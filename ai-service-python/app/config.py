"""服務設定與外部 client（自 main.py 機械搬出，行為不變）。

依賴方向：config ← ranking ← retrieval ← agent ← line_routes ← main。
"""
from __future__ import annotations

import contextvars
import logging
import os

from fastapi import HTTPException
from google import genai
from google.genai.errors import ClientError, ServerError
from prometheus_client import Counter as PromCounter, Histogram
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import QdrantClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class Settings(BaseSettings):
    java_backend_url: str = "http://localhost:8081"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "shops"
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_chat_model: str = "gemini-3.1-flash-lite"
    gemini_agent_model: str = "gemini-3.1-flash-lite"
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    line_signature_verify: bool = True
    line_reply_enabled: bool = False
    line_public_web_url: str = "http://localhost:3000"
    line_background_push_enabled: bool = False
    line_internal_webhook_secret: str = ""
    line_internal_webhook_require_secret: bool = True
    line_action_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
if settings.line_action_secret and not os.getenv("LINE_ACTION_SECRET"):
    os.environ["LINE_ACTION_SECRET"] = settings.line_action_secret
if settings.line_internal_webhook_secret and not os.getenv("LINE_INTERNAL_WEBHOOK_SECRET"):
    os.environ["LINE_INTERNAL_WEBHOOK_SECRET"] = settings.line_internal_webhook_secret

_agent_auth_token: contextvars.ContextVar[str] = contextvars.ContextVar("agent_auth_token", default="")
_gemini_client: genai.Client | None = None
_qdrant_client: QdrantClient | None = None
ai_requests = PromCounter("bytebites_ai_requests_total", "AI endpoint requests", ["endpoint"])
ai_tokens = PromCounter("bytebites_ai_tokens_total", "Gemini token usage", ["model", "kind"])
ai_latency = Histogram("bytebites_ai_latency_seconds", "AI endpoint latency", ["endpoint"])
logger = logging.getLogger("bytebites.ai")


def get_gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        if not settings.gemini_api_key:
            raise HTTPException(503, "GEMINI_API_KEY not configured")
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def get_qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=settings.qdrant_url)
    return _qdrant_client


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=3, min=10, max=120),
    retry=retry_if_exception_type((ClientError, ServerError)),
)
def generate(model: str, contents, config=None):
    response = get_gemini().models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    usage = getattr(response, "usage_metadata", None)
    if usage:
        ai_tokens.labels(model=model, kind="prompt").inc(usage.prompt_token_count or 0)
        ai_tokens.labels(model=model, kind="output").inc(usage.candidates_token_count or 0)
    return response


def call_llm(prompt: str) -> str:
    try:
        response = generate(settings.gemini_chat_model, prompt)
    except ClientError as exc:
        if "not found" not in str(exc).lower() and "unsupported" not in str(exc).lower():
            raise
        response = generate("gemini-1.5-flash", prompt)
    return response.text
