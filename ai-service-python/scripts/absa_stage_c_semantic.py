#!/usr/bin/env python3
"""
ABSA Stage C — Stage 2 of 2: async semantic rescue.

Reads tb_shop_absa rows where semantic_hit_rate IS NULL, runs verify_v2
(gemini-embedding-2, Tier 1 RPM=3000), updates semantic_hit_rate /
synonym_recovered / unverified_count.

Run after Stage 1 (absa_stage_c_batch.py).

Usage: uv run python -u scripts/absa_stage_c_semantic.py
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
CONCURRENCY   = 20     # Embedding 2 Tier 1 = 3000 RPM → 20 concurrent shops is fine
SEM_THRESHOLD = 0.55

# ── env ────────────────────────────────────────────────────────────────────────
_env: dict[str, str] = {}
for _line in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in _line and not _line.startswith("#"):
        k, _, v = _line.partition("=")
        _env[k.strip()] = v.strip()

API_KEY     = _env.get("GEMINI_API_KEY", "")
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
    print(f"  [LOG] {event} shop={shop_id}: {detail[:120]}", flush=True)

# ── ETL data ───────────────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).resolve().parent.parent.parent / "etl-pipeline" / "data" / "raw"
shop_map: dict[int, dict] = {}
for _f in sorted(RAW_DIR.glob("places_extracted_*.json")):
    for _s in json.loads(_f.read_text()).get("shops", []):
        sid = _s.get("shop_id")
        if sid:
            shop_map[sid] = _s


def load_reviews(shop_id: int) -> list[dict]:
    shop = shop_map.get(shop_id)
    if not shop:
        return []
    return [
        {"idx": i, "rating": float(r.get("rating") or 0), "text": (r.get("text") or "").strip()}
        for i, r in enumerate(shop.get("reviews", []))
        if (r.get("text") or "").strip()
    ]

# ── embedding + cosine ─────────────────────────────────────────────────────────
_embed_cache: dict[str, list[float]] = {}

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=API_KEY)
    return _client


@tenacity.retry(
    stop=tenacity.stop_after_attempt(5),
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

# ── verifier v1 (char-level, no API) ──────────────────────────────────────────
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


# ── verifier v2 (semantic rescue) ─────────────────────────────────────────────
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
        "semantic_hit_rate":       sem_hit,
        "synonym_recovered_count": recovered,
        "unverified_count":        len(still_unver),
    }

# ── async task per shop ────────────────────────────────────────────────────────
async def _sem_task(
    sem: asyncio.Semaphore,
    shop_id: int,
    aspects: list[dict],
    reviews: list[dict],
) -> tuple[int, dict | None, str | None]:
    async with sem:
        try:
            v2 = await asyncio.to_thread(verify_v2, aspects, reviews, shop_id)
            return shop_id, v2, None
        except Exception as exc:
            return shop_id, None, str(exc)

# ── DB update ─────────────────────────────────────────────────────────────────
UPDATE_SQL = """
UPDATE tb_shop_absa
SET semantic_hit_rate  = %s,
    synonym_recovered  = %s,
    unverified_count   = %s,
    update_time        = CURRENT_TIMESTAMP
