"""Hit@1/3/5 eval runner for ByteBites RAG."""
import json, sys
import httpx
from pathlib import Path

EVAL_FILE = sys.argv[1] if len(sys.argv) > 1 else "evals/dataset.jsonl"
TOP_K = 5

cases = [json.loads(l) for l in Path(EVAL_FILE).read_text().splitlines() if l.strip()]
h1 = h3 = h5 = 0
total = len(cases)

for i, item in enumerate(cases):
    query = item["query"]
    expected = set(item.get("expected_shop_ids", []))
    r = httpx.post("http://localhost:8000/api/ai/search", json={"query": query, "top_k": TOP_K}, timeout=30)
    hits = r.json().get("hits", [])
    ids = [h["shop_id"] for h in hits[:TOP_K]]

    m1 = bool(set(ids[:1]) & expected)
    m3 = bool(set(ids[:3]) & expected)
    m5 = bool(set(ids[:5]) & expected)
    if m1: h1 += 1
    if m3: h3 += 1
    if m5: h5 += 1

    mark = "✓" if m3 else ("~" if m5 else "✗")
    matched = [x for x in ids[:5] if x in expected]
    print(f"{mark} [{i+1:02d}] {query:<28} expected={list(expected)[:3]} got={ids[:3]} matched={matched}")

print(f"\n=== Hit@k (n={total}) ===")
print(f"Hit@1: {h1}/{total} = {h1/total*100:.1f}%")
print(f"Hit@3: {h3}/{total} = {h3/total*100:.1f}%")
print(f"Hit@5: {h5}/{total} = {h5/total*100:.1f}%")
