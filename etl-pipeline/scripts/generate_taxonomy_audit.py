#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
RAW_DIR = ROOT / "data" / "raw"
DEFAULT_CSV = PROJECT_ROOT / "docs" / "taxonomy-audit.csv"
DEFAULT_MD = PROJECT_ROOT / "docs" / "taxonomy-audit.md"

sys.path.append(str(ROOT))

from app import taxonomy  # noqa: E402

try:
    import pymysql
except Exception:  # pragma: no cover - optional local dependency
    pymysql = None

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional local dependency
    load_dotenv = None


CATEGORY_REASON = {
    2001: ("火鍋", taxonomy.HOTPOT_KEYWORDS),
    2002: ("日式燒肉", taxonomy.YAKINIKU_KEYWORDS),
    2003: ("居酒屋", taxonomy.IZAKAYA_KEYWORDS),
    2004: ("日式料理", taxonomy.JAPANESE_KEYWORDS),
    2005: ("素食", taxonomy.VEGETARIAN_KEYWORDS),
    2007: ("義法料理", taxonomy.EUROPEAN_KEYWORDS),
    2008: ("中式料理", taxonomy.CHINESE_KEYWORDS),
    2010: ("美式料理", taxonomy.BRUNCH_KEYWORDS | taxonomy.STEAK_TAG_KEYWORDS),
    2011: ("自助餐", taxonomy.BUFFET_KEYWORDS),
    2012: ("咖啡/甜點", taxonomy.CAFE_KEYWORDS),
}

HIGH_IMPACT_MIN_COMMENTS = 600
HIGH_IMPACT_MIN_SCORE = 43


@dataclass(frozen=True)
class AuditRow:
    priority: int
    shop_id: int
    name: str
    primary_type: str
    assigned_type_id: int
    assigned_category: str
    tags: str
    comments: int
    score: float
    flags: str
    suggestion: str
    evidence: str


def load_taxonomy_names() -> dict[int, str]:
    payload = json.loads((PROJECT_ROOT / "shared" / "taxonomy.json").read_text(encoding="utf-8"))
    return {int(item["type_id"]): str(item["name"]) for item in payload["categories"]}


