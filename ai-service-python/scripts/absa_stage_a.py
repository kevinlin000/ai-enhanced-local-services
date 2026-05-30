#!/usr/bin/env python3
"""
ABSA Stage A — research-grade aspect-based sentiment analysis with faithfulness verification.
Runs on 3 shops, outputs a markdown report.  No DB writes, no frontend, no batch.

Usage: uv run python scripts/absa_stage_a.py
"""
import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

from google import genai

# ── env ───────────────────────────────────────────────────────────────────────
_env: dict[str, str] = {}
for _line in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in _line and not _line.startswith("#"):
        k, _, v = _line.partition("=")
        _env[k.strip()] = v.strip()

API_KEY   = _env.get("GEMINI_API_KEY", "")
CHAT_MODEL = _env.get("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not in .env"); sys.exit(1)

# ── data ──────────────────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).resolve().parent.parent.parent / "etl-pipeline" / "data" / "raw"
shop_map: dict[int, dict] = {}
for _f in sorted(RAW_DIR.glob("places_extracted_*.json")):
    for _s in json.loads(_f.read_text()).get("shops", []):
        sid = _s.get("shop_id")
        if sid:
            shop_map[sid] = _s

TARGET_IDS = [
    10139,   # 小小樹食 敦南店 — mixed baseline (13 neg / 20)
    10144,   # 二本松涮涮屋 本館 — mostly positive (0 neg / 20)
    10149,   # 夏慕尼新香榭鐵板燒 台北南昌店 — controversial (12 neg / 8 pos)
]

# ── prompt builder ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
你是一個專業的餐廳評論分析師，任務是對單一餐廳的評論進行 aspect-based sentiment analysis (ABSA)。

【任務】
讀完所有評論後，針對四個 aspect（dishes / service / environment / price）各輸出一個結構化分析。

【步驟，依序執行】
1. 完整讀完所有評論，標記每則評論對每個 aspect 的提及（內部步驟，不輸出）。
2. 對每個 aspect，找出至少 2 則明確提及才能輸出；不足則 confidence=low，evidence 陣列為空。
3. 撰寫 summary 時：
   a. 正面與負面的細節度必須對等。若有 5 則負面細節（菜名、口感、具體缺點），也要努力找出 5 則正面細節並反映。
   b. 若評論中提到具體菜名、做法、價格數字、空間元素，務必納入 summary。
   c. 禁止使用通用句型，例如：「N 則評論對 X 有具體描述」、「整體體驗評分的一部分」、「給人良好感受」等樣板語。
   d. 禁止逐字引用評論原文（版權）；用自己的話歸納。
   e. summary 必須是「只適用於這家店」的描述，換到別家店會明顯不通。
4. 每個 aspect 內，分別列出 positive_evidence 和 negative_evidence（兩個獨立陣列），各自帶 source_review_ids 與從評論抽出的 concrete_terms。
5. 完成後，做自我驗證：對每個 aspect 的 summary，逐句檢查能否在 source_review_ids 對應的評論中找到支撐；若有任何一句找不到，標為 hallucination_risk=true，並在 hallucination_note 說明哪句沒找到支撐。

【輸出格式 — 嚴格 JSON，禁止前後加任何文字或 markdown 圍欄】
{
  "shop_id": <int>,
  "review_count_total": <int>,
  "review_count_analyzed": <int>,
  "aspects": [
    {
      "aspect": "dishes",
      "summary": "<自然語言摘要，正反細節對等，專門描述這家店>",
      "sentiment": "positive|negative|mixed|neutral",
      "confidence": "high|medium|low",
      "confidence_reason": "<說明>",
      "mention_count": <int>,
      "positive_evidence": [
        {
          "claim": "<這條正面說法>",
          "source_review_ids": [<int>, ...],
          "concrete_terms": ["<菜名/詞>", ...]
        }
      ],
      "negative_evidence": [
        {
          "claim": "<這條負面說法>",
          "source_review_ids": [<int>, ...],
          "concrete_terms": ["<菜名/詞>", ...]
        }
      ],
      "hallucination_risk": false,
      "hallucination_note": ""
    }
  ],
  "meta": {
    "model": "<model>",
    "generated_at": "<ISO timestamp>",
    "prompt_version": "v2.0"
  }
}

