#!/usr/bin/env python3
"""
ABSA Stage C — Stage 1 of 2: batch 103 shops, write to tb_shop_absa with char-level verification only.

Stage 1 (this script): ABSA generation + verify_v1 (char, no API) + DB write if char_hit >= 0.60.
Stage 2 (absa_stage_c_semantic.py): reads rows where semantic_hit_rate IS NULL, runs verify_v2,
    updates semantic_hit_rate / synonym_recovered / unverified_count.

Pre-conditions (run before this script):
  - V19 migration applied (tb_shop_absa exists)
  - backup_pre_c2_*.sql dumped to docs/_internal/

Failure policy (per production_design.md):
  - < MIN_REVIEWS reviews → SKIP, log reason
  - LLM returns invalid JSON → SKIP, log reason
  - source_review_ids out of range → strip invalid ids, log, still write
  - char_hit_rate < QUALITY_GATE → count failures
  - > 10% of shops fail quality gate → STOP, report, no write for those shops

Usage: uv run python -u scripts/absa_stage_c_batch.py
"""
import asyncio
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pymysql
import pymysql.cursors

from google import genai
from google.genai import errors as genai_errors
import tenacity

# ── config ─────────────────────────────────────────────────────────────────────
MIN_REVIEWS          = 5
CONCURRENCY          = 20     # gemini-3.5-flash Tier 1 → high RPM, 20 concurrent safe
QUALITY_GATE_HIT     = 0.60   # char_hit_rate threshold (char undercounts due to synonyms)
QUALITY_GATE_MAX_PCT = 0.10   # max fraction of shops allowed below gate before STOP
PROMPT_VERSION       = "v2.1" # bumped: model changed to gemini-3.5-flash (prompt text unchanged)

# ── cost tracking ────────────────────────────────────────────────────────────
# gemini-3.5-flash approximate pricing (verify in Cloud Console before production)
COST_IN_PER_1M  = 0.075   # USD per 1M input tokens
COST_OUT_PER_1M = 0.30    # USD per 1M output tokens

# ── env ────────────────────────────────────────────────────────────────────────
_env: dict[str, str] = {}
for _line in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in _line and not _line.startswith("#"):
        k, _, v = _line.partition("=")
        _env[k.strip()] = v.strip()

API_KEY     = _env.get("GEMINI_API_KEY", "")
CHAT_MODEL  = _env.get("GEMINI_CHAT_MODEL", "gemini-3.5-flash")
EMBED_MODEL = "gemini-embedding-2"

DB_CONFIG = {
    "host":        "127.0.0.1",
    "port":        3306,
    "user":        "root",
    "password":    "password",
    "database":    "hmdp",
    "charset":     "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# ── logging ─────────────────────────────────────────────────────────────────────
_log: list[dict] = []

def log(event: str, shop_id: int, detail: str) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "event": event,
             "shop_id": shop_id, "detail": detail}
    _log.append(entry)
    print(f"  [LOG] {event} shop={shop_id}: {detail[:120]}")

# ── ETL data ───────────────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).resolve().parent.parent.parent / "etl-pipeline" / "data" / "raw"
shop_map: dict[int, dict] = {}
for _f in sorted(RAW_DIR.glob("places_extracted_*.json")):
    for _s in json.loads(_f.read_text()).get("shops", []):
        sid = _s.get("shop_id")
        if sid:
            shop_map[sid] = _s

ACTIVE_IDS = sorted(shop_map.keys())  # 103 shops

def load_reviews(shop_id: int) -> list[dict]:
    shop = shop_map.get(shop_id)
    if not shop:
        return []
    return [
        {"idx": i, "rating": float(r.get("rating") or 0), "text": (r.get("text") or "").strip()}
        for i, r in enumerate(shop.get("reviews", []))
        if (r.get("text") or "").strip()
    ]

