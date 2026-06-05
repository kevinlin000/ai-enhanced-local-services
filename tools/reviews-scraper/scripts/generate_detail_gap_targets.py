#!/usr/bin/env python3
"""Generate review-scraper targets for shops missing rich detail coverage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from detail_coverage import active_shops, load_env, media_shop_ids, mongo_review_shop_ids, sqlite_overview


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = ROOT / "tools" / "reviews-scraper" / "shops_detail_gaps.txt"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    args = parser.parse_args()

    load_env()
    shops = active_shops()
    overview_ids = set(sqlite_overview())
    media_ids, media_photo_ids = media_shop_ids()
    mongo_ids, mongo_error = mongo_review_shop_ids()
    if mongo_error:
        raise SystemExit(f"Mongo unavailable: {mongo_error}")

    targets = []
    for shop in shops:
        reasons = []
        if shop.id not in overview_ids:
            reasons.append("missing_overview")
        if shop.id not in media_ids or shop.id not in media_photo_ids:
            reasons.append("missing_media")
        if shop.id not in mongo_ids:
            reasons.append("missing_reviews")
        if not reasons:
            continue
        priority = (
            1 if "missing_overview" in reasons else 0,
            1 if "missing_media" in reasons else 0,
            1 if "missing_reviews" in reasons else 0,
            shop.comments or 0,
        )
        targets.append((priority, shop, reasons))

    targets.sort(key=lambda item: item[0], reverse=True)
    if args.limit > 0:
        targets = targets[: args.limit]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(f"{shop.id}|{shop.name}|{shop.address}" for _priority, shop, _reasons in targets) + ("\n" if targets else ""),
        encoding="utf-8",
    )

    summary = {
        "targets": len(targets),
        "output": str(args.output),
        "reason_counts": {
            reason: sum(1 for _priority, _shop, reasons in targets if reason in reasons)
            for reason in ("missing_overview", "missing_media", "missing_reviews")
        },
        "sample": [
            {"shop_id": shop.id, "name": shop.name, "area": shop.area, "category": shop.category, "reasons": reasons}
            for _priority, shop, reasons in targets[:20]
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