WHERE shop_id = %s
"""

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*64}", flush=True)
print(f"ABSA Stage C — Stage 2 Semantic Rescue  |  {datetime.now().isoformat()[:16]}", flush=True)
print(f"Concurrency={CONCURRENCY}  SemThreshold={SEM_THRESHOLD}  Model={EMBED_MODEL}", flush=True)
print(f"Target: rows where semantic_hit_rate IS NULL", flush=True)
print(f"{'='*64}\n", flush=True)

conn = pymysql.connect(**DB_CONFIG)
with conn.cursor() as cur:
    cur.execute("SELECT shop_id, aspects FROM tb_shop_absa WHERE semantic_hit_rate IS NULL")
    pending = cur.fetchall()

print(f"Shops pending semantic rescue: {len(pending)}", flush=True)
if not pending:
    print("Nothing to do.", flush=True)
    conn.close()
    raise SystemExit(0)

# ── build task list ────────────────────────────────────────────────────────────
tasks_input: list[tuple[int, list, list]] = []
skip = 0
for row in pending:
    shop_id  = row["shop_id"]
    aspects  = row["aspects"] if isinstance(row["aspects"], list) else json.loads(row["aspects"])
    reviews  = load_reviews(shop_id)
    if not reviews:
        log("skip_no_reviews", shop_id, "no ETL reviews found")
        skip += 1
        continue
    tasks_input.append((shop_id, aspects, reviews))

print(f"Tasks to run: {len(tasks_input)}  Skipped (no reviews): {skip}", flush=True)
print(f"\n--- Running semantic rescue ({CONCURRENCY} concurrent) ---", flush=True)

# ── run ───────────────────────────────────────────────────────────────────────
t0 = time.time()

async def run_all() -> list:
    sem = asyncio.Semaphore(CONCURRENCY)
    coros = [_sem_task(sem, sid, asp, rev) for sid, asp, rev in tasks_input]
    return await asyncio.gather(*coros)

results = asyncio.run(run_all())
wall = time.time() - t0

# ── write results + report ────────────────────────────────────────────────────
ok = fail = 0
for shop_id, v2, err in results:
    name = shop_map.get(shop_id, {}).get("display_name", "?")
    if err:
        log("verify_v2_error", shop_id, err)
        fail += 1
        continue
    try:
        with conn.cursor() as cur:
            cur.execute(UPDATE_SQL, (
                v2["semantic_hit_rate"],
                v2["synonym_recovered_count"],
                v2["unverified_count"],
                shop_id,
            ))
        conn.commit()
        ok += 1
        print(f"  [{shop_id}] {name[:30]:30s}  sem={v2['semantic_hit_rate']:.3f}  "
              f"syn_rec={v2['synonym_recovered_count']}  unver={v2['unverified_count']}", flush=True)
    except Exception as exc:
        log("db_update_error", shop_id, str(exc))
        fail += 1

conn.close()

print(f"\n{'='*64}", flush=True)
print(f"Semantic rescue complete  |  wall={wall:.1f}s", flush=True)
print(f"  Updated : {ok}", flush=True)
print(f"  Skipped : {skip}  (no reviews in ETL)", flush=True)
print(f"  Failed  : {fail}", flush=True)

# ── distribution check ────────────────────────────────────────────────────────
conn2 = pymysql.connect(**DB_CONFIG)
with conn2.cursor() as cur:
    cur.execute("""
        SELECT MIN(semantic_hit_rate) AS min_sem, AVG(semantic_hit_rate) AS avg_sem,
               MAX(semantic_hit_rate) AS max_sem, SUM(synonym_recovered) AS total_syn_rec,
               SUM(semantic_hit_rate = 1.0) AS perfect, COUNT(*) AS total
        FROM tb_shop_absa WHERE semantic_hit_rate IS NOT NULL
    """)
    dist = cur.fetchone()
conn2.close()

if dist and dist["total"]:
    print(f"\n  semantic_hit_rate distribution ({dist['total']} rows):", flush=True)
    print(f"    min={dist['min_sem']:.3f}  avg={dist['avg_sem']:.3f}  max={dist['max_sem']:.3f}", flush=True)
    print(f"    perfect (1.0) : {dist['perfect']}", flush=True)
    print(f"    total syn_rec : {dist['total_syn_rec']}", flush=True)

LOG_PATH = Path(__file__).resolve().parent.parent / "evals" / "absa_c_semantic_log.json"
LOG_PATH.write_text(json.dumps(_log, ensure_ascii=False, indent=2))
print(f"\n  Log: {LOG_PATH}", flush=True)
print("Done.", flush=True)
