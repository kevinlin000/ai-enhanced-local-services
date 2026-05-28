"""Verify shared/taxonomy.json is in sync with DB (tb_shop_type / tb_badge_def / tb_tag_def).
Exit 0 = all green. Exit 1 = diff found (details printed).
Usage: python etl-pipeline/scripts/verify_taxonomy_sync.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")

TAXONOMY_PATH = REPO_ROOT / "shared" / "taxonomy.json"


def load_taxonomy() -> dict:
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_conn():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
    )


def check_categories(tax: dict, conn) -> list[str]:
    errors: list[str] = []
    expected = {c["type_id"]: c["name"] for c in tax["categories"]}
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM tb_shop_type WHERE is_active = 1")
        db_rows = {row[0]: row[1] for row in cur.fetchall()}

    for type_id, name in expected.items():
        if type_id not in db_rows:
            errors.append(f"  MISSING type_id={type_id} ({name}) in tb_shop_type")
        elif db_rows[type_id] != name:
            errors.append(
                f"  NAME MISMATCH type_id={type_id}: JSON='{name}' DB='{db_rows[type_id]}'"
            )
    for type_id in db_rows:
        if type_id not in expected:
            errors.append(
                f"  EXTRA type_id={type_id} ({db_rows[type_id]}) in DB but not in taxonomy.json"
            )
    return errors


def check_badges(tax: dict, conn) -> list[str]:
    errors: list[str] = []
    expected_codes = {b["code"] for b in tax["badges"]}
    with conn.cursor() as cur:
        cur.execute("SELECT code FROM tb_badge_def WHERE is_active = 1")
        db_codes = {row[0] for row in cur.fetchall()}

    for code in expected_codes - db_codes:
        errors.append(f"  MISSING badge code='{code}' in tb_badge_def")
    for code in db_codes - expected_codes:
        errors.append(f"  EXTRA badge code='{code}' in DB but not in taxonomy.json")
    return errors


def check_tags(tax: dict, conn) -> list[str]:
    errors: list[str] = []
    expected_codes = {t["code"] for t in tax["tags"]}
    with conn.cursor() as cur:
        cur.execute("SELECT code FROM tb_tag_def WHERE is_active = 1")
        db_codes = {row[0] for row in cur.fetchall()}

    for code in expected_codes - db_codes:
        errors.append(f"  MISSING tag code='{code}' in tb_tag_def")
    for code in db_codes - expected_codes:
        errors.append(f"  EXTRA tag code='{code}' in DB but not in taxonomy.json")
    return errors


def main() -> None:
    tax = load_taxonomy()
    conn = get_conn()
    all_errors: list[str] = []

    print("Checking categories (tb_shop_type)...")
    errs = check_categories(tax, conn)
    all_errors.extend(errs)
    print(f"  {'OK' if not errs else f'FAIL ({len(errs)} issues)'}")

    print("Checking badges (tb_badge_def)...")
    errs = check_badges(tax, conn)
    all_errors.extend(errs)
    print(f"  {'OK' if not errs else f'FAIL ({len(errs)} issues)'}")

    print("Checking tags (tb_tag_def)...")
    errs = check_tags(tax, conn)
    all_errors.extend(errs)
    print(f"  {'OK' if not errs else f'FAIL ({len(errs)} issues)'}")

    conn.close()

    if all_errors:
        print("\nDIFF FOUND:")
        for e in all_errors:
            print(e)
        sys.exit(1)

    print("\nAll green — taxonomy.json in sync with DB.")


if __name__ == "__main__":
    main()
