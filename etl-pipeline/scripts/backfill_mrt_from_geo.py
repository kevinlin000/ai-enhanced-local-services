#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymysql

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional local dependency
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[2]
REPORT_JSON = ROOT / "docs" / "mrt-backfill-report.json"
REPORT_MD = ROOT / "docs" / "mrt-backfill-report.md"


TAIPEI_LAT_MIN = 24.85
TAIPEI_LAT_MAX = 25.25
TAIPEI_LNG_MIN = 121.35
TAIPEI_LNG_MAX = 121.70


def load_env() -> None:
    if not load_dotenv:
        return
    for path in (ROOT / ".env", ROOT / "etl-pipeline" / ".env", ROOT / "backend-java" / ".env"):
        if path.exists():
            load_dotenv(path, override=False)


def connect():
    load_env()
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER") or os.getenv("MYSQL_USERNAME") or "root",
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def valid_taipei_coord(lat: Any, lng: Any) -> bool:
    if lat is None or lng is None:
        return False
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return False
    return TAIPEI_LAT_MIN <= lat_f <= TAIPEI_LAT_MAX and TAIPEI_LNG_MIN <= lng_f <= TAIPEI_LNG_MAX


def nearest_station(shop: dict[str, Any], stations: list[dict[str, Any]]) -> tuple[dict[str, Any], int] | None:
    shop_lat = float(shop["y"])
    shop_lng = float(shop["x"])
    best: tuple[dict[str, Any], int] | None = None
    for station in stations:
        distance = int(round(haversine_meters(shop_lat, shop_lng, float(station["y"]), float(station["x"]))))
        if best is None or distance < best[1]:
            best = (station, distance)
    return best


def bucket_distance(distance: int) -> str:
    if distance <= 400:
        return "<=400m"
    if distance <= 800:
        return "401-800m"
    if distance <= 1000:
        return "801-1000m"
    if distance <= 1200:
        return "1001-1200m"
    return ">1200m"


def fetch_inputs(cur, overwrite: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cur.execute(
        """
        SELECT id, name, district, mrt_station, x, y
        FROM tb_shop
        WHERE x IS NOT NULL
          AND y IS NOT NULL
          AND (%s OR mrt_station IS NULL OR mrt_station = '')
        ORDER BY id
        """,
        (overwrite,),
    )
    shops = list(cur.fetchall())
    cur.execute("SELECT id, name, district, x, y FROM tb_mrt_station ORDER BY id")
    stations = list(cur.fetchall())
    return shops, stations


def apply_updates(cur, matches: list[dict[str, Any]]) -> None:
    cur.executemany(
        """
        UPDATE tb_shop
        SET mrt_station = %s,
            mrt_distance_meters = %s
        WHERE id = %s
        """,
        [(item["station"], item["distance_meters"], item["shop_id"]) for item in matches],
    )


def generate(args: argparse.Namespace) -> dict[str, Any]:
    with connect() as conn, conn.cursor() as cur:
        shops, stations = fetch_inputs(cur, args.overwrite)
        if not stations:
            raise RuntimeError("tb_mrt_station has no stations")

        invalid_coord: list[dict[str, Any]] = []
        out_of_radius: list[dict[str, Any]] = []
        matches: list[dict[str, Any]] = []

        for shop in shops:
            if not valid_taipei_coord(shop["y"], shop["x"]):
                invalid_coord.append({"shop_id": shop["id"], "name": shop["name"], "x": shop["x"], "y": shop["y"]})
                continue
            nearest = nearest_station(shop, stations)
            if not nearest:
                continue
            station, distance = nearest
            item = {
                "shop_id": shop["id"],
                "name": shop["name"],
                "district": shop.get("district") or "",
                "station": station["name"],
                "station_district": station.get("district") or "",
                "distance_meters": distance,
            }
            if distance <= args.radius_meters:
                matches.append(item)
            else:
                out_of_radius.append(item)

        if args.apply and matches:
            apply_updates(cur, matches)
            conn.commit()

        cur.execute("SELECT COUNT(*) AS n FROM tb_shop WHERE mrt_station IS NOT NULL AND mrt_station <> ''")
        total_with_mrt = int(cur.fetchone()["n"] or 0)
        cur.execute("SELECT COUNT(*) AS n FROM tb_shop")
        total_shops = int(cur.fetchone()["n"] or 0)

    station_counts = Counter(item["station"] for item in matches)
    distance_buckets = Counter(bucket_distance(item["distance_meters"]) for item in matches)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "applied": bool(args.apply),
        "radius_meters": args.radius_meters,
        "overwrite": bool(args.overwrite),
        "candidates": len(shops),
        "matched": len(matches),
        "invalid_or_outside_taipei_coords": len(invalid_coord),
        "out_of_radius": len(out_of_radius),
        "total_shops": total_shops,
        "total_with_mrt_after": total_with_mrt,
        "station_counts": [{"station": station, "count": count} for station, count in station_counts.most_common()],
        "distance_buckets": [{"bucket": bucket, "count": count} for bucket, count in distance_buckets.items()],
        "sample_matches": matches[:40],
        "sample_out_of_radius": out_of_radius[:20],
        "sample_invalid_coords": invalid_coord[:20],
    }


def write_markdown(report: dict[str, Any]) -> None:
    pct = report["total_with_mrt_after"] / report["total_shops"] * 100 if report["total_shops"] else 0
    lines = [
        "# MRT Geo Backfill Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Applied: `{report['applied']}`",
        f"- Radius: `{report['radius_meters']}m`",
        f"- Candidates: `{report['candidates']}`",
        f"- Matched: `{report['matched']}`",
        f"- Invalid/outside Taipei coords: `{report['invalid_or_outside_taipei_coords']}`",
        f"- Out of radius: `{report['out_of_radius']}`",
        f"- MRT coverage after run: `{report['total_with_mrt_after']}/{report['total_shops']} ({pct:.1f}%)`",
        "",
        "## Station Counts",
        "",
        "| Station | Count |",
        "|---|---:|",
    ]
    for row in report["station_counts"]:
        lines.append(f"| {row['station']} | {row['count']} |")

    lines.extend(["", "## Distance Buckets", "", "| Bucket | Count |", "|---|---:|"])
    for row in report["distance_buckets"]:
        lines.append(f"| {row['bucket']} | {row['count']} |")

    lines.extend(["", "## Sample Matches", "", "| ID | Shop | Station | Distance |", "|---:|---|---|---:|"])
    for row in report["sample_matches"]:
        lines.append(f"| {row['shop_id']} | {row['name']} | {row['station']} | {row['distance_meters']} |")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill tb_shop.mrt_station from nearest tb_mrt_station")
    parser.add_argument("--radius-meters", type=int, default=1000)
    parser.add_argument("--apply", action="store_true", help="write matches to MySQL")
    parser.add_argument("--overwrite", action="store_true", help="also recompute rows with existing mrt_station")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = generate(args)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"{mode}: matched {report['matched']} shops within {report['radius_meters']}m")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Wrote {REPORT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