def load_shops(raw_dir: Path) -> dict[int, dict]:
    shops: dict[int, dict] = {}
    for path in sorted(raw_dir.glob("places_extracted_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for shop in payload.get("shops", []):
            shop_id = shop.get("shop_id")
            if shop_id:
                shops[int(shop_id)] = shop
    return shops


def load_env() -> None:
    for path in (PROJECT_ROOT / ".env", ROOT / ".env", PROJECT_ROOT / "ai-service-python" / ".env"):
        if path.exists():
            if load_dotenv:
                load_dotenv(path, override=False)
            else:
                load_env_file(path)


def load_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip("'\"")
        os.environ[key] = value


def connect_db():
    if pymysql is None:
        raise RuntimeError("pymysql is not installed")
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


def load_db_shops() -> dict[int, dict]:
    sql = """
        SELECT
          s.id AS shop_id,
          s.name AS display_name,
          s.type_id AS current_type_id,
          s.comments,
          s.score,
          s.avg_price,
          s.area,
          s.address,
          t.name AS current_type_name,
          m.ai_summary,
          m.signature_dishes,
          m.atmosphere_tags,
          m.booking_difficulty,
          m.price_per_person,
          tag_rel.tag_codes
        FROM tb_shop s
        LEFT JOIN tb_shop_type t ON t.id = s.type_id
        LEFT JOIN tb_shop_ai_metadata m ON m.shop_id = s.id
        LEFT JOIN (
          SELECT shop_id, GROUP_CONCAT(tag_code ORDER BY tag_code SEPARATOR '、') AS tag_codes
          FROM tb_shop_tag
          GROUP BY shop_id
        ) tag_rel ON tag_rel.shop_id = s.id
        WHERE COALESCE(s.is_active, 1) = 1
        ORDER BY s.id
    """
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = list(cur.fetchall())

    shops: dict[int, dict] = {}
    for row in rows:
        shop_id = int(row["shop_id"])
        tags = [tag for tag in str(row.get("tag_codes") or "").split("、") if tag]
        shops[shop_id] = {
            "shop_id": shop_id,
            "display_name": row.get("display_name"),
            "current_type_id": int(row["current_type_id"]) if row.get("current_type_id") is not None else None,
            "current_type_name": row.get("current_type_name"),
            "comments": row.get("comments"),
            "score": row.get("score"),
            "avg_price": row.get("avg_price"),
            "area": row.get("area"),
            "address": row.get("address"),
            "db_tags": tags,
            "ai_extracted": {
                "ai_summary": row.get("ai_summary") or "",
                "signature_dishes": parse_json_list(row.get("signature_dishes")),
                "atmosphere_tags": parse_json_list(row.get("atmosphere_tags")),
                "booking_difficulty": row.get("booking_difficulty") or "",
                "price_per_person": row.get("price_per_person") or "",
            },
        }
    return shops


def parse_json_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    return [text]


def clean(value: object, limit: int = 120) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def score_value(shop: dict) -> float:
    value = shop.get("rating") or shop.get("score") or 0
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return score / 10 if score > 5 else score


def comments_value(shop: dict) -> int:
    value = shop.get("comments") or shop.get("user_ratings_total") or 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def keyword_hits(text: str, keywords: Iterable[str], limit: int = 5) -> list[str]:
    hits = [keyword for keyword in sorted(keywords, key=len, reverse=True) if keyword.lower() in text]
    return hits[:limit]


def category_matches(text: str) -> list[tuple[int, str, list[str]]]:
    matches: list[tuple[int, str, list[str]]] = []
    for type_id, (name, keywords) in CATEGORY_REASON.items():
        hits = keyword_hits(text, keywords)
        if hits:
            matches.append((type_id, name, hits))
    return matches


def suggestion_from_matches(assigned_type_id: int, matches: list[tuple[int, str, list[str]]]) -> str:
    if not matches:
        return "人工確認主分類"
    preferred = [item for item in matches if item[0] != assigned_type_id]
    if not preferred:
        return "保留分類，確認 tags 是否完整"
    type_id, name, hits = preferred[0]
    return f"檢查是否應改為 {name} ({type_id})；命中：{'、'.join(hits)}"


def build_audit_rows(shops: dict[int, dict], category_names: dict[int, str]) -> list[AuditRow]:
    rows: list[AuditRow] = []
    for shop_id, shop in sorted(shops.items()):
        is_db_shop = "current_type_id" in shop
        result = taxonomy.classify_shop(shop)
        assigned_type_id = int(shop["current_type_id"] or 0) if is_db_shop else int(result["primary_type_id"])
        assigned_category = category_names.get(assigned_type_id, str(assigned_type_id))
        classifier_tags = [str(tag) for tag in result.get("tags", [])]
        tags = [str(tag) for tag in (shop.get("db_tags") or classifier_tags)]
        text = taxonomy._build_text_blob(shop)
        primary_type = str(shop.get("primary_type") or "")
        matches = category_matches(text)
        flags: list[str] = []
        evidence_parts: list[str] = []

        if is_db_shop:
            primary_type = "db_current"
            if assigned_type_id not in category_names:
                flags.append("unknown_current_category")
        else:
            base_type_id = taxonomy._base_primary_type_id(shop)
            if primary_type in taxonomy.FALLBACK_PRIMARY_TYPE_VALUES:
                flags.append("broad_google_type")
            elif primary_type in taxonomy.AMBIGUOUS_PRIMARY_TYPE_VALUES:
                flags.append("ambiguous_google_type")
            elif primary_type and primary_type not in taxonomy.PRIMARY_TYPE_MAP:
                flags.append("unknown_google_type")

            if base_type_id != assigned_type_id:
                flags.append("classifier_changed_base_type")

        conflict_matches = [item for item in matches if item[0] != assigned_type_id]
        if conflict_matches:
            flags.append("keyword_conflict")
            evidence_parts.extend(
                f"{name}:{'、'.join(hits)}" for _, name, hits in conflict_matches[:3]
            )

        if assigned_type_id == 2008 and not keyword_hits(text, taxonomy.CHINESE_KEYWORDS):
            flags.append("defaulted_to_chinese")

        if "韓式" in tags or keyword_hits(text, taxonomy.KOREAN_TAG_KEYWORDS):
            flags.append("korean_tag_review")
            evidence_parts.append("韓式 tag")

        ai = shop.get("ai_extracted", {}) or {}
        if not clean(ai.get("ai_summary")) and not ai.get("signature_dishes"):
            flags.append("thin_ai_evidence")

        if not flags:
            continue

        comments = comments_value(shop)
        score = score_value(shop)
        if comments >= HIGH_IMPACT_MIN_COMMENTS or score >= HIGH_IMPACT_MIN_SCORE / 10:
            flags.append("high_impact")

        priority = 0
        priority += 35 if "keyword_conflict" in flags else 0
        priority += 30 if "defaulted_to_chinese" in flags else 0
        priority += 25 if "unknown_google_type" in flags else 0
        priority += 20 if "broad_google_type" in flags or "ambiguous_google_type" in flags else 0
        priority += 15 if "classifier_changed_base_type" in flags else 0
        priority += 12 if "korean_tag_review" in flags else 0
        priority += 10 if "thin_ai_evidence" in flags else 0
        priority += 10 if "high_impact" in flags else 0

        rows.append(
            AuditRow(
                priority=priority,
                shop_id=shop_id,
                name=clean(shop.get("display_name") or shop.get("name")),
                primary_type=primary_type or "-",
                assigned_type_id=assigned_type_id,
                assigned_category=assigned_category,
                tags="、".join(tags),
                comments=comments,
                score=score,
                flags=";".join(flags),
                suggestion=suggestion_from_matches(assigned_type_id, matches),
                evidence=clean("; ".join(evidence_parts) or ai.get("ai_summary"), 220),
            )
        )

    return sorted(rows, key=lambda row: (-row.priority, -row.comments, row.shop_id))


def write_csv(rows: list[AuditRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(AuditRow.__dataclass_fields__.keys()),
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def write_markdown(rows: list[AuditRow], shops: dict[int, dict], category_names: dict[int, str], path: Path, limit: int) -> None:
    category_counts = Counter(
        int(shop["current_type_id"] or 0) if "current_type_id" in shop else int(taxonomy.classify_shop(shop)["primary_type_id"])
        for shop in shops.values()
    )
    tag_counts = Counter(
        tag
        for shop in shops.values()
        for tag in (shop.get("db_tags") or taxonomy.classify_shop(shop).get("tags", []))
    )
    flag_counts = Counter(flag for row in rows for flag in row.flags.split(";") if flag)
    korean_rows = [row for row in rows if "korean_tag_review" in row.flags]

    lines = [
        "# Taxonomy Audit",
        "",
        f"- Unique shops scanned: {len(shops)}",
        f"- Audit rows: {len(rows)}",
        f"- Korean-tagged rows needing review: {len(korean_rows)}",
        "",
        "## Category Distribution",
        "",
    ]
    for type_id, name in sorted(category_names.items()):
        lines.append(f"- {type_id} {name}: {category_counts.get(type_id, 0)}")

    lines.extend([
        "",
        "## Tag Distribution",
        "",
    ])
    for tag, count in tag_counts.most_common():
        lines.append(f"- {tag}: {count}")

    lines.extend([
        "",
        "## Flag Distribution",
        "",
    ])
    for flag, count in flag_counts.most_common():
        lines.append(f"- {flag}: {count}")

    lines.extend([
        "",
        "## Recommendation",
        "",
        "- Keep `日式料理` as a Japanese-only primary category for now.",
        "- Keep Korean as the `韓式` tag unless the reviewed Korean-tagged shop count becomes large enough to justify a dedicated primary category.",
        "- Do not rename `日式料理` to `日韓料理`: Korean intent crosses yakiniku, hotpot, bistro, and general restaurants, so a tag preserves clearer retrieval semantics.",
        "- Review high-priority rows first, then add classifier overrides or DB migrations for confirmed fixes.",
        "",
        f"## Top {min(limit, len(rows))} Review Rows",
        "",
        "| priority | shop_id | name | category | tags | flags | suggestion | evidence |",
        "| ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ])
    for row in rows[:limit]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.priority),
                    str(row.shop_id),
                    row.name.replace("|", "\\|"),
                    row.assigned_category.replace("|", "\\|"),
                    row.tags.replace("|", "\\|"),
                    row.flags.replace("|", "\\|"),
                    row.suggestion.replace("|", "\\|"),
                    row.evidence.replace("|", "\\|"),
                ]
            )
            + " |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ByteBites taxonomy audit reports.")
    parser.add_argument("--source", choices=["auto", "db", "raw"], default="auto")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    category_names = load_taxonomy_names()
    source = args.source
    if source in {"auto", "db"}:
        try:
            shops = load_db_shops()
            source = "db"
        except Exception as exc:
            if args.source == "db":
                raise
            print(f"db unavailable, falling back to raw: {exc}")
            shops = load_shops(args.raw_dir)
            source = "raw"
    else:
        shops = load_shops(args.raw_dir)
    rows = build_audit_rows(shops, category_names)
    write_csv(rows, args.csv)
    write_markdown(rows, shops, category_names, args.md, max(1, args.limit))
    print(f"source={source} scanned={len(shops)} audit_rows={len(rows)} csv={args.csv} md={args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
