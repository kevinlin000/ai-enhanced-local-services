"""
Minimal RAG evaluation: hit@k.
For each query, retrieve top-k, check if any expected shop_id appears.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path

import httpx


DATASET = Path(__file__).parent / "dataset.jsonl"
SERVICE_URL = "http://localhost:8000"
TOP_K = 5


async def eval_one(client: httpx.AsyncClient, case: dict) -> dict:
    response = await client.post(
        f"{SERVICE_URL}/api/ai/search",
        json={"query": case["query"], "top_k": TOP_K},
        timeout=20.0,
    )
    response.raise_for_status()
    hits = response.json().get("hits", [])
    hit_ids = [hit["shop_id"] for hit in hits]
    expected = set(case["expected_shop_ids"])
    matched = [shop_id for shop_id in hit_ids if shop_id in expected]
    return {
        "query": case["query"],
        "rationale": case["rationale"],
        "hit_ids": hit_ids,
        "expected": list(expected),
        "matched": matched,
        "hit_at_k": len(matched) > 0,
    }


async def main():
    cases = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]
    async with httpx.AsyncClient() as client:
        results = []
        for case in cases:
            result = await eval_one(client, case)
            results.append(result)
            print(f"{'✓' if result['hit_at_k'] else '✗'} {result['query']}")
            await asyncio.sleep(1)

    hit_count = sum(1 for result in results if result["hit_at_k"])
    total = len(results)
    hit_rate = hit_count / total if total else 0

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_cases": total,
        "hits": hit_count,
        "hit_rate_at_k": round(hit_rate, 3),
        "top_k": TOP_K,
        "cases": results,
    }

    out_json = Path(__file__).parent / "report.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    lines = [
        "# RAG Eval Report",
        "",
        f"- Timestamp: {report['timestamp']}",
        f"- Total cases: {total}",
        f"- Hit@{TOP_K}: {hit_count}/{total} ({hit_rate:.1%})",
        "",
        "## Case Details",
        "",
    ]
    for result in results:
        mark = "✓" if result["hit_at_k"] else "✗"
        lines.append(
            f"- {mark} **{result['query']}** — matched {result['matched']}, retrieved {result['hit_ids']}"
        )
    out_md = Path(__file__).parent / "report.md"
    out_md.write_text("\n".join(lines))

    print(f"\nHit@{TOP_K}: {hit_count}/{total} = {hit_rate:.1%}")


if __name__ == "__main__":
    asyncio.run(main())
