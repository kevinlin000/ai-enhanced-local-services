#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymysql

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional in local scripts
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[2]
REPORT_JSON = ROOT / "docs" / "data-coverage-report.json"
REPORT_MD = ROOT / "docs" / "data-coverage-report.md"


def load_env() -> None:
    if not load_dotenv:
        return
    for path in (ROOT / ".env", ROOT / "etl-pipeline" / ".env", ROOT / "ai-service-python" / ".env"):
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


def table_exists(cur, table: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
        (table,),
    )
    return bool(cur.fetchone()["n"])


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) AS n
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cur.fetchone()["n"])


def scalar(cur, sql: str, params: tuple = ()) -> int:
    cur.execute(sql, params)
    row = cur.fetchone()
    if not row:
        return 0
    return int(next(iter(row.values())) or 0)


def rows(cur, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    cur.execute(sql, params)
    return list(cur.fetchall())


def pct(value: int | None, total: int) -> str:
    if value is None:
        return "-"
    if total == 0:
        return "0.0%"
    return f"{value / total * 100:.1f}%"


def mongo_distinct_review_shops() -> int | None:
    try:
        from pymongo import MongoClient
    except Exception:
        return None
    uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
    if not uri:
        return None
    db_name = os.getenv("MONGO_DB", "bytebites_reviews")
    collection_name = os.getenv("MONGO_REVIEWS_COLLECTION", "google_reviews")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=2500)
        client.admin.command("ping")
        values = client[db_name][collection_name].distinct("shop_id")
        return len([value for value in values if value])
    except Exception:
        return None


def build_flags(cur) -> dict[str, str]:
    has_metadata = table_exists(cur, "tb_shop_ai_metadata")
    has_absa = table_exists(cur, "tb_shop_absa")
    has_reviews = table_exists(cur, "tb_review")

    image_expr = "0"
    if column_exists(cur, "tb_shop", "images"):
        image_expr = "COALESCE(NULLIF(CAST(s.images AS CHAR), ''), '[]') <> '[]'"
    elif column_exists(cur, "tb_shop", "image_url"):
        image_expr = "s.image_url IS NOT NULL AND s.image_url <> ''"

    price_parts = []
    if column_exists(cur, "tb_shop", "avg_price"):
        price_parts.append("s.avg_price IS NOT NULL AND s.avg_price > 0")
    if column_exists(cur, "tb_shop", "price_range"):
        price_parts.append("s.price_range IS NOT NULL AND s.price_range <> ''")
    if has_metadata and column_exists(cur, "tb_shop_ai_metadata", "price_per_person"):
        price_parts.append("m.price_per_person IS NOT NULL AND m.price_per_person NOT IN ('', '未提及', '未公開價位')")

    return {
        "image": image_expr,
        "price": " OR ".join(price_parts) if price_parts else "0",
        "metadata_join": "LEFT JOIN tb_shop_ai_metadata m ON m.shop_id = s.id" if has_metadata else "",
        "absa_join": "LEFT JOIN tb_shop_absa a ON a.shop_id = s.id" if has_absa else "",
        "review_join": "LEFT JOIN tb_review r ON r.shop_id = s.id" if has_reviews else "",
        "has_metadata": "m.ai_summary IS NOT NULL AND m.ai_summary <> ''" if has_metadata else "0",
        "has_absa": "a.shop_id IS NOT NULL" if has_absa else "0",
        "review_count": "COUNT(DISTINCT r.id)" if has_reviews else "0",
    }


def coverage_count(cur, total: int, label: str, sql: str) -> dict[str, Any]:
    value = scalar(cur, sql)
    return {"label": label, "count": value, "percent": pct(value, total)}


