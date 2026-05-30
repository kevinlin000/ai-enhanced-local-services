# ABSA Production Design

> Derived from Stage B scaling test (10 shops, 2026-05-29).  
> Model: `gemini-3.1-flash-lite` (ABSA) + `gemini-embedding-001` (semantic verifier).

---

## 1. Cost Analysis

### Token budget (measured, 10-shop sample)

| Metric | Value |
|---|---|
| Avg input tokens / shop | 3,914 |
| Avg output tokens / shop | 1,710 |
| Max input tokens (小小樹食 敦南店) | 5,896 |
| Max output tokens (大樹先生的家) | 2,085 |

### Gemini flash-lite pricing (current)

| Token type | Price |
|---|---|
| Input | $0.075 / 1M tokens |
| Output | $0.30 / 1M tokens |

### Cost projection

| Scope | Input cost | Output cost | Total |
|---|---|---|---|
| 10 shops (measured) | $0.0029 | $0.0051 | ~$0.008 |
| 103 shops (full batch) | $0.030 | $0.053 | **~$0.083** |
| 1,000 shops (scaled) | $0.294 | $0.513 | **~$0.807** |

### Semantic verifier embedding cost

`gemini-embedding-001` runs only on char-level failures (unverified claims).  
From Stage B: avg 2.4 unverified claims/shop × 2 embeds each (claim + best chunk) = ~5 embed calls/shop.  
Gemini embedding pricing ~$0.00025 / 1K chars → negligible (<$0.001 for 103 shops).

**Total Stage C batch cost estimate: ~$0.09** (ABSA + embeddings, 103 shops).

---

## 2. Latency

### Measured (10 shops, sequential)

| Percentile | Latency |
|---|---|
| avg | 9.5s |
| p50 | 8.2s |
| p95 | ~17s |
| max | 17.9s (肉執事台北松山門市) |

### Concurrent batch strategy

- Rate limit: 10 concurrent requests (Gemini free-tier RPM = 15, paid = higher)
- 103 shops ÷ 10 concurrent = ~11 batches × 9.5s avg = **~105s total** (~2 min)
- With p95 latency overhead: budget **5 minutes** for full 103-shop batch

### Latency drivers

Long latency correlates with output token count, not input. Shops with mixed-sentiment reviews generate longer evidence arrays.  
Cap output: `max_output_tokens=2048` in production (current max observed: 2,085 — already near limit).

---

## 3. Failure Handling

### Error categories

| Error | Frequency (Stage B) | Handling |
|---|---|---|
| JSON parse failure | 0/10 (0%) | Retry once with stricter prompt; if fail → skip shop, log |
| API timeout (>30s) | 0/10 (0%) | `httpx` timeout=30s, tenacity retry 3× with exp backoff |
| Rate limit (429) | 0/10 (sequential) | tenacity: wait_random_exponential(min=2, max=30), stop_after_attempt=5 |
| Network error | 0/10 | Retry 3× then mark shop as FAILED in status table |
| Validation failure (bad schema) | 0/10 | Pydantic parse with fallback: skip malformed aspect, log aspect_id |

### Partial failure policy

- Per-shop failure → skip shop, record `status=FAILED`, continue batch
- Batch proceeds even if 20% of shops fail (acceptable for nightly refresh)
- Failed shops retried in next scheduled run

### Verifier failure policy

- v1 char-level miss → escalate to v2 semantic rescue (automatic, Stage B)
- v2 semantic miss (sim < 0.70) → mark claim as `unverified`, DO NOT surface in frontend
- 大樹先生的家 had 1 remaining unverified claim after v2 → safely suppressed

---

## 4. Refresh Strategy

### Trigger conditions (either → re-run ABSA for shop)

1. **New reviews ≥ 3** since last ABSA run (ETL pipeline increments counter on ingest)
2. **Days since last ABSA run ≥ 30** (stale signal; shop profile may drift)
3. **Manual override** via admin endpoint `POST /admin/absa/refresh/{shop_id}`

### Cache key

```
cache_key = f"absa:{shop_id}:{hash(sorted(review_texts))[:8]}"
```

Deterministic hash over review text content (not timestamps) → same reviews always hit cache even if ETL re-runs.  
Cache TTL: 7 days (Redis `SET EX 604800`).

### Scheduled batch

