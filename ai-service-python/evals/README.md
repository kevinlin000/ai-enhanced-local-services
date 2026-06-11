# RAG Eval Report

## Eval set

15 筆 golden queries on 103 ETL-loaded shops (post Stage 4):
- 10 basic queries (品類、店名、區域、場景)
- 5 hard cases (商務語意、抽象口味、多條件、預算 + 氛圍)

格式：JSONL with `{query, expected_shop_ids, rationale}`

## Results (2026-05-23, gemini-embedding-001 768d, Qdrant Cosine)

| Metric | Score |
|---|---|
| Hit@1 | 12/15 = 80.0% |
| Hit@3 | 14/15 = 93.3% |
| Hit@5 | 14/15 = 93.3% |

## Failure analysis

**Case 11: "跟客戶談生意的高檔餐廳"**

- Expected: 10160 (新東南海鮮), 10135 (榮榮園) — atmosphere_tags 含「商務」
- Got: 10107 (老井燒肉), 10104 (饗饗), 10106 (饗食天堂) — 都是「高檔」但非商務語意

Root cause: embed text 含 `ai_summary + atmosphere_tags`，但「商務」在這兩家的 summary 被家庭/親友聚餐語意稀釋，而高知名度的信義高檔品牌得分更高。

Improvement options:
1. Embed text 把 atmosphere_tags 重複出現 2 次，提升 tag 權重
2. Hybrid search: Qdrant dense + BM25 sparse on tags exact match
3. Two-stage: dense 撈 top-20，再以 atmosphere tag filter rerank

## How to run

```bash
cd ai-service-python
uv run python scripts/run_rag_eval.py evals/dataset.jsonl
```

## Conversation Quality Gates

`conversation_quality_cases.jsonl` defines the critical Web/LINE AI concierge flows that must not regress before a demo or release:

- vague group dining requests must ask for missing context instead of guessing
- recommendation follow-ups can create booking drafts from exact shop names
- booking drafts can be edited by natural language, including time and shop changes
- negative selections such as "不要第二間，換一家" must request more candidates, not accidentally book the rejected shop
- cuisine hard constraints must keep Taiwanese/business and Korean cuisine intent from being swallowed by noisy vector matches

Run the executable regression suite:

```bash
cd ai-service-python
uv run pytest tests/test_agent_conversation_eval.py -q
```