def generate() -> dict[str, Any]:
    mongo_review_shops = mongo_distinct_review_shops()
    with connect() as conn, conn.cursor() as cur:
        total = scalar(cur, "SELECT COUNT(*) AS n FROM tb_shop")
        flags = build_flags(cur)

        joins = "\n".join(part for part in (flags["metadata_join"], flags["absa_join"], flags["review_join"]) if part)
        base_from = f"FROM tb_shop s\n{joins}"

        coverage = [
            coverage_count(cur, total, "Cover image/media", f"SELECT COUNT(*) AS n FROM tb_shop s WHERE {flags['image']}"),
            coverage_count(cur, total, "Price signal", f"SELECT COUNT(DISTINCT s.id) AS n {base_from} WHERE {flags['price']}"),
        ]

        if column_exists(cur, "tb_shop", "district"):
            coverage.append(
                coverage_count(cur, total, "District", "SELECT COUNT(*) AS n FROM tb_shop WHERE district IS NOT NULL AND district <> ''")
            )
        if column_exists(cur, "tb_shop", "mrt_station"):
            coverage.append(
                coverage_count(cur, total, "MRT station", "SELECT COUNT(*) AS n FROM tb_shop WHERE mrt_station IS NOT NULL AND mrt_station <> ''")
            )
        coverage.extend(
            [
                coverage_count(cur, total, "AI summary", f"SELECT COUNT(DISTINCT s.id) AS n {base_from} WHERE {flags['has_metadata']}"),
                coverage_count(cur, total, "ABSA", f"SELECT COUNT(DISTINCT s.id) AS n {base_from} WHERE {flags['has_absa']}"),
                coverage_count(
                    cur,
                    total,
                    "SQL reviews",
                    f"SELECT COUNT(*) AS n FROM (SELECT s.id {base_from} GROUP BY s.id HAVING {flags['review_count']} > 0) x",
                ),
            ]
        )
        coverage.append(
            {
                "label": "Mongo reviews",
                "count": mongo_review_shops,
                "percent": pct(mongo_review_shops, total) if mongo_review_shops is not None else "unavailable",
            }
        )

        category_distribution = []
        if table_exists(cur, "tb_shop_type"):
            name_col = "label_zh" if column_exists(cur, "tb_shop_type", "label_zh") else "name"
            category_distribution = rows(
                cur,
                f"""
                SELECT COALESCE(t.{name_col}, '未分類') AS label, COUNT(*) AS count
                FROM tb_shop s
                LEFT JOIN tb_shop_type t ON t.id = s.type_id
                GROUP BY label
                ORDER BY count DESC
                LIMIT 20
                """,
            )

        district_distribution = []
        if column_exists(cur, "tb_shop", "district"):
            district_distribution = rows(
                cur,
                """
                SELECT COALESCE(NULLIF(district, ''), '未填') AS label, COUNT(*) AS count
                FROM tb_shop
                GROUP BY label
                ORDER BY count DESC
                LIMIT 20
                """,
            )

        mrt_distribution = []
        if column_exists(cur, "tb_shop", "mrt_station"):
            mrt_distribution = rows(
                cur,
                """
                SELECT COALESCE(NULLIF(mrt_station, ''), '未填') AS label, COUNT(*) AS count
                FROM tb_shop
                GROUP BY label
                ORDER BY count DESC
                LIMIT 20
                """,
            )

        missing = rows(
            cur,
            f"""
            SELECT
                s.id,
                s.name,
                COALESCE(s.district, '') AS district,
                COALESCE(s.mrt_station, '') AS mrt_station,
                IF({flags['image']}, 1, 0) AS has_image,
                IF({flags['price']}, 1, 0) AS has_price,
                IF({flags['has_metadata']}, 1, 0) AS has_ai_summary,
                IF({flags['has_absa']}, 1, 0) AS has_absa,
                {flags['review_count']} AS review_count
            {base_from}
            GROUP BY s.id, s.name, s.district, s.mrt_station
            HAVING has_image = 0 OR has_price = 0 OR has_ai_summary = 0 OR has_absa = 0 OR review_count = 0
            ORDER BY
                (has_image + has_price + has_ai_summary + has_absa + IF(review_count > 0, 1, 0)) ASC,
                s.id DESC
            LIMIT 40
            """,
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_shops": total,
        "coverage": coverage,
        "category_distribution": category_distribution,
        "district_distribution": district_distribution,
        "mrt_distribution": mrt_distribution,
        "critical_missing": missing,
    }


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# ByteBites Data Coverage Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Total shops: `{report['total_shops']}`",
        "",
        "## Coverage",
        "",
        "| Area | Shops | Percent |",
        "|---|---:|---:|",
    ]
    for item in report["coverage"]:
        count = "-" if item["count"] is None else item["count"]
        lines.append(f"| {item['label']} | {count} | {item['percent']} |")

    def add_distribution(title: str, values: list[dict[str, Any]]) -> None:
        lines.extend(["", f"## {title}", "", "| Label | Count |", "|---|---:|"])
        for row in values:
            lines.append(f"| {row['label']} | {row['count']} |")

    add_distribution("Category Distribution", report["category_distribution"])
    add_distribution("District Distribution", report["district_distribution"])
    add_distribution("MRT Distribution", report["mrt_distribution"])

    lines.extend(
        [
            "",
            "## Critical Missing Detail Data",
            "",
            "| ID | Shop | District | MRT | Image | Price | AI Summary | ABSA | Reviews |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["critical_missing"]:
        lines.append(
            "| {id} | {name} | {district} | {mrt_station} | {has_image} | {has_price} | {has_ai_summary} | {has_absa} | {review_count} |".format(
                **row
            )
        )

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    report = generate()
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report)
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Wrote {REPORT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
