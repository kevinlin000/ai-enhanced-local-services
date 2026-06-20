# AI Service Context

## Scope

`ai-service-python` owns AI-assisted restaurant discovery, RAG recommendations, LINE-facing AI flows, guardrails, and AI service APIs.

## Technology

- FastAPI
- LlamaIndex
- Qdrant
- LiteLLM
- RAGAS / promptfoo where evaluation is needed

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