# ── ABSA prompt (v2.0, unchanged) ──────────────────────────────────────────────
ABSA_SYSTEM = """\
你是一個專業的餐廳評論分析師，任務是對單一餐廳的評論進行 aspect-based sentiment analysis (ABSA)。

【任務】
讀完所有評論後，針對四個 aspect（dishes / service / environment / price）各輸出一個結構化分析。

【步驟，依序執行】
1. 完整讀完所有評論，標記每則評論對每個 aspect 的提及（內部步驟，不輸出）。
2. 對每個 aspect，找出至少 2 則明確提及才能輸出；不足則 confidence=low，evidence 陣列為空。
3. 撰寫 summary 時：
   a. 正面與負面的細節度必須對等。若有 5 則負面細節，也要努力找出 5 則正面細節並反映。
   b. 若評論中提到具體菜名、做法、價格數字、空間元素，務必納入 summary。
   c. 禁止使用通用句型，例如「N 則評論對 X 有具體描述」「整體體驗評分的一部分」等樣板語。
   d. 禁止逐字引用評論原文（版權）；用自己的話歸納。
   e. summary 必須是「只適用於這家店」的描述，換到別家店會明顯不通。
4. 每個 aspect 分別列出 positive_evidence 和 negative_evidence，各自帶 source_review_ids 與 concrete_terms。
5. 完成後，做自我驗證：對每個 aspect 的 summary，逐句檢查能否在 source_review_ids 對應評論中找到支撐；\
若有任何一句找不到，標為 hallucination_risk=true，並在 hallucination_note 說明哪句沒找到支撐。

【輸出格式 — 嚴格 JSON，禁止前後加任何文字或 markdown 圍欄】
{
  "shop_id": <int>,
  "review_count_total": <int>,
  "review_count_analyzed": <int>,
  "aspects": [
    {
      "aspect": "dishes",
      "summary": "<針對這家店的具體描述>",
      "sentiment": "positive|negative|mixed|neutral",
      "confidence": "high|medium|low",
      "confidence_reason": "<說明>",
      "mention_count": <int>,
      "positive_evidence": [{"claim":"","source_review_ids":[],"concrete_terms":[]}],
      "negative_evidence": [{"claim":"","source_review_ids":[],"concrete_terms":[]}],
      "hallucination_risk": false,
      "hallucination_note": ""
    }
  ],
  "meta": {"model": "", "generated_at": "", "prompt_version": "v2.1"}
}

評論索引從 0 開始。四個 aspect 全部輸出。若整家店評論幾乎全正面，positive_evidence 仍需詳細列出。"""


def build_absa_prompt(shop_id: int, reviews: list[dict]) -> str:
    shop = shop_map.get(shop_id, {})
    name = shop.get("display_name", f"shop_{shop_id}")
    block = "\n".join(f"[{r['idx']}] {r['rating']:.0f}★  {r['text'][:400]}" for r in reviews)
    return (
        ABSA_SYSTEM
        + f"\n\n以下是「{name}」(shop_id={shop_id}) 的 {len(reviews)} 則評論：\n\n"
        + block
        + "\n\n分析 dishes、service、environment、price 四個面向，輸出 JSON。"
    )

# ── LLM helpers ────────────────────────────────────────────────────────────────
_client: genai.Client | None = None
def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=API_KEY)
    return _client


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_random_exponential(min=1, max=10),
    retry=tenacity.retry_if_exception_type((genai_errors.ClientError, genai_errors.ServerError)),
)
def _llm_call(prompt: str) -> tuple[str, int, int]:
    resp = get_client().models.generate_content(model=CHAT_MODEL, contents=prompt)
    u = getattr(resp, "usage_metadata", None)
    return resp.text, getattr(u, "prompt_token_count", 0) or 0, getattr(u, "candidates_token_count", 0) or 0


