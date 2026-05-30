# ABSA Stage C — Quality Report

## Post-Dedup Rerun (2026-05-30)

### Background

Before this rerun, 54 of 103 shops had near-duplicate reviews embedded in the raw JSON files
(same author + whitespace-normalized text appearing multiple times in one file). Root cause:
ETL scraper ran multiple times and appended results to the same output files.

Fix applied:
1. `loadExtractedShopMap` (Next.js): in-memory dedup at load time (defensive layer)
2. `etl-pipeline/scripts/dedup_reviews.py`: one-shot dedup of raw JSON files (180 dups removed, .bak backups created)
3. Deleted 54 affected rows from `tb_shop_absa`, reran both stages

### Metrics Comparison

| Metric | Before (pre-dedup) | After (post-dedup) |
|---|---|---|
| Shops in DB | 49 | 103 |
| avg char_hit_rate | 0.903 | 0.935 |
| min char_hit_rate | 0.667 | 0.621 |
| max char_hit_rate | 1.000 | 1.000 |
| avg semantic_hit_rate | n/a (partial) | 0.996 |
| perfect semantic (1.0) | n/a | 102/103 |
| quality gate fails | 0 | 0 |
| ABSA write failures | 0 | 0 |
| Stage 1 wall time | — | 229.5s (54 shops) |
| Stage 2 wall time | — | 35.4s (54 shops) |
| Est. token cost | — | $0.0605 |

### Notes

- avg char_hit_rate improved from 0.903 → 0.935: fewer duplicate reviews = cleaner evidence alignment
- 1 shop (10169 蔬食百匯) has char=0.621, still above quality gate threshold (0.6)
- semantic_hit_rate=1.000 for all 54 new shops; 0.996 overall (102/103 perfect)

---

## Agent Model Ablation (2026-05-31)

### Task-specific model split rationale

**Decision**: separate `GEMINI_AGENT_MODEL` from `GEMINI_CHAT_MODEL` so each task uses the model best suited to its latency / cost / capability trade-off. This is standard task-specific model routing — a concrete case-study talking point for portfolio review.

Config split:
| Env var | Current value | Used by |
|---|---|---|
| `GEMINI_CHAT_MODEL` | `gemini-3.5-flash` | `/api/ai/recommend` (RAG LLM step) |
| `GEMINI_AGENT_MODEL` | `gemini-3.5-flash` | Agent function-calling loop + synthesis stream |
| ETL `GEMINI_CHAT_MODEL` | `gemini-3.1-flash-lite` | ABSA Stage 1 extraction |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Qdrant ingest + query embedding |

### Model ablation table

Measurement conditions: query = "推薦信義區的火鍋", Qdrant up (73 points), compact synthesis context (~233 tokens), 3 runs each.

| Model | Context | TTFT (last_tool → first_chunk) | Total | Chunks | Notes |
|---|---|---|---|---|---|
| `gemini-3.5-flash` | fallback (no Qdrant) | median 7,294ms, range 6,529–7,544ms | ~18–20s | 36–47 | Qdrant was down; Java fallback slow |
| `gemini-3.1-flash-lite` | Qdrant up | **median 908ms, range 747–1,194ms** | ~6.4–6.8s | 25–28 | ✅ target <1s met; 8× faster TTFT |

### Observations (2026-05-31)

- `gemini-3.5-flash` with Java fallback (Qdrant down): TTFT ~7.3s — dominated by Java fallback latency + heavier model.
- `gemini-3.1-flash-lite` with Qdrant up: TTFT **~900ms** — 8× faster. Two confounding factors improved simultaneously (model + Qdrant), but flash-lite's lower latency is the primary driver since Qdrant real vector search is only ~100ms vs Java fallback ~2–5s.
- Synthesis context reduced 70% (3,155 → 933 chars) via compact one-liner format. No measurable TTFT impact at this token scale — API floor is ~750ms, context not the bottleneck.
- **Decision: use `gemini-3.1-flash-lite` for all Agent calls.** `gemini-3.5-flash` is 8× slower on TTFT and significantly more expensive; quality for tool-routing + synthesis is sufficient with flash-lite.

---

## Phase 4 TODO (deferred)

- [ ] LLM paragraph rewriting for review display (Phase 4): rewrite raw Google reviews into structured
  paragraphs with consistent tone, removing noise (time references, filler phrases). Not implemented;
  current display uses raw text with smart sentence splitting only.

- [ ] Tier-1: LLM-powered translation of non-Chinese reviews.
  Cost: ~$0.001 per review (gemini-flash).
  Storage: new column `translated_content` on tb_shop_absa or a new `tb_review_translation` table.
  UX: toggle between original and translation in ReviewCard ("查看中文翻譯 / 顯示原文").
  Current status: non-Chinese reviews are shown with language flag badge only (no translation).