【特別注意】
- 評論索引從 0 開始，與輸入順序一致。
- review_count_analyzed = 你實際讀入並用來分析的則數。
- 四個 aspect 全部輸出，即使某 aspect 無充分資訊（此時 confidence=low，summary 寫「評論中無充分資訊」）。
- 若整家店評論幾乎全正面，positive_evidence 仍需詳細列出，不能因為「都是好評」而偷懶。
"""


def build_prompt(shop: dict, reviews: list[dict]) -> str:
    block = "\n".join(
        f"[{r['idx']}] {r['rating']:.0f}★  {r['text'][:400]}"
        for r in reviews
    )
    return (
        SYSTEM_PROMPT
        + f"\n\n以下是「{shop.get('display_name')}」(shop_id={shop.get('shop_id')}) 的 {len(reviews)} 則評論：\n\n"
        + block
        + "\n\n分析 dishes、service、environment、price 四個面向，輸出 JSON。"
    )


# ── faithfulness verifier ─────────────────────────────────────────────────────
def verify_faithfulness(aspects: list[dict], reviews: list[dict]) -> dict:
    """
    For each evidence claim, check whether concrete_terms actually appear
    in the source review texts.  Returns quantitative metrics.
    """
    rev_by_idx = {r["idx"]: r["text"].lower() for r in reviews}

    verified = 0
    unverified = 0
    unverified_details = []
    all_terms_total = 0
    all_terms_hit = 0

    for asp in aspects:
        for polarity, evidences in [("positive", asp.get("positive_evidence", [])),
                                    ("negative", asp.get("negative_evidence", []))]:
            for ev in evidences:
                claim         = ev.get("claim", "")
                src_ids       = ev.get("source_review_ids", [])
                terms         = ev.get("concrete_terms", [])

                # build combined text of source reviews
                combined = " ".join(rev_by_idx.get(i, "") for i in src_ids)

                # concrete_term hit check
                hit = sum(1 for t in terms if t.lower() in combined)
                all_terms_total += len(terms)
                all_terms_hit   += hit

                hit_rate = hit / len(terms) if terms else 1.0

                if hit_rate < 0.5:
                    unverified += 1
                    unverified_details.append({
                        "aspect":       asp["aspect"],
                        "polarity":     polarity,
                        "claim":        claim[:80],
                        "hit_rate":     round(hit_rate, 2),
                        "missing_terms": [t for t in terms if t.lower() not in combined],
                    })
                else:
                    verified += 1

        # also flag LLM self-reported hallucination
        if asp.get("hallucination_risk"):
            unverified_details.append({
                "aspect":   asp["aspect"],
                "polarity": "self-reported",
                "claim":    asp.get("hallucination_note", "")[:80],
                "hit_rate": None,
                "missing_terms": [],
            })

    global_hit_rate = all_terms_hit / all_terms_total if all_terms_total else 1.0

    return {
        "verified_evidence_count":   verified,
        "unverified_evidence_count": unverified,
        "concrete_term_hit_rate":    round(global_hit_rate, 3),
        "unverified_details":        unverified_details,
    }


# ── LLM call ──────────────────────────────────────────────────────────────────
_client: genai.Client | None = None

def call_gemini(prompt: str) -> str:
    global _client
    if _client is None:
        _client = genai.Client(api_key=API_KEY)
    resp = _client.models.generate_content(model=CHAT_MODEL, contents=prompt)
    return resp.text


def parse_json(raw: str) -> dict:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```[a-z]*\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean)
    return json.loads(clean.strip())


# ── main ──────────────────────────────────────────────────────────────────────
results = []

for shop_id in TARGET_IDS:
    shop = shop_map.get(shop_id)
    if not shop:
        print(f"⚠ shop {shop_id} not found, skipping"); continue

    reviews = [
        {"idx": i, "rating": float(r.get("rating") or 0), "text": (r.get("text") or "").strip()}
        for i, r in enumerate(shop.get("reviews", []))
        if (r.get("text") or "").strip()
    ]

    name = shop.get("display_name", "?")
    print(f"\n{'='*64}\nProcessing {shop_id} {name}  ({len(reviews)} reviews)\n{'='*64}")

    prompt = build_prompt(shop, reviews)
    print(f"Prompt length: {len(prompt)} chars")

    raw_resp = call_gemini(prompt)
    print("LLM responded.")

    try:
        llm_out = parse_json(raw_resp)
    except json.JSONDecodeError as exc:
        print(f"❌ JSON parse error: {exc}")
        print("RAW:", raw_resp[:500])
        results.append({"shop_id": shop_id, "name": name, "error": str(exc), "raw": raw_resp})
        continue

    faith = verify_faithfulness(llm_out.get("aspects", []), reviews)

    results.append({
        "shop_id":  shop_id,
        "name":     name,
        "reviews":  reviews,
        "prompt":   prompt,
        "raw_resp": raw_resp,
        "llm_out":  llm_out,
        "faith":    faith,
    })

    print(f"  aspects: {[a['aspect'] for a in llm_out.get('aspects', [])]}")
    print(f"  faithfulness: hit_rate={faith['concrete_term_hit_rate']}  unverified={faith['unverified_evidence_count']}")


# ── markdown report ───────────────────────────────────────────────────────────
MD_PATH = Path(__file__).resolve().parent.parent / "docs" / "absa_stage_a_report.md"
MD_PATH.parent.mkdir(parents=True, exist_ok=True)

lines: list[str] = [
    "# ABSA Stage A Report",
    f"\nGenerated: {datetime.now(timezone.utc).isoformat()}  |  Model: `{CHAT_MODEL}`  |  Prompt version: v2.0\n",
    "---",
]

# 1. faithfulness summary table
lines += ["\n## Faithfulness Summary\n",
          "| shop | name | hit_rate | verified | unverified | hallu_risk_aspects |",
          "|---|---|---|---|---|---|"]
for r in results:
    if "error" in r:
        lines.append(f"| {r['shop_id']} | {r['name']} | ERROR | — | — | — |")
        continue
    faith = r["faith"]
    hallu = [a["aspect"] for a in r["llm_out"].get("aspects", []) if a.get("hallucination_risk")]
    lines.append(
        f"| {r['shop_id']} | {r['name']} | {faith['concrete_term_hit_rate']} "
        f"| {faith['verified_evidence_count']} | {faith['unverified_evidence_count']} "
        f"| {', '.join(hallu) if hallu else '—'} |"
    )

# 2. dishes summary comparison
lines += ["\n## Dishes Summary — Cross-Shop Comparison\n"]
for r in results:
    if "error" in r: continue
    asp = next((a for a in r["llm_out"].get("aspects", []) if a["aspect"] == "dishes"), None)
    if not asp: continue
    lines.append(f"**{r['shop_id']} {r['name']}** `{asp['sentiment']}` / `{asp['confidence']}`")
    lines.append(f"> {asp['summary']}\n")

# 3. per-shop details
for r in results:
    if "error" in r:
        lines += [f"\n---\n## {r['shop_id']} {r['name']} — ERROR\n", f"```\n{r.get('raw','')[:400]}\n```"]
        continue

    faith = r["faith"]
    lines += [
        f"\n---\n## {r['shop_id']} {r['name']}\n",
        f"Reviews analyzed: {r['llm_out'].get('review_count_analyzed', '?')}  "
        f"|  concrete_term_hit_rate: **{faith['concrete_term_hit_rate']}**  "
        f"|  unverified: {faith['unverified_evidence_count']}\n",
    ]

    for asp in r["llm_out"].get("aspects", []):
        h_flag = "⚠️ HALLU_RISK" if asp.get("hallucination_risk") else ""
        lines.append(f"### {asp['aspect']}  `{asp['sentiment']}` / `{asp['confidence']}` {h_flag}")
        lines.append(f"\n{asp['summary']}\n")
        lines.append(f"*Confidence reason:* {asp.get('confidence_reason', '—')}\n")

        if asp.get("positive_evidence"):
            lines.append("**Positive evidence:**")
            for ev in asp["positive_evidence"]:
                terms_str = ", ".join(ev.get("concrete_terms", []))
                lines.append(f"- {ev['claim']}  *(ids: {ev['source_review_ids']}, terms: `{terms_str}`)*")
            lines.append("")

        if asp.get("negative_evidence"):
            lines.append("**Negative evidence:**")
            for ev in asp["negative_evidence"]:
                terms_str = ", ".join(ev.get("concrete_terms", []))
                lines.append(f"- {ev['claim']}  *(ids: {ev['source_review_ids']}, terms: `{terms_str}`)*")
            lines.append("")

        if asp.get("hallucination_note"):
            lines.append(f"**Hallucination note:** {asp['hallucination_note']}\n")

    # faithfulness unverified details
    if faith["unverified_details"]:
        lines.append("**Unverified evidence (hit_rate < 0.5 or self-reported):**")
        for ud in faith["unverified_details"]:
            lines.append(
                f"- [{ud['aspect']} / {ud['polarity']}] hit_rate={ud.get('hit_rate', 'N/A')} "
                f"— `{ud['claim']}`  missing: {ud.get('missing_terms', [])}"
            )
        lines.append("")

    # prompt (collapsible)
    lines += [
        "<details><summary>Full prompt (click to expand)</summary>\n",
        "```",
        r["prompt"],
        "```",
        "\n</details>\n",
    ]

    # raw LLM response
    lines += [
        "<details><summary>Raw LLM response (click to expand)</summary>\n",
        "```json",
        r["raw_resp"],
        "```",
        "\n</details>\n",
    ]

# 4. cross-shop positive/negative evidence balance
lines += ["\n---\n## Evidence Balance (positive vs negative per aspect)\n",
          "| shop | aspect | pos_ev | neg_ev | balanced? |",
          "|---|---|---|---|---|"]
for r in results:
    if "error" in r: continue
    for asp in r["llm_out"].get("aspects", []):
        pos = len(asp.get("positive_evidence", []))
        neg = len(asp.get("negative_evidence", []))
        balanced = "✅" if abs(pos - neg) <= 2 else ("⬆️ pos" if pos > neg else "⬇️ neg")
        lines.append(f"| {r['shop_id']} | {asp['aspect']} | {pos} | {neg} | {balanced} |")

MD_PATH.write_text("\n".join(lines), encoding="utf-8")
print(f"\n\nReport written to: {MD_PATH}")

# ── console summary ───────────────────────────────────────────────────────────
print("\n" + "="*64)
print("DISHES SUMMARY COMPARISON")
print("="*64)
for r in results:
    if "error" in r: continue
    asp = next((a for a in r["llm_out"].get("aspects",[]) if a["aspect"]=="dishes"), None)
    if not asp: continue
    print(f"\n[{r['shop_id']}] {r['name']}")
    print(f"  sentiment={asp['sentiment']}  confidence={asp['confidence']}")
    print(f"  {asp['summary'][:200]}")

print("\n" + "="*64)
print("FAITHFULNESS METRICS")
print("="*64)
for r in results:
    if "error" in r: continue
    f = r["faith"]
    print(f"\n[{r['shop_id']}] {r['name']}")
    print(f"  concrete_term_hit_rate = {f['concrete_term_hit_rate']}")
    print(f"  verified={f['verified_evidence_count']}  unverified={f['unverified_evidence_count']}")
    if f["unverified_details"]:
        print("  unverified:")
        for ud in f["unverified_details"]:
            print(f"    [{ud['aspect']}/{ud['polarity']}] {ud.get('hit_rate','N/A')} {ud['claim'][:60]}")