def call_absa(shop_id: int, reviews: list[dict]) -> tuple[dict, float, int, int]:
    prompt = build_absa_prompt(shop_id, reviews)
    t0 = time.time()
    raw, in_tok, out_tok = _llm_call(prompt)
    latency = time.time() - t0
    clean = raw.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```[a-z]*\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean)
    return json.loads(clean.strip()), latency, in_tok, out_tok

# ── embedding + cosine ─────────────────────────────────────────────────────────
_embed_cache: dict[str, list[float]] = {}


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_random_exponential(min=1, max=10),
    retry=tenacity.retry_if_exception_type((genai_errors.ClientError, genai_errors.ServerError)),
)
def embed(text: str) -> list[float]:
    key = text[:120]
    if key in _embed_cache:
        return _embed_cache[key]
    resp = get_client().models.embed_content(model=EMBED_MODEL, contents=text)
    vec = resp.embeddings[0].values
    _embed_cache[key] = vec
    return vec


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def sentence_chunks(text: str, min_len: int = 8) -> list[str]:
    return [p.strip() for p in re.split(r"[。！？\n；]", text) if len(p.strip()) >= min_len]

# ── verifier v1 ─────────────────────────────────────────────────────────────────
def verify_v1(aspects: list[dict], reviews: list[dict]) -> dict:
    rev_txt = {r["idx"]: r["text"].lower() for r in reviews}
    total = hits = verified = unverified = 0
    unverified_details: list[dict] = []
    for asp in aspects:
        for pol, evs in [("pos", asp.get("positive_evidence", [])),
                         ("neg", asp.get("negative_evidence", []))]:
            for ev in evs:
                combined = " ".join(rev_txt.get(i, "") for i in ev.get("source_review_ids", []))
                terms = ev.get("concrete_terms", [])
                h = sum(1 for t in terms if t.lower() in combined)
                total += len(terms); hits += h
                rate = h / len(terms) if terms else 1.0
                if rate < 0.5:
                    unverified += 1
                    unverified_details.append({
                        "aspect": asp["aspect"], "polarity": pol,
                        "claim": ev.get("claim", "")[:80], "char_hit_rate": round(rate, 2),
                        "missing_terms": [t for t in terms if t.lower() not in combined],
                    })
                else:
                    verified += 1
    return {"char_hit_rate": round(hits / total, 3) if total else 1.0,
            "verified": verified, "unverified": unverified,
            "unverified_details": unverified_details}


# ── verifier v2 (semantic rescue, threshold=0.55) ──────────────────────────────
SEM_THRESHOLD = 0.55

def verify_v2(aspects: list[dict], reviews: list[dict], shop_id: int) -> dict:
    v1 = verify_v1(aspects, reviews)
    rev_txt = {r["idx"]: r["text"] for r in reviews}
    recovered = 0
    still_unver: list[dict] = []

    for ud in v1["unverified_details"]:
        asp_obj = next((a for a in aspects if a["aspect"] == ud["aspect"]), None)
        if not asp_obj:
            still_unver.append(ud); continue

        pol_key = "positive_evidence" if ud["polarity"] == "pos" else "negative_evidence"
        ev_obj  = next(
            (e for e in asp_obj.get(pol_key, []) if e.get("claim", "")[:80] == ud["claim"]),
            None,
        )
        if not ev_obj:
            still_unver.append(ud); continue

        claim = ev_obj.get("claim", "")
        src_txts = [rev_txt.get(i, "") for i in ev_obj.get("source_review_ids", []) if i in rev_txt]

        try:
            claim_emb = embed(claim)
        except Exception as exc:
            log("embed_error", shop_id, f"claim embed failed: {exc}")
            still_unver.append(ud); continue

        best = 0.0
        for src in src_txts:
            for chunk in (sentence_chunks(src) or [src[:200]]):
                try:
                    sim = cosine(claim_emb, embed(chunk))
                except Exception:
                    continue
                if sim > best:
                    best = sim

        if best >= SEM_THRESHOLD:
            recovered += 1
        else:
            still_unver.append({**ud, "sem_max_sim": round(best, 3)})

    total_ev = v1["verified"] + v1["unverified"]
    new_ver  = v1["verified"] + recovered
    sem_hit  = round(new_ver / total_ev, 3) if total_ev else 1.0
    return {
        "char_hit_rate":          v1["char_hit_rate"],
        "semantic_hit_rate":      sem_hit,
        "synonym_recovered_count": recovered,
        "unverified_count":       len(still_unver),
        "remaining_unverified":   still_unver,
    }

# ── validate source_review_ids in-place ────────────────────────────────────────
def sanitize_source_ids(aspects: list[dict], valid_idxs: set[int], shop_id: int) -> list[dict]:
    """Strip out-of-range source_review_ids from every evidence entry. Log if any stripped."""
    for asp in aspects:
        for pol_key in ("positive_evidence", "negative_evidence"):
            for ev in asp.get(pol_key, []):
                orig = ev.get("source_review_ids", [])
                valid = [i for i in orig if i in valid_idxs]
                invalid = [i for i in orig if i not in valid_idxs]
                if invalid:
                    log("out_of_range_ids", shop_id,
                        f"{asp['aspect']}/{pol_key} claim={ev.get('claim','')[:40]} "
                        f"invalid_ids={invalid}")
                ev["source_review_ids"] = valid
    return aspects

# ── async batch ───────────────────────────────────────────────────────────────
async def _absa_task(
    sem: asyncio.Semaphore,
    shop_id: int,
    reviews: list[dict],
) -> tuple[int, dict | None, float, int, int, str | None]:
    async with sem:
        try:
            result, latency, in_tok, out_tok = await asyncio.to_thread(call_absa, shop_id, reviews)
            return shop_id, result, latency, in_tok, out_tok, None
        except json.JSONDecodeError as exc:
            return shop_id, None, 0.0, 0, 0, f"json_parse_error: {exc}"
        except Exception as exc:
            return shop_id, None, 0.0, 0, 0, str(exc)


async def run_absa_batch(
    shop_ids: list[int],
    reviews_map: dict[int, list[dict]],
) -> dict[int, tuple[dict, float, int, int]]:
    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = [_absa_task(sem, sid, reviews_map[sid]) for sid in shop_ids]
    rows  = await asyncio.gather(*tasks)
    results: dict[int, tuple[dict, float, int, int]] = {}
    for shop_id, result, latency, in_tok, out_tok, err in rows:
        if err:
            log("absa_failed", shop_id, err)
        else:
            results[shop_id] = (result, latency, in_tok, out_tok)
    return results

# ── DB write ───────────────────────────────────────────────────────────────────
UPSERT_SQL = """
INSERT INTO tb_shop_absa (
    shop_id, aspects, meta, char_hit_rate, semantic_hit_rate,
    synonym_recovered, unverified_count, prompt_version, model, generated_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    aspects           = VALUES(aspects),
    meta              = VALUES(meta),
    char_hit_rate     = VALUES(char_hit_rate),
    semantic_hit_rate = VALUES(semantic_hit_rate),
    synonym_recovered = VALUES(synonym_recovered),
    unverified_count  = VALUES(unverified_count),
    prompt_version    = VALUES(prompt_version),
    model             = VALUES(model),
    generated_at      = VALUES(generated_at),
    update_time       = CURRENT_TIMESTAMP
"""


def write_absa_row(
    conn: pymysql.connections.Connection,
    shop_id: int,
    aspects: list[dict],
    meta: dict,
    v2: dict,
    generated_at: datetime,
) -> None:
    with conn.cursor() as cur:
        cur.execute(UPSERT_SQL, (
            shop_id,
            json.dumps(aspects, ensure_ascii=False),
            json.dumps(meta, ensure_ascii=False),
            v2["char_hit_rate"],
            v2["semantic_hit_rate"],
            v2["synonym_recovered_count"],
            v2["unverified_count"],
            meta.get("prompt_version", PROMPT_VERSION),
            CHAT_MODEL,
            generated_at,
        ))
    conn.commit()

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*64}")
print(f"ABSA Stage C Batch  |  {len(ACTIVE_IDS)} shops  |  {datetime.now().isoformat()[:16]}")
print(f"Concurrency={CONCURRENCY}  MinReviews={MIN_REVIEWS}  Stage=1-of-2 (char-verify only, no embed)")
print(f"QualityGate: char_hit_rate >= {QUALITY_GATE_HIT} (max fail {QUALITY_GATE_MAX_PCT:.0%})")
print(f"{'='*64}\n")

# ── pre-flight: DB check + load already-written shops ─────────────────────────
conn = pymysql.connect(**DB_CONFIG)
with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) AS n FROM tb_shop_absa")
    existing = cur.fetchone()["n"]
    cur.execute("SELECT shop_id FROM tb_shop_absa")
    already_done: set[int] = {row["shop_id"] for row in cur.fetchall()}
print(f"Pre-flight: tb_shop_absa rows before batch = {existing}")
if already_done:
    print(f"  Skipping {len(already_done)} shops already in DB: {sorted(already_done)[:10]}...")

# ── pre-flight: skip shops with < MIN_REVIEWS ─────────────────────────────────
reviews_map:   dict[int, list[dict]] = {}
skipped_shops: list[dict] = []
batch_ids:     list[int]  = []

for sid in ACTIVE_IDS:
    revs = load_reviews(sid)
    if sid in already_done:
        reason = "already in tb_shop_absa"
        skipped_shops.append({"shop_id": sid, "reason": reason,
                              "name": shop_map.get(sid, {}).get("display_name", "?")})
    elif len(revs) < MIN_REVIEWS:
        reason = f"only {len(revs)} non-empty reviews (< {MIN_REVIEWS})"
        log("skip_sparse", sid, reason)
        skipped_shops.append({"shop_id": sid, "reason": reason,
                              "name": shop_map.get(sid, {}).get("display_name", "?")})
    else:
        reviews_map[sid] = revs
        batch_ids.append(sid)

print(f"\nShops to process : {len(batch_ids)}")
print(f"Skipped (sparse) : {len(skipped_shops)}")

# ── concurrent ABSA batch ─────────────────────────────────────────────────────
print(f"\n--- Running ABSA ({CONCURRENCY} concurrent) ---")
wall_start   = time.time()
absa_results = asyncio.run(run_absa_batch(batch_ids, reviews_map))
wall_time    = time.time() - wall_start
ok_absa      = len(absa_results)
print(f"\nABSA done: {ok_absa}/{len(batch_ids)} OK  |  wall={wall_time:.1f}s")

# ── verify + sanitize ─────────────────────────────────────────────────────────
print("\n--- Running verifiers ---")
written_rows: list[dict] = []
quality_fails: list[int] = []
total_in_tok = total_out_tok = 0

for shop_id, (result, latency, in_tok, out_tok) in absa_results.items():
    total_in_tok  += in_tok
    total_out_tok += out_tok
    name = shop_map.get(shop_id, {}).get("display_name", "?")
    aspects = result.get("aspects", [])
    meta    = result.get("meta", {})
    valid_idxs = {r["idx"] for r in reviews_map[shop_id]}

    # sanitize out-of-range ids (no API calls)
    aspects = sanitize_source_ids(aspects, valid_idxs, shop_id)

    # C2: char-level only — no embed calls, no quota drain
    v1 = verify_v1(aspects, reviews_map[shop_id])
    char_hit = v1["char_hit_rate"]

    if char_hit < QUALITY_GATE_HIT:
        quality_fails.append(shop_id)
        log("quality_gate_fail", shop_id,
            f"char_hit={char_hit:.3f} < {QUALITY_GATE_HIT}  unver={v1['unverified']}")

    gen_at_str = (meta.get("generated_at") or "").strip()
    try:
        generated_at = datetime.fromisoformat(gen_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        generated_at = datetime.now(timezone.utc)

    written_rows.append({
        "shop_id":       shop_id,
        "name":          name,
        "latency_s":     round(latency, 2),
        "in_tokens":     in_tok,
        "out_tokens":    out_tok,
        "char_hit":      char_hit,
        "sem_hit":       None,   # semantic rescue deferred to separate maintenance job
        "syn_recovered": 0,
        "unverified":    v1["unverified"],
        "aspects":       aspects,
        "meta":          meta,
        "generated_at":  generated_at,
    })
    print(f"  [{shop_id}] {name[:25]:25s}  char={char_hit:.3f}  unver={v1['unverified']}")

# ── quality gate check ────────────────────────────────────────────────────────
fail_pct = len(quality_fails) / max(1, len(written_rows))
print(f"\nQuality gate (char_hit_rate >= {QUALITY_GATE_HIT}): "
      f"{len(quality_fails)}/{len(written_rows)} shops failed ({fail_pct:.1%})")

if fail_pct > QUALITY_GATE_MAX_PCT:
    print(f"\n⛔ STOP: quality gate exceeded ({fail_pct:.1%} > {QUALITY_GATE_MAX_PCT:.0%})")
    print("Shops that failed:")
    for sid in quality_fails:
        name = shop_map.get(sid, {}).get("display_name", "?")
        row  = next(r for r in written_rows if r["shop_id"] == sid)
        print(f"  [{sid}] {name}  char_hit={row['char_hit']:.3f}")
    print("\nNo rows written. Fix quality issues before proceeding.")
    conn.close()
    raise SystemExit(1)

# ── write to DB ───────────────────────────────────────────────────────────────
print("\n--- Writing to tb_shop_absa ---")
write_ok = write_fail = 0
for row in written_rows:
    try:
        write_absa_row(
            conn,
            shop_id     = row["shop_id"],
            aspects     = row["aspects"],
            meta        = row["meta"],
            v2          = {"char_hit_rate":          row["char_hit"],
                           "semantic_hit_rate":      row["sem_hit"],
                           "synonym_recovered_count": row["syn_recovered"],
                           "unverified_count":       row["unverified"]},
            generated_at = row["generated_at"],
        )
        write_ok += 1
    except Exception as exc:
        write_fail += 1
        log("db_write_error", row["shop_id"], str(exc))

print(f"Written: {write_ok}  Failed: {write_fail}")

conn.close()

# ── post-batch verification ───────────────────────────────────────────────────
print("\n" + "="*64)
print("POST-BATCH VERIFICATION")
print("="*64)

conn2 = pymysql.connect(**DB_CONFIG)
with conn2.cursor() as cur:
    cur.execute("SELECT COUNT(*) AS n FROM tb_shop_absa")
    final_count = cur.fetchone()["n"]
    print(f"\n  COUNT(*) tb_shop_absa = {final_count}")

    # hit_rate distribution
    cur.execute("""
        SELECT
            MIN(char_hit_rate)          AS min_char,
            AVG(char_hit_rate)          AS avg_char,
            MAX(char_hit_rate)          AS max_char,
            SUM(char_hit_rate < 0.70)   AS below_0_70,
            SUM(char_hit_rate < 0.80)   AS below_0_80,
            SUM(char_hit_rate = 1.0)    AS perfect,
            SUM(unverified_count = 0)   AS zero_unverified,
            COUNT(*)                    AS total
        FROM tb_shop_absa
    """)
    dist = cur.fetchone()
    print(f"\n  char_hit_rate distribution ({dist['total']} rows):")
    print(f"    min={dist['min_char']:.3f}  avg={dist['avg_char']:.3f}  max={dist['max_char']:.3f}")
    print(f"    perfect (1.0)     : {dist['perfect']}")
    print(f"    zero unverified   : {dist['zero_unverified']}")
    print(f"    below 0.80        : {dist['below_0_80']}")
    print(f"    below 0.70        : {dist['below_0_70']}")
    print(f"  (semantic_hit_rate deferred — run semantic rescue job after quota recovers)")

    # 3 random shops for spot check
    cur.execute("""
        SELECT shop_id, semantic_hit_rate, unverified_count, aspects
        FROM tb_shop_absa
        ORDER BY RAND()
        LIMIT 3
    """)
    samples = cur.fetchall()

conn2.close()

print("\n  --- 3 random shop spot check ---")
for s in samples:
    sid   = s["shop_id"]
    name  = shop_map.get(sid, {}).get("display_name", "?")
    aspects_data = s["aspects"] if isinstance(s["aspects"], list) else json.loads(s["aspects"])
    sem_val = s["semantic_hit_rate"]
    sem_str = f"{sem_val:.3f}" if sem_val is not None else "NULL (pending Stage 2)"
    print(f"\n  [{sid}] {name}  sem_hit={sem_str}  "
          f"unver={s['unverified_count']}")
    for asp in aspects_data:
        pos_ev = asp.get("positive_evidence", [])
        neg_ev = asp.get("negative_evidence", [])
        print(f"    [{asp['aspect']}] {asp['sentiment']}/{asp['confidence']}  "
              f"pos_ev={len(pos_ev)}  neg_ev={len(neg_ev)}")
        print(f"      summary: {asp['summary'][:80]}")
        if pos_ev:
            ev = pos_ev[0]
            print(f"      pos[0]: {ev.get('claim','')[:60]}  "
                  f"src_ids={ev.get('source_review_ids',[])}  "
                  f"terms={ev.get('concrete_terms',[])[:3]}")
        if neg_ev:
            ev = neg_ev[0]
            print(f"      neg[0]: {ev.get('claim','')[:60]}  "
                  f"src_ids={ev.get('source_review_ids',[])}  "
                  f"terms={ev.get('concrete_terms',[])[:3]}")

# ── summary report ─────────────────────────────────────────────────────────────
print("\n" + "="*64)
print("BATCH SUMMARY")
print("="*64)
print(f"  Active shops total   : {len(ACTIVE_IDS)}")
print(f"  Skipped (< {MIN_REVIEWS} reviews): {len(skipped_shops)}")
print(f"  Attempted ABSA       : {len(batch_ids)}")
print(f"  ABSA succeeded       : {ok_absa}")
print(f"  ABSA failed (JSON/LLM): {len(batch_ids) - ok_absa}")
print(f"  Quality gate fails   : {len(quality_fails)}")
print(f"  Written to DB        : {write_ok}")
print(f"  DB write failures    : {write_fail}")
print(f"  Wall time (ABSA)     : {wall_time:.1f}s")
cost_usd = (total_in_tok / 1_000_000 * COST_IN_PER_1M) + (total_out_tok / 1_000_000 * COST_OUT_PER_1M)
print(f"\n  Token usage:")
print(f"    Input  tokens : {total_in_tok:,}")
print(f"    Output tokens : {total_out_tok:,}")
print(f"    Est. cost USD : ${cost_usd:.4f}  (@ ${COST_IN_PER_1M}/1M in, ${COST_OUT_PER_1M}/1M out)")

if skipped_shops:
    print(f"\n  Skipped shops:")
    for s in skipped_shops:
        print(f"    [{s['shop_id']}] {s['name']}  —  {s['reason']}")

absa_fails = [sid for sid in batch_ids if sid not in absa_results]
if absa_fails:
    print(f"\n  ABSA failed shops:")
    for sid in absa_fails:
        fail_log = [e for e in _log if e["shop_id"] == sid and "fail" in e["event"]]
        reason = fail_log[-1]["detail"] if fail_log else "unknown"
        print(f"    [{sid}] {shop_map.get(sid,{}).get('display_name','?')}  —  {reason[:80]}")

# save log
LOG_PATH = Path(__file__).resolve().parent.parent / "evals" / "absa_c_batch_log.json"
LOG_PATH.write_text(json.dumps(_log, ensure_ascii=False, indent=2))
print(f"\n  Log: {LOG_PATH}")
print("\nDone.")