- **Nightly at 03:00 Taiwan time** (low traffic, Gemini quota reset)
- Query: `SELECT shop_id FROM shops WHERE days_since_absa > 30 OR new_reviews_since_absa >= 3`
- Expected scope: ~10–15 shops/night in steady state (not all 103 every night)
- Full re-index only on schema change (new aspect categories, prompt version bump)

### Prompt version control

Bump `PROMPT_VERSION` constant on any system prompt change.  
Store `prompt_version` alongside result in DB:

```sql
ALTER TABLE shop_absa_results ADD COLUMN prompt_version VARCHAR(10) NOT NULL DEFAULT 'v2.0';
```

Stale results (old `prompt_version`) queued for re-run on next nightly cycle.

---

## 5. Monitoring Metrics

### Operational metrics (Prometheus counters/gauges)

| Metric | Type | Alert threshold |
|---|---|---|
| `absa_batch_duration_seconds` | Histogram | p95 > 600s → PagerDuty |
| `absa_shop_failure_total` | Counter | > 5% batch failure rate → warning |
| `absa_token_usage_total{type="input\|output"}` | Counter | > 2× baseline → cost spike alert |
| `absa_verifier_unverified_total` | Counter | > 10% claims unverified → quality alert |
| `absa_synonym_recovered_total` | Counter | Track v2 uplift over time |
| `absa_cache_hit_total` | Counter | < 80% hit rate → investigate ETL churn |

### Quality metrics (logged to `absa_quality_log` table)

| Metric | Stage B value | Prod target |
|---|---|---|
| v1 char avg hit_rate | 0.724 | — (diagnostic only) |
| v2 semantic avg hit_rate | 0.993 | ≥ 0.95 |
| v2 F1 on gold set | 0.955 | ≥ 0.90 (re-evaluate quarterly) |
| Shops with all aspects unverified | 0/10 | 0 (block frontend display) |

### Gold set re-evaluation schedule

- Re-run `eval_verifier()` against `absa_gold_v1.json` after any verifier threshold change
- Expand gold set to 100 items before Stage C prod launch (current: 35 items, 5 shops)
- Add ≥ 1 sparse-review shop (< 5 non-empty reviews) to stress-test hallucination_risk path

### Alerting summary

```
absa_shop_failure_rate > 0.05   → Slack #ops-alerts (warning)
absa_batch_duration_p95 > 600s  → PagerDuty (critical)
absa_token_cost_daily > $1.00   → Slack #finance-alerts (warning)
absa_sem_hit_rate_7d_avg < 0.90 → Slack #ml-quality (warning)
```

---

## Known Gaps Before Production

1. **hallucination_risk never self-triggered** in any test shop (all had rich, complete reviews).  
   Add ≥ 1 sparse-review shop to test coverage before batch 103 shops.

2. **Semantic verifier threshold 0.70** calibrated on Stage B sample.  
   Re-calibrate on expanded gold set (100+ items) before production.

3. **Concurrent batch rate-limit handling** not yet implemented.  
   Add `asyncio.Semaphore(10)` around Gemini calls in Stage C batch runner.

4. **No DB schema yet** for `shop_absa_results`.  
   Stage C will define schema and write pipeline.

---

## Future Improvement: Local Sentence-Transformers for Semantic Verifier

**Root cause of Stage C quota contention:** ABSA generation (`gemini-3.1-flash-lite`) and semantic verification (`gemini-embedding-001`) share the same Gemini free-tier quota. Running 103-shop ABSA exhausts the quota; subsequent embed calls for semantic rescue all fail, falsely depressing `semantic_hit_rate`.

**Workaround (current):** Two-stage decoupling — Stage 1 writes with `char_hit_rate` only, Stage 2 runs semantic rescue as a separate job after quota recovers (~1 hour).

**Long-term fix:** Migrate semantic verifier to a **local sentence-transformers model** (e.g. `paraphrase-multilingual-mpnet-base-v2`). Benefits:
- Zero quota dependency — embed calls never rate-limit
- Stage 2 runs immediately after Stage 1, no scheduling needed
- Lower latency per embed call (no network round-trip)
- `semantic_hit_rate` filled synchronously in same batch run

**Do not implement now.** Requires adding `sentence-transformers` to pyproject.toml and re-profiling embedding quality against gold set (`absa_gold_v1.json`). Schedule as Stage D pre-work when shop count exceeds ~500 or Gemini free-tier quota becomes a recurring bottleneck.
