#!/usr/bin/env python3
"""Live AI smoke checks for the portfolio demo.

Requires the local AI service on AI_BASE_URL (default: http://localhost:8000).
This script only calls local AI endpoints. It does not read secrets and does
not write to MySQL.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:8000").rstrip("/")


def post_json(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"{path} returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise AssertionError(f"Cannot reach AI service at {BASE_URL}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    session_id = f"portfolio-ai-smoke-{int(time.time())}"

    first = post_json(
        "/api/ai/agent",
        {
            "query": "大安區人均200到400義式餐廳，想約會聊天",
            "session_id": session_id,
        },
    )
    first_answer = str(first.get("answer") or "")
    require(
        "光司DATE" in first_answer or 10673 in first.get("recommended_shop_ids", []),
        "first query should find the Italian/date scenario",
    )

    second = post_json(
        "/api/ai/agent",
        {
            "query": "大安區想吃牛排，適合約會聊天，也想知道附近停車",
            "session_id": session_id,
        },
    )
    answer = str(second.get("answer") or "")
    ids = [int(item) for item in second.get("recommended_shop_ids", []) if str(item).isdigit()]
    shops = [str(shop.get("name") or "") for shop in second.get("shops", []) if isinstance(shop, dict)]

    require("**" not in answer, "fresh recommendation answer should not expose raw Markdown markers")
    require("牛排餐廳" in answer, "fresh steak query should be labeled as steak, not generic American")
    require(10673 not in ids, "fresh steak query should not reuse previous 光司DATE recommendation")
    require(any("牛排" in name for name in shops[:3]), "fresh steak query should return steak candidates")
    require({10544, 10159}.intersection(ids), "fresh steak query should include a strong steak candidate")

    search = post_json(
        "/api/ai/search",
        {"query": "大安區想吃牛排，適合約會聊天，也想知道附近停車", "limit": 5},
    )
    search_results = search.get("shops") or search.get("hits") or []
    search_names = [str(shop.get("name") or "") for shop in search_results if isinstance(shop, dict)]
    require(any("牛排" in name for name in search_names[:3]), "AI search should surface steak candidates near the top")

    print("AI portfolio smoke passed")
    print(f"- session_id: {session_id}")
    print(f"- agent recommended ids: {ids[:3]}")
    print(f"- search top names: {', '.join(search_names[:3])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"AI portfolio smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
