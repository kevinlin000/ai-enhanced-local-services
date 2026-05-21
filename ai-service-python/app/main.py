import httpx
from fastapi import FastAPI, HTTPException
from google import genai
from google.genai.errors import ClientError, ServerError
from google.genai import types
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import QdrantClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class Settings(BaseSettings):
    java_backend_url: str = "http://localhost:8081"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "shops"
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_chat_model: str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
app = FastAPI(title="ByteBites AI Service", version="0.1.0")
_gemini_client: genai.Client | None = None
_qdrant_client: QdrantClient | None = None


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
    return get_gemini().models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )


def call_llm(prompt: str) -> str:
    try:
        response = generate(settings.gemini_chat_model, prompt)
    except ClientError as exc:
        if "not found" not in str(exc).lower() and "unsupported" not in str(exc).lower():
            raise
        response = generate("gemini-1.5-flash", prompt)
    return response.text


async def tool_search_by_mrt(station: str, radius: int = 500) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            f"{settings.java_backend_url}/api/shop/nearby-mrt/{station}",
            params={"radius": radius},
        )
        return {"shops": response.json().get("data", [])[:5]}


async def tool_semantic_search(query: str) -> dict:
    gemini = get_gemini()
    qdrant = get_qdrant()
    emb_resp = gemini.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    results = qdrant.query_points(
        collection_name=settings.qdrant_collection,
        query=emb_resp.embeddings[0].values,
        limit=5,
    ).points
    return {
        "shops": [
            {
                "name": result.payload.get("name"),
                "district": result.payload.get("district"),
                "mrt_station": result.payload.get("mrt_station"),
                "score": result.payload.get("score"),
            }
            for result in results
        ]
    }


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchHit(BaseModel):
    shop_id: int
    name: str
    district: str | None
    mrt_station: str | None
    score: float


class RecommendRequest(BaseModel):
    query: str
    top_k: int = 5


class RecommendResponse(BaseModel):
    query: str
    answer: str
    hits: list[SearchHit]


class AgentRequest(BaseModel):
    query: str


TOOLS = [
    {
        "function_declarations": [
            {
                "name": "search_shops_by_mrt",
                "description": "查詢指定捷運站附近的店家。當使用者提到特定捷運站名（如「市政府」「中山」「信義安和」）時使用。",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "station": {
                            "type": "STRING",
                            "description": "捷運站名，例如「市政府」「中山」",
                        },
                        "radius": {
                            "type": "INTEGER",
                            "description": "搜尋半徑（公尺），預設 500",
                        },
                    },
                    "required": ["station"],
                },
            },
            {
                "name": "semantic_shop_search",
                "description": "語意搜尋店家。當使用者描述抽象需求（如「想吃手搖飲」「適合約會」），用此 tool。",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING"},
                    },
                    "required": ["query"],
                },
            },
        ]
    }
]


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


@app.post("/api/ai/search")
async def semantic_search(req: SearchRequest):
    """Semantic shop search via Gemini embedding + Qdrant."""
    if not req.query.strip():
        raise HTTPException(400, "query is empty")

    gemini = get_gemini()
    qdrant = get_qdrant()

    emb_resp = gemini.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=req.query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    query_vec = emb_resp.embeddings[0].values

    results = qdrant.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vec,
        limit=req.top_k,
    ).points

    return {
        "query": req.query,
        "hits": [
            SearchHit(
                shop_id=result.payload["shop_id"],
                name=result.payload.get("name"),
                district=result.payload.get("district"),
                mrt_station=result.payload.get("mrt_station"),
                score=float(result.score),
            )
            for result in results
        ],
    }


@app.post("/api/ai/recommend")
async def recommend(req: RecommendRequest):
    """Full RAG: retrieve + LLM generate recommendation."""
    if not req.query.strip():
        raise HTTPException(400, "query is empty")

    gemini = get_gemini()
    qdrant = get_qdrant()

    emb_resp = gemini.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=req.query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    query_vec = emb_resp.embeddings[0].values

    results = qdrant.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vec,
        limit=req.top_k,
    ).points

    context_lines = []
    for index, result in enumerate(results, 1):
        payload = result.payload
        context_lines.append(
            f"{index}. {payload.get('name')} | {payload.get('district')} | "
            f"捷運{payload.get('mrt_station')}站 | 評分 {payload.get('score', 'N/A')}"
        )
    context = "\n".join(context_lines)

    prompt = f"""你是台灣在地店家推薦助手。使用者問：「{req.query}」

候選店家列表：
{context}

請用 2-3 句話自然地推薦 1-2 家最合適的店家，說明推薦理由（位置、評分等）。
不要編造資訊，只能用候選列表中的資料。用繁體中文回答。"""

    return RecommendResponse(
        query=req.query,
        answer=call_llm(prompt),
        hits=[
            SearchHit(
                shop_id=result.payload["shop_id"],
                name=result.payload.get("name"),
                district=result.payload.get("district"),
                mrt_station=result.payload.get("mrt_station"),
                score=float(result.score),
            )
            for result in results
        ],
    )


@app.post("/api/ai/agent")
async def agent(req: AgentRequest):
    """LLM with function calling - picks tool, executes, then synthesizes answer."""
    if not req.query.strip():
        raise HTTPException(400, "query is empty")

    gemini = get_gemini()

    first = generate(
        settings.gemini_chat_model,
        req.query,
        types.GenerateContentConfig(
            tools=TOOLS,
            system_instruction="你是台灣店家推薦助手。根據使用者的問題，選擇合適的 tool 查詢資料，然後用繁體中文簡潔回答。",
        ),
    )

    candidate = first.candidates[0]
    function_call = None
    for part in candidate.content.parts:
        if hasattr(part, "function_call") and part.function_call:
            function_call = part.function_call
            break

    if not function_call:
        return {"query": req.query, "answer": first.text, "tool_used": None}

    tool_name = function_call.name
    tool_args = dict(function_call.args)

    if tool_name == "search_shops_by_mrt":
        tool_result = await tool_search_by_mrt(**tool_args)
    elif tool_name == "semantic_shop_search":
        tool_result = await tool_semantic_search(**tool_args)
    else:
        raise HTTPException(500, f"unknown tool: {tool_name}")

    second = generate(
        settings.gemini_chat_model,
        [
            req.query,
            candidate.content,
            types.Content(
                role="tool",
                parts=[
                    types.Part.from_function_response(
                        name=tool_name,
                        response=tool_result,
                    )
                ],
            ),
        ],
        types.GenerateContentConfig(
            system_instruction="根據查詢結果，用 2-3 句繁體中文推薦最合適的 1-2 家店。",
        ),
    )

    return {
        "query": req.query,
        "answer": second.text,
        "tool_used": tool_name,
        "tool_args": tool_args,
        "tool_result_count": len(tool_result.get("shops", [])),
    }
