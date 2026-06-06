#!/usr/bin/env python3
"""
Backfill missing shop ABSA rows from Mongo Google review documents.

Why this exists:
  - The original Stage C ABSA script only reads legacy ETL JSON for the first
    103 shops.
  - The expanded catalog stores per-review documents in MongoDB.
  - Frontend shop detail pages need tb_shop_absa for "餐廳特色" and review
    judgement sections to match the original 103-shop quality bar.

Default behavior is safe and idempotent:
  - targets active shops without tb_shop_absa
  - skips shops with too few reviews
  - writes only rows that pass char-level quality gate unless overridden
  - stores review_ids_by_idx in meta so semantic verification can reload the
    exact same source reviews later
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymysql
import pymysql.cursors
from google import genai
from google.genai import errors as genai_errors
from pymongo import MongoClient
import tenacity


MIN_REVIEWS = 5
MAX_REVIEWS = 40
CONCURRENCY = 20
QUALITY_GATE_HIT = 0.60
PROMPT_VERSION = "mongo-v1.0"

COST_IN_PER_1M = 0.075
COST_OUT_PER_1M = 0.30

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
LOG_PATH = ROOT / "evals" / "absa_mongo_backfill_log.jsonl"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


ENV = load_env()
API_KEY = ENV.get("GEMINI_API_KEY", "")
CHAT_MODEL = ENV.get("GEMINI_CHAT_MODEL", "gemini-3.5-flash")

DB_CONFIG = {
    "host": ENV.get("MYSQL_HOST", "127.0.0.1"),
    "port": int(ENV.get("MYSQL_PORT", "3306")),
    "user": ENV.get("MYSQL_USER", "root"),
    "password": ENV.get("MYSQL_PASSWORD", "password"),
    "database": ENV.get("MYSQL_DATABASE", "hmdp"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

MONGO_URI = ENV.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = ENV.get("MONGO_DB", "bytebites_reviews")
MONGO_COLLECTION = ENV.get("MONGO_REVIEWS_COLLECTION", "google_reviews")


ABSA_SYSTEM = """\
你是一個專業的餐廳評論分析師，任務是對單一餐廳的 Google 顧客評論進行 aspect-based sentiment analysis (ABSA)。

【任務】
讀完評論後，針對四個 aspect（dishes / service / environment / price）各輸出一個結構化分析。

【高品質要求】
1. summary 必須是「只適用於這家店」的具體描述，避免模板句。
2. 若評論提到具體菜名、餐點形式、價格數字、座位/空間/服務流程，必須納入 summary 或 evidence。
3. evidence 的 claim 必須由 source_review_ids 支撐；不可憑空補常識。
4. source_review_ids 使用輸入評論前方的索引，索引從 0 開始。
5. 不逐字長引用評論；用自己的話歸納。
6. mention_count 是該 aspect 在評論中被提到的約略則數，不是 evidence 數。
7. 若某 aspect 明確提及不足，confidence=low，evidence 可為空，但四個 aspect 都必須輸出。

