# AI Service Context

## Scope

`ai-service-python` owns AI-assisted restaurant discovery, RAG recommendations, LINE-facing AI flows, guardrails, and AI service APIs.

## Technology

- FastAPI
- google-genai SDK（Gemini 直連：embedding、chat、function calling）
- Qdrant（向量檢索）
- tenacity（LLM 呼叫重試）+ prometheus-client（token/延遲指標）
- 自製 guardrail（`app/guardrail.py`）與 eval harness（`evals/run_eval.py`，Hit@K）

## Module Layout（依賴方向單向）

```
config.py → ranking.py → retrieval.py → agent.py → line_routes.py → main.py
```

- `config.py`：Settings、Gemini/Qdrant client、generate/call_llm、metrics
- `ranking.py`：查詢意圖解析、分類/地區/意圖過濾與排序（純函式，改這裡要跑 eval）
- `retrieval.py`：embedding 快取、Qdrant 檢索、Java 補查
- `agent.py`：agent 迴圈、工具呼叫、訂位守衛、推薦決策
- `line_routes.py`：LINE webhook、內部通知、/line/* HTML（APIRouter）
- `main.py`：app 組裝 + /api/ai/* endpoints（並 re-export 各模組名稱）

## Domain Terms

- `Semantic hit`: restaurant candidate retrieved from vector search
- `RAG recommendation`: answer grounded in indexed restaurant metadata
- `AI concierge`: assistant flow that helps users discover restaurants and move toward booking
- `Guardrail`: rule that constrains unsafe, unsupported, or off-domain AI behavior
- `LINE card`: LINE Flex or text response shown inside LINE chat

## Boundaries

- Python can recommend, summarize, and orchestrate AI flows.
- Python should not become the source of truth for booking/payment state.
- When AI output affects booking, call Java APIs and verify the returned business state.
