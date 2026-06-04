#!/usr/bin/env python3
"""Generate detail-scraper target queues from real coverage gaps."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from detail_coverage import (
    ROOT,
    SCRAPER_DIR,
    active_shops,
    load_env,
    media_shop_ids,
    mongo_review_shop_ids,
    sqlite_overview,
)


DEFAULT_OUTPUTS = {
    "overview-missing": SCRAPER_DIR / "shops_overview_missing.txt",
    "media-missing": SCRAPER_DIR / "shops_media_missing.txt",
    "reviews-missing": SCRAPER_DIR / "shops_reviews_missing.txt",
}
DEFAULT_REVIEW_EXCLUDE_FILE = SCRAPER_DIR / "known_limited_view_review_shops.txt"


def safe_field(value: str) -> str:
    return (value or "").replace("|", " ").replace("\n", " ").strip()


def write_targets(path: Path, shops: list) -> None:
    lines = [f"{shop.id}|{safe_field(shop.name)}|{safe_field(shop.address)}" for shop in shops]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    try:
        display_path = path.relative_to(ROOT)
    except ValueError:
        display_path = path
    print(f"generated {len(lines)} targets -> {display_path}")


def load_excluded_shop_ids(path: Path | None) -> set[int]:
    if not path or not path.exists():
        return set()

    excluded: set[int] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        shop_id_text = line.split("|", 1)[0].strip()
        try:
            excluded.add(int(shop_id_text))
        except ValueError:
            raise SystemExit(f"invalid shop_id in exclude file {path}: {raw_line}")
    return excluded


def priority_key(shop) -> tuple:
    """Prioritize shops likely to appear in browse/recommendation surfaces."""
    comments = shop.comments or 0
    rating = shop.rating or 0.0
    return (-comments, -rating, shop.id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("overview-missing", "media-missing", "reviews-missing"),
        default="overview-missing",
    )
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--order",
        choices=("priority", "id"),
        default="priority",
        help="priority sorts by review count/rating first; id keeps deterministic inventory order",
    )
    parser.add_argument(
        "--exclude-file",
        type=Path,
        help=(
            "optional shop_id blacklist. For reviews-missing, defaults to "
            "known_limited_view_review_shops.txt"
        ),
    )
    args = parser.parse_args()

    load_env()
    shops = active_shops()
    if args.mode == "overview-missing":
        covered = set(sqlite_overview())
    elif args.mode == "media-missing":
        covered, _ = media_shop_ids()
    else:
        covered, mongo_error = mongo_review_shop_ids()
        if mongo_error:
            raise SystemExit(f"cannot generate reviews queue: {mongo_error}")

    exclude_file = args.exclude_file
    if args.mode == "reviews-missing" and exclude_file is None:
        exclude_file = DEFAULT_REVIEW_EXCLUDE_FILE
    excluded = load_excluded_shop_ids(exclude_file)

    targets = [shop for shop in shops if shop.id not in covered and shop.id not in excluded]
    if args.order == "priority":
        targets.sort(key=priority_key)
    if args.limit > 0:
        targets = targets[: args.limit]

    output = args.output or DEFAULT_OUTPUTS[args.mode]
    write_targets(output, targets)
    if excluded:
        print(f"excluded {len(excluded)} known limited-view shops")


if __name__ == "__main__":
    main()
