from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

DEFAULT_OVERRIDES_PATH = ROOT / "data" / "taxonomy" / "manual_overrides.json"


@dataclass(frozen=True)
class ShopRow:
    id: int
    name: str
    type_id: int
    tag_codes: tuple[str, ...] | None = None


@dataclass(frozen=True)
class PrimaryUpdate:
    shop_id: int
    name: str
    old_type_id: int
    new_type_id: int
    match: str


@dataclass(frozen=True)
class TagDelete:
    shop_id: int
    name: str
    tag_code: str
    match: str


@dataclass(frozen=True)
class SyncPlan:
    primary_updates: tuple[PrimaryUpdate, ...]
    tag_deletes: tuple[TagDelete, ...]
    primary_unchanged: int
    missing_matches: tuple[str, ...]


def load_overrides(path: Path = DEFAULT_OVERRIDES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _match_shops(shops: list[ShopRow], match: str) -> list[ShopRow]:
    needle = match.strip()
    if not needle:
        return []
    return [shop for shop in shops if needle in shop.name]


def build_sync_plan(overrides: dict, shops: list[ShopRow]) -> SyncPlan:
    primary_updates: list[PrimaryUpdate] = []
    tag_deletes_by_key: dict[tuple[int, str], TagDelete] = {}
    primary_unchanged = 0
    missing_matches: list[str] = []

    for row in overrides.get("primary_type_overrides", []):
        match = row["match"]
        matched_shops = _match_shops(shops, match)
        if not matched_shops:
            missing_matches.append(match)
            continue
        new_type_id = int(row["type_id"])
        for shop in matched_shops:
            if shop.type_id == new_type_id:
                primary_unchanged += 1
                continue
            primary_updates.append(
                PrimaryUpdate(
                    shop_id=shop.id,
                    name=shop.name,
                    old_type_id=shop.type_id,
                    new_type_id=new_type_id,
                    match=match,
                )
            )

    for row in overrides.get("suppress_tags", []):
        match = row["match"]
        matched_shops = _match_shops(shops, match)
        if not matched_shops:
            if match not in missing_matches:
                missing_matches.append(match)
            continue
        for tag_code in row.get("tags", []):
            for shop in matched_shops:
                if shop.tag_codes is not None and tag_code not in shop.tag_codes:
                    continue
                key = (shop.id, tag_code)
                tag_deletes_by_key[key] = TagDelete(
                    shop_id=shop.id,
                    name=shop.name,
                    tag_code=tag_code,
                    match=match,
                )

    return SyncPlan(
        primary_updates=tuple(primary_updates),
        tag_deletes=tuple(tag_deletes_by_key.values()),
        primary_unchanged=primary_unchanged,
        missing_matches=tuple(missing_matches),
    )


def connect_mysql():
    import pymysql

    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", "password"),
        database=os.getenv("MYSQL_DATABASE", "hmdp"),
        charset="utf8mb4",
        autocommit=False,
    )


def fetch_active_google_shops(conn) -> list[ShopRow]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, s.name, s.type_id, tag_rel.tag_codes
            FROM tb_shop s
            LEFT JOIN (
                SELECT shop_id, GROUP_CONCAT(tag_code ORDER BY tag_code SEPARATOR '||') AS tag_codes
                FROM tb_shop_tag
                GROUP BY shop_id
            ) tag_rel ON tag_rel.shop_id = s.id
            WHERE s.source = 'google_places' AND s.is_active = 1
            """
        )
        return [
            ShopRow(
                id=int(row[0]),
                name=str(row[1]),
                type_id=int(row[2]),
                tag_codes=tuple(str(row[3]).split("||")) if row[3] else (),
            )
            for row in cur.fetchall()
        ]


def apply_plan(conn, plan: SyncPlan) -> tuple[int, int]:
    with conn.cursor() as cur:
        for item in plan.primary_updates:
            cur.execute(
                "UPDATE tb_shop SET type_id = %s, update_time = NOW() WHERE id = %s",
                (item.new_type_id, item.shop_id),
            )
        deleted_tags = 0
        for item in plan.tag_deletes:
            deleted_tags += cur.execute(
                "DELETE FROM tb_shop_tag WHERE shop_id = %s AND tag_code = %s",
                (item.shop_id, item.tag_code),
            )
    return len(plan.primary_updates), deleted_tags


def print_plan(plan: SyncPlan, limit: int = 20) -> None:
    print(f"primary_updates={len(plan.primary_updates)}")
    print(f"tag_deletes={len(plan.tag_deletes)}")
    print(f"primary_unchanged={plan.primary_unchanged}")
    print(f"missing_matches={len(plan.missing_matches)}")

    for item in plan.primary_updates[:limit]:
        print(
            f"UPDATE shop_id={item.shop_id} {item.old_type_id}->{item.new_type_id} "
            f"name={item.name} match={item.match}"
        )
    for item in plan.tag_deletes[:limit]:
        print(f"DELETE_TAG shop_id={item.shop_id} tag={item.tag_code} name={item.name} match={item.match}")
    if plan.missing_matches:
        print("MISSING " + " | ".join(plan.missing_matches[:limit]))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply manual taxonomy overrides to the current MySQL shop table."
    )
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES_PATH)
    parser.add_argument("--write", action="store_true", help="Apply changes. Default is dry-run.")
    parser.add_argument(
        "--sync-qdrant",
        action="store_true",
        help="After --write, refresh Qdrant payload metadata without re-embedding.",
    )
    args = parser.parse_args()

    overrides = load_overrides(args.overrides)
    conn = connect_mysql()
    try:
        shops = fetch_active_google_shops(conn)
        plan = build_sync_plan(overrides, shops)
        print_plan(plan)
        if not args.write:
            print("dry_run=true")
            return 0

        updated, deleted = apply_plan(conn, plan)
        conn.commit()
        print(f"written=true primary_updated={updated} tags_deleted={deleted}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if args.sync_qdrant:
        from app.qdrant_loader import sync_payloads_only

        sync_payloads_only()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
