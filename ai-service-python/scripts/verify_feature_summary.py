#!/usr/bin/env python3
"""
One-off verification script: LLM-generated feature summary for a single shop.
Not integrated into main service. For prompt validation only.
Run: uv run python scripts/verify_feature_summary.py
"""
import json
import sys
from pathlib import Path

from google import genai

# ── load .env manually (no dotenv dep needed) ────────────────────────────────
_env_path = Path(__file__).resolve().parent.parent / ".env"
_env: dict[str, str] = {}
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            k, _, v = _line.partition("=")
            _env[k.strip()] = v.strip()

API_KEY = _env.get("GEMINI_API_KEY", "")
CHAT_MODEL = _env.get("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite")

if not API_KEY:
    print("ERROR: GEMINI_API_KEY not in .env")
    sys.exit(1)

# ── load shop data ────────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).resolve().parent.parent.parent / "etl-pipeline" / "data" / "raw"
shop_map: dict[int, dict] = {}
for f in sorted(RAW_DIR.glob("places_extracted_*.json")):
    for s in json.loads(f.read_text()).get("shops", []):
        sid = s.get("shop_id")
        if sid:
            shop_map[sid] = s  # last file wins (latest ETL run)

TARGET_ID = 10139  # 小小樹食 敦南店 — 13 neg / 20 total, rich mix

shop = shop_map.get(TARGET_ID)
if not shop:
    print(f"Shop {TARGET_ID} not found")
    sys.exit(1)

print(f"Shop: {shop.get('display_name')} (id={TARGET_ID})\n")

reviews = [
    {
        "idx": i,
        "rating": float(r.get("rating") or 0),
        "text": (r.get("text") or "").strip(),
    }
    for i, r in enumerate(shop.get("reviews", []))
    if (r.get("text") or "").strip()
]
print(f"Non-empty reviews: {len(reviews)}")

# ── prompt ────────────────────────────────────────────────────────────────────
SYSTEM = """你是一位餐廳用餐體驗分析師。根據提供的評論，生成這家店的結構化特色摘要。

【強制規則，違反則重試】
1. 每條 summary 必須是「專門描述這家店」的具體說法。
   ✗ 禁止：「N 則好評對服務有具體描述」「多則評論提到環境」等骨架句。
   ✓ 應該：直接說這家店在那個面向「做了什麼」「有什麼特徵」「給人什麼感受」。
2. 禁止逐字引用評論原文，用自己的話歸納。
3. source_review_ids 只放實際支撐該結論的評論 idx（照下方清單編號）。
4. 某面向有效評論 < 2 則 → 不輸出該面向。
5. 評論褒貶混雜 → sentiment 標 "mixed"，summary 同時呈現兩側。
6. 只輸出 JSON，不要 markdown 圍欄或其他文字。

confidence 規則：
- high: ≥ 5 則評論支撐此結論
- medium: 2–4 則
- low: < 2 則（此時不輸出）

輸出 schema：
{
  "aspects": [
    {
      "aspect": "dishes|service|environment|price",
      "summary": "<針對這家店的具體描述>",
      "sentiment": "positive|mixed|negative",
      "mention_count": <int>,
      "source_review_ids": [<idx>, ...],
      "confidence": "high|medium|low"
    }
  ]
}"""

reviews_block = "\n".join(
    f"[{r['idx']}] {r['rating']:.0f}★  {r['text'][:350]}"
    for r in reviews
)

USER = f"""以下是「{shop.get('display_name')}」的 {len(reviews)} 則評論：

{reviews_block}

分析 dishes（料理）、service（服務）、environment（環境）、price（價格）四個面向，輸出 JSON。"""

full_prompt = SYSTEM + "\n\n" + USER

print("\n" + "=" * 64)
print("FULL PROMPT:")
print("=" * 64)
print(full_prompt)
print("=" * 64)

# ── call Gemini ───────────────────────────────────────────────────────────────
client = genai.Client(api_key=API_KEY)
response = client.models.generate_content(model=CHAT_MODEL, contents=full_prompt)
raw = response.text

print("\n" + "=" * 64)
print("RAW LLM RESPONSE:")
print("=" * 64)
print(raw)
print("=" * 64)

# ── parse ─────────────────────────────────────────────────────────────────────
clean = raw.strip()
if clean.startswith("```"):
    clean = "\n".join(clean.split("\n")[1:])
    clean = clean.rstrip("`").strip()
try:
    result = json.loads(clean)
except json.JSONDecodeError as exc:
    print(f"\n❌ JSON parse error: {exc}")
    sys.exit(1)

print("\nPARSED ASPECTS:")
for asp in result.get("aspects", []):
    print(f"\n  [{asp['aspect']}] {asp['sentiment']} / {asp['confidence']}")
    print(f"  summary      : {asp['summary']}")
    print(f"  mention_count: {asp['mention_count']}")
    print(f"  source_ids   : {asp['source_review_ids']}")

# ── spot-check first aspect ───────────────────────────────────────────────────
aspects = result.get("aspects", [])
if aspects:
    spot = aspects[0]
    print("\n" + "=" * 64)
    print(f"SPOT CHECK → aspect='{spot['aspect']}'")
    print(f"LLM says: {spot['summary']}")
    print(f"Claimed source_review_ids: {spot['source_review_ids']}")
    print("Actual review texts for those ids:")
    for idx in spot["source_review_ids"][:5]:
        match = next((r for r in reviews if r["idx"] == idx), None)
        if match:
            print(f"  [{idx}] {match['rating']:.0f}★  {match['text'][:250]}")
        else:
            print(f"  [{idx}] ⚠ idx not found in review list")
    print("=" * 64)