【輸出格式 — 嚴格 JSON，禁止 markdown】
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
      "confidence_reason": "<簡短說明>",
      "mention_count": <int>,
      "positive_evidence": [{"claim":"","source_review_ids":[],"concrete_terms":[]}],
      "negative_evidence": [{"claim":"","source_review_ids":[],"concrete_terms":[]}],
      "hallucination_risk": false,
      "hallucination_note": ""
    }
  ],
  "meta": {"model": "", "generated_at": "", "prompt_version": "mongo-v1.0"}
}
"""


UPSERT_SQL = """
INSERT INTO tb_shop_absa (
    shop_id, aspects, meta,
    char_hit_rate, semantic_hit_rate,
    synonym_recovered, unverified_count,
    create_time, update_time
) VALUES (%s, %s, %s, %s, NULL, 0, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON DUPLICATE KEY UPDATE
    aspects = VALUES(aspects),
    meta = VALUES(meta),
    char_hit_rate = VALUES(char_hit_rate),
    semantic_hit_rate = NULL,
    synonym_recovered = 0,
    unverified_count = VALUES(unverified_count),
    update_time = CURRENT_TIMESTAMP
"""


@dataclass(frozen=True)
class Shop:
    id: int
    name: str
    address: str
    area: str | None
    district: str | None
    type_name: str | None


@dataclass(frozen=True)
class Review:
    idx: int
    review_id: str
    rating: float
    text: str
    author: str
    date: str


def log_json(event: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    with LOG_PATH.open("a") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def mysql_conn():
    return pymysql.connect(**DB_CONFIG)


def mongo_collection():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client[MONGO_DB][MONGO_COLLECTION]


def text_from_description(description: Any) -> str:
    if isinstance(description, dict):
        for key in ("zh", "zh-TW", "text", "en"):
            value = description.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    if isinstance(description, str):
        return description.strip()
    return ""


def get_targets(shop_ids: list[int], force: bool, limit: int | None) -> list[Shop]:
    where = ["s.is_active = 1"]
    params: list[Any] = []
    join_absa = ""
    if shop_ids:
        where.append("s.id IN (" + ",".join(["%s"] * len(shop_ids)) + ")")
        params.extend(shop_ids)
    elif not force:
        join_absa = "LEFT JOIN tb_shop_absa a ON a.shop_id = s.id"
        where.append("a.shop_id IS NULL")

    sql = f"""
        SELECT s.id, s.name, s.address, s.area, s.district, t.name AS type_name
        FROM tb_shop s
        LEFT JOIN tb_shop_type t ON t.id = s.type_id
        {join_absa}
        WHERE {' AND '.join(where)}
        ORDER BY s.id
    """
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    with mysql_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        Shop(
            id=int(row["id"]),
            name=row["name"],
            address=row["address"],
            area=row.get("area"),
            district=row.get("district"),
            type_name=row.get("type_name"),
        )
        for row in rows
    ]


def balanced_review_selection(docs: list[dict[str, Any]], max_reviews: int) -> list[dict[str, Any]]:
    def sort_key(doc: dict[str, Any]) -> tuple[int, str]:
        likes = int(doc.get("likes") or 0)
        date = str(doc.get("created_date") or doc.get("last_modified_date") or doc.get("review_date") or "")
        return (-likes, date)

    usable = [doc for doc in docs if text_from_description(doc.get("description"))]
    if len(usable) <= max_reviews:
        return usable

    negative = [doc for doc in usable if float(doc.get("rating") or 0) <= 3]
    positive = [doc for doc in usable if float(doc.get("rating") or 0) >= 4]
    neutral = [doc for doc in usable if 3 < float(doc.get("rating") or 0) < 4]

    negative.sort(key=sort_key)
    positive.sort(key=sort_key)
    neutral.sort(key=sort_key)

    selected: list[dict[str, Any]] = []
    selected.extend(negative[: min(12, len(negative))])
    remaining = max_reviews - len(selected)
    selected.extend(positive[: max(0, remaining)])
    remaining = max_reviews - len(selected)
    selected.extend(neutral[: max(0, remaining)])

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for doc in selected:
        rid = str(doc.get("review_id") or doc.get("_id"))
        if rid not in seen:
            seen.add(rid)
            deduped.append(doc)
    return deduped[:max_reviews]


def load_reviews(collection, shop_id: int, max_reviews: int) -> tuple[list[Review], int]:
    docs = list(collection.find({"shop_id": shop_id}))
    selected = balanced_review_selection(docs, max_reviews)
    reviews: list[Review] = []
    for idx, doc in enumerate(selected):
        text = text_from_description(doc.get("description"))
        if not text:
            continue
        reviews.append(
            Review(
                idx=idx,
                review_id=str(doc.get("review_id") or doc.get("_id")),
                rating=float(doc.get("rating") or 0),
                text=text,
                author=str(doc.get("author") or ""),
                date=str(doc.get("created_date") or doc.get("review_date") or ""),
            )
        )
    return reviews, len(docs)


def build_prompt(shop: Shop, reviews: list[Review], total_review_count: int) -> str:
    review_block = "\n".join(
        f"[{r.idx}] {r.rating:.0f}★ {r.date} {r.text[:650]}" for r in reviews
    )
    metadata = {
        "shop_id": shop.id,
        "name": shop.name,
        "type": shop.type_name,
        "area": shop.area,
        "district": shop.district,
        "address": shop.address,
        "review_count_total": total_review_count,
        "review_count_analyzed": len(reviews),
    }
    return (
        ABSA_SYSTEM
        + "\n\n【店家資料】\n"
        + json.dumps(metadata, ensure_ascii=False)
        + "\n\n【評論】\n"
        + review_block
        + "\n\n請輸出符合格式的 JSON。"
    )


_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=API_KEY)
    return _client


@tenacity.retry(
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(min=1, max=30),
    retry=tenacity.retry_if_exception_type((genai_errors.ClientError, genai_errors.ServerError)),
)
def llm_call(prompt: str, model: str) -> tuple[str, int, int]:
    resp = get_client().models.generate_content(model=model, contents=prompt)
    usage = getattr(resp, "usage_metadata", None)
    return (
        resp.text or "",
        getattr(usage, "prompt_token_count", 0) or 0,
        getattr(usage, "candidates_token_count", 0) or 0,
    )


def parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def sanitize_source_ids(aspects: list[dict[str, Any]], reviews: list[Review]) -> int:
    valid_ids = {r.idx for r in reviews}
    stripped = 0
    for aspect in aspects:
        for key in ("positive_evidence", "negative_evidence"):
            clean_evidence = []
            for evidence in aspect.get(key, []) or []:
                source_ids = [int(i) for i in evidence.get("source_review_ids", []) if int(i) in valid_ids]
                if len(source_ids) != len(evidence.get("source_review_ids", [])):
                    stripped += 1
                evidence["source_review_ids"] = source_ids
                evidence["concrete_terms"] = [
                    str(term).strip()
                    for term in evidence.get("concrete_terms", []) or []
                    if str(term).strip()
                ]
                evidence["claim"] = str(evidence.get("claim") or "").strip()
                if evidence["claim"] or evidence["concrete_terms"]:
                    clean_evidence.append(evidence)
            aspect[key] = clean_evidence
    return stripped


def verify_v1(aspects: list[dict[str, Any]], reviews: list[Review]) -> dict[str, Any]:
    review_text = {r.idx: r.text.lower() for r in reviews}
    total = hits = verified = unverified = 0
    details: list[dict[str, Any]] = []

    for aspect in aspects:
        for polarity, key in (("pos", "positive_evidence"), ("neg", "negative_evidence")):
            for evidence in aspect.get(key, []) or []:
                combined = " ".join(review_text.get(i, "") for i in evidence.get("source_review_ids", []))
                terms = evidence.get("concrete_terms", []) or []
                term_hits = sum(1 for term in terms if str(term).lower() in combined)
                total += len(terms)
                hits += term_hits
                rate = term_hits / len(terms) if terms else 1.0
                if rate < 0.5:
                    unverified += 1
                    details.append(
                        {
                            "aspect": aspect.get("aspect"),
                            "polarity": polarity,
                            "claim": str(evidence.get("claim") or "")[:120],
                            "char_hit_rate": round(rate, 2),
                            "missing_terms": [
                                term for term in terms if str(term).lower() not in combined
                            ],
                        }
                    )
                else:
                    verified += 1

    return {
        "char_hit_rate": round(hits / total, 3) if total else 1.0,
        "verified": verified,
        "unverified": unverified,
        "unverified_details": details,
    }


def write_absa(shop: Shop, result: dict[str, Any], reviews: list[Review], v1: dict[str, Any], model: str) -> None:
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    meta.update(
        {
            "model": model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "prompt_version": PROMPT_VERSION,
            "review_source": "mongo_google_reviews",
            "review_ids_by_idx": [r.review_id for r in reviews],
            "review_count_analyzed": len(reviews),
            "shop_name": shop.name,
            "shop_type": shop.type_name,
        }
    )
    aspects_json = json.dumps(result["aspects"], ensure_ascii=False)
    meta_json = json.dumps(meta, ensure_ascii=False)

    with mysql_conn() as conn, conn.cursor() as cur:
        cur.execute(
            UPSERT_SQL,
            (
                shop.id,
                aspects_json,
                meta_json,
                v1["char_hit_rate"],
                v1["unverified"],
            ),
        )
        conn.commit()


async def process_shop(
    sem: asyncio.Semaphore,
    collection,
    shop: Shop,
    args: argparse.Namespace,
) -> dict[str, Any]:
    async with sem:
        reviews, total_review_count = await asyncio.to_thread(
            load_reviews, collection, shop.id, args.max_reviews
        )
        if len(reviews) < args.min_reviews:
            return {"shop_id": shop.id, "name": shop.name, "status": "skip_low_reviews", "reviews": len(reviews)}

        prompt = build_prompt(shop, reviews, total_review_count)
        if args.dry_run:
            return {
                "shop_id": shop.id,
                "name": shop.name,
                "status": "dry_run",
                "reviews": len(reviews),
                "prompt_chars": len(prompt),
            }

        started = time.time()
        raw, input_tokens, output_tokens = await asyncio.to_thread(llm_call, prompt, args.model)
        latency = time.time() - started
        result = parse_json(raw)
        result["shop_id"] = shop.id
        result["review_count_total"] = total_review_count
        result["review_count_analyzed"] = len(reviews)
        aspects = result.get("aspects") or []
        stripped = sanitize_source_ids(aspects, reviews)
        v1 = verify_v1(aspects, reviews)

        should_write = v1["char_hit_rate"] >= args.quality_gate or args.write_low_quality
        if should_write:
            await asyncio.to_thread(write_absa, shop, result, reviews, v1, args.model)

        cost = input_tokens / 1_000_000 * COST_IN_PER_1M + output_tokens / 1_000_000 * COST_OUT_PER_1M
        return {
            "shop_id": shop.id,
            "name": shop.name,
            "status": "written" if should_write else "skip_quality_gate",
            "reviews": len(reviews),
            "total_reviews": total_review_count,
            "char_hit_rate": v1["char_hit_rate"],
            "unverified": v1["unverified"],
            "stripped_source_ids": stripped,
            "latency_sec": round(latency, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shop-id", type=int, action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true", help="Regenerate even if tb_shop_absa already exists")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    parser.add_argument("--min-reviews", type=int, default=MIN_REVIEWS)
    parser.add_argument("--max-reviews", type=int, default=MAX_REVIEWS)
    parser.add_argument("--quality-gate", type=float, default=QUALITY_GATE_HIT)
    parser.add_argument("--write-low-quality", action="store_true")
    parser.add_argument("--model", default=CHAT_MODEL)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if not API_KEY and not args.dry_run:
        raise SystemExit("GEMINI_API_KEY missing")

    targets = get_targets(args.shop_id, args.force, args.limit)
    collection = mongo_collection()

    print("=" * 72, flush=True)
    print("ABSA Mongo Backfill", flush=True)
    print(
        f"targets={len(targets)} dry_run={args.dry_run} force={args.force} "
        f"model={args.model} concurrency={args.concurrency}",
        flush=True,
    )
    print(
        f"min_reviews={args.min_reviews} max_reviews={args.max_reviews} "
        f"quality_gate={args.quality_gate}",
        flush=True,
    )
    print("=" * 72, flush=True)

    started = time.time()
    sem = asyncio.Semaphore(args.concurrency)
    tasks = [process_shop(sem, collection, shop, args) for shop in targets]

    counters: dict[str, int] = {}
    total_cost = 0.0
    for coro in asyncio.as_completed(tasks):
        try:
            result = await coro
        except Exception as exc:
            result = {"status": "error", "error": str(exc)}
        counters[result["status"]] = counters.get(result["status"], 0) + 1
        total_cost += float(result.get("cost_usd") or 0)
        log_json(result)

        if result["status"] in {"written", "skip_quality_gate"}:
            print(
                f"[{result['status']}] {result['shop_id']} {result['name'][:28]:28s} "
                f"reviews={result['reviews']} char={result['char_hit_rate']:.3f} "
                f"unv={result['unverified']} cost=${result['cost_usd']:.5f}",
                flush=True,
            )
        else:
            print(f"[{result['status']}] {result.get('shop_id', '-')} {result.get('name', '')}", flush=True)

    wall = time.time() - started
    print("=" * 72, flush=True)
    print(f"complete wall={wall:.1f}s cost_est=${total_cost:.4f}", flush=True)
    print(" ".join(f"{key}={value}" for key, value in sorted(counters.items())), flush=True)
    print(f"log={LOG_PATH}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
