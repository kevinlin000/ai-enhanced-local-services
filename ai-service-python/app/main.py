import httpx
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from app.guardrail import GuardrailViolation, check_input, filter_output
from google import genai
from google.genai.errors import ClientError, ServerError
from google.genai import types
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from prometheus_client import CONTENT_TYPE_LATEST, Counter as PromCounter, Histogram, generate_latest
from qdrant_client import QdrantClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class Settings(BaseSettings):
    java_backend_url: str = "http://localhost:8081"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "shops"
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_chat_model: str = "gemini-3.1-flash-lite"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
app = FastAPI(title="ByteBites AI Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
_gemini_client: genai.Client | None = None
_qdrant_client: QdrantClient | None = None
ai_requests = PromCounter("bytebites_ai_requests_total", "AI endpoint requests", ["endpoint"])
ai_tokens = PromCounter("bytebites_ai_tokens_total", "Gemini token usage", ["model", "kind"])
ai_latency = Histogram("bytebites_ai_latency_seconds", "AI endpoint latency", ["endpoint"])


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


async def _fetch_hot_seat_vouchers(shop_ids: list[int]) -> dict[int, list]:
    """Return {shop_id: [{id, title, pay_value, actual_value, stock}]}. N+1 ok for demo."""
    out: dict[int, list] = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for sid in shop_ids:
            try:
                r = await client.get(f"{settings.java_backend_url}/api/shop/{sid}/hot-seat-vouchers")
                out[sid] = r.json().get("data", []) if r.status_code == 200 else []
            except Exception:
                out[sid] = []
    return out


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

    hits = [
        {
            "shop_id": r.payload.get("shop_id"),
            "name": r.payload.get("name"),
            "district": r.payload.get("district"),
            "mrt_station": r.payload.get("mrt_station"),
            "score": r.payload.get("score"),
        }
        for r in results
    ]

    shop_ids = [h["shop_id"] for h in hits if h["shop_id"]]
    voucher_map = await _fetch_hot_seat_vouchers(shop_ids)
    for h in hits:
        h["hot_seat_vouchers"] = voucher_map.get(h["shop_id"], [])

    return {"shops": hits}


async def tool_create_hot_seat_order(voucher_id: int) -> dict:
    """Call Java seckill endpoint with X-Demo-Mode header."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{settings.java_backend_url}/voucher-order/seckill/{voucher_id}",
            headers={"X-Demo-Mode": "true"},
        )
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}", "body": r.text[:200]}
    data = r.json()
    if not data.get("success"):
        return {"success": False, "error": data.get("errorMsg", "unknown")}
    return {
        "success": True,
        "voucher_order_id": data.get("data"),
        "message": "已為您搶到熱座 voucher，可在「我的訂單」查看",
    }


TOOL_DISPATCH = {
    "search_shops_by_mrt": tool_search_by_mrt,
    "semantic_shop_search": tool_semantic_search,
    "create_hot_seat_order": tool_create_hot_seat_order,
}

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
                "description": "語意搜尋店家。當使用者描述抽象需求（如「想吃手搖飲」「適合約會」「有沒有秒殺優惠」），用此 tool。回應含 hot_seat_vouchers 欄位。",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "create_hot_seat_order",
                "description": """為用戶搶熱座（秒殺）voucher。當用戶明確說想訂位、想搶位、想下訂某個 voucher 時呼叫。
回應含 voucher_order_id。僅支援已啟動秒殺的 voucher。
若用戶尚未指定 voucher_id，應先呼叫 semantic_shop_search 找店，再從回應的 hot_seat_vouchers 挑一個。""",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "voucher_id": {
                            "type": "INTEGER",
                            "description": "秒殺 voucher ID（從 search 結果 hot_seat_vouchers 取得，不要瞎猜）",
                        },
                    },
                    "required": ["voucher_id"],
                },
            },
        ]
    }
]

AGENT_SYSTEM_PROMPT = """你是台灣店家推薦助手。根據使用者的問題，選擇合適的 tool 查詢資料，然後用繁體中文簡潔回答。

訂位規則：
- 當用戶說「幫我訂」「想訂位」「幫我搶」「搶位」，呼叫 create_hot_seat_order
- 不要主動下單，除非用戶明確要訂
- 若不知道 voucher_id，先呼叫 semantic_shop_search 找到 hot_seat_vouchers，再取其中一個 id
- 訂單成功後，回應要包含 voucher_order_id，並提示用戶到「我的訂單」查看
- 一個 query 最多訂 1 個 voucher，不要一次訂多個"""


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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bytebites-ai"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
    try:
        check_input(req.query)
    except GuardrailViolation as exc:
        raise HTTPException(400, f"input rejected: {exc}") from exc

    ai_requests.labels(endpoint="search").inc()
    with ai_latency.labels(endpoint="search").time():
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
    try:
        check_input(req.query)
    except GuardrailViolation as exc:
        raise HTTPException(400, f"input rejected: {exc}") from exc

    ai_requests.labels(endpoint="recommend").inc()
    with ai_latency.labels(endpoint="recommend").time():
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

        answer = call_llm(prompt)

    return RecommendResponse(
        query=req.query,
        answer=filter_output(answer),
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
    """Multi-turn function calling agent. Loops up to 3 tool calls before synthesizing."""
    try:
        check_input(req.query)
    except GuardrailViolation as exc:
        raise HTTPException(400, f"input rejected: {exc}") from exc

    ai_requests.labels(endpoint="agent").inc()
    with ai_latency.labels(endpoint="agent").time():
        contents: list = [req.query]
        tools_used: list[str] = []
        last_tool_result: dict = {}

        for _ in range(3):
            response = generate(
                settings.gemini_chat_model,
                contents,
                types.GenerateContentConfig(
                    tools=TOOLS,
                    system_instruction=AGENT_SYSTEM_PROMPT,
                ),
            )

            candidate = response.candidates[0]
            function_call = None
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    function_call = part.function_call
                    break

            if not function_call:
                return {
                    "query": req.query,
                    "answer": filter_output(response.text),
                    "tools_used": tools_used,
                    "tool_result": last_tool_result,
                }

            tool_name = function_call.name
            tool_args = dict(function_call.args)

            tool_fn = TOOL_DISPATCH.get(tool_name)
            if tool_fn is None:
                raise HTTPException(500, f"unknown tool: {tool_name}")

            tool_result = await tool_fn(**tool_args)
            tools_used.append(tool_name)
            last_tool_result = tool_result

            contents.append(candidate.content)
            contents.append(
                types.Content(
                    role="tool",
                    parts=[
                        types.Part.from_function_response(
                            name=tool_name,
                            response=tool_result,
                        )
                    ],
                )
            )

        # Max iterations reached — synthesize without tools
        final = generate(
            settings.gemini_chat_model,
            contents,
            types.GenerateContentConfig(
                system_instruction="根據以上工具查詢結果，用 2-3 句繁體中文給出最終回答。",
            ),
        )

    return {
        "query": req.query,
        "answer": filter_output(final.text),
        "tools_used": tools_used,
        "tool_result": last_tool_result,
    }
