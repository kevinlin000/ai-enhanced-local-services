#!/usr/bin/env python3
import json
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "etl-pipeline" / "data" / "raw"
OUT = Path(__file__).resolve().parent / "shops_next30.txt"


def latest_raw_file() -> Path:
    files = sorted(RAW_DIR.glob("places_extracted_*.json"))
    if not files:
        raise SystemExit("no places_extracted_*.json found")
    return files[-1]


def load_raw_shops() -> list[dict]:
    raw = json.loads(latest_raw_file().read_text())
    return raw["shops"]


def fetch_shop_id_map() -> dict[str, tuple[int, str]]:
    load_dotenv(ROOT / "etl-pipeline" / ".env")
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT place_id, id, name
                FROM tb_shop
                WHERE source='google_places' AND is_active=1
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return {place_id: (shop_id, name) for place_id, shop_id, name in rows if place_id}


def main() -> None:
    raw_shops = load_raw_shops()
    id_map = fetch_shop_id_map()
    lines: list[str] = []
    missing: list[str] = []

    for shop in raw_shops:
        place_id = shop.get("place_id")
        display_name = (shop.get("display_name") or "").replace("|", " ")
        if not place_id or place_id not in id_map:
            missing.append(display_name or place_id or "unknown")
            continue
        shop_id, db_name = id_map[place_id]
        name = (db_name or display_name).replace("|", " ")
        lines.append(f"{place_id}|{name}|{shop_id}")

    OUT.write_text("\n".join(lines) + "\n")
    print(f"generated {len(lines)} shops -> {OUT}")
    if missing:
        print(f"missing mappings: {len(missing)}")
        for item in missing[:10]:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
