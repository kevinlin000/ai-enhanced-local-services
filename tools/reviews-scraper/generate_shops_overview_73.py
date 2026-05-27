#!/usr/bin/env python3
from pathlib import Path

import pymysql


OUT = Path(__file__).resolve().parent / "shops_overview_73.txt"


def main() -> None:
    conn = pymysql.connect(
        host="localhost",
        port=3306,
        user="root",
        password="password",
        database="hmdp",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, address
                FROM tb_shop
                WHERE id BETWEEN 10099 AND 10171
                  AND is_active = 1
                ORDER BY id
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    lines = []
    for shop_id, name, address in rows:
        safe_name = (name or "").replace("|", " ").strip()
        safe_address = (address or "").replace("|", " ").replace("\n", " ").strip()
        lines.append(f"{shop_id}|{safe_name}|{safe_address}")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"generated {len(lines)} shops -> {OUT}")


if __name__ == "__main__":
    main()
