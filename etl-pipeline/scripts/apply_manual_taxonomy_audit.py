from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DEFAULT_OVERRIDES_PATH = ROOT / "data" / "taxonomy" / "manual_overrides.json"
DEFAULT_TAXONOMY_PATH = REPO_ROOT / "shared" / "taxonomy.json"

ACTION_RE = re.compile(r"(?:改為|改成|維持|分類為|歸類為|是)")
SKIP_PREFIXES = ("###", "💡", "》", "目前", "這批", "以下", "關於")

CATEGORY_ALIASES = {
    "咖啡甜點": "咖啡/甜點",
    "咖啡廳": "咖啡/甜點",
    "甜點": "咖啡/甜點",
    "印度料理": "異國料理",
    "泰式料理": "異國料理",
    "泰國菜": "異國料理",
    "馬來西亞料理": "異國料理",
    "中東料理": "異國料理",
    "以色列料理": "異國料理",
    "西式料理": "義法料理",
    "義式料理": "義法料理",
    "法式料理": "義法料理",
    "日式豬排": "日式料理",
    "日式咖哩": "日式料理",
    "韓式": "韓式料理",
    "韓國料理": "韓式料理",
}


@dataclass(frozen=True)
class ParsedAuditRow:
    match: str
    type_id: int | None = None
    suppress_tags: tuple[str, ...] = ()
    source_line: str = ""


def _clean_name(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"^[>*\-\s•]+", "", cleaned)
    cleaned = re.sub(r"^\d+[.)、]\s*", "", cleaned)
    cleaned = cleaned.strip(" ：:，,。")
    return cleaned.strip()


def _strip_notes(value: str) -> str:
    return re.split(r"[（(【\[]", value, maxsplit=1)[0].strip()


def load_category_name_to_type_id(path: Path = DEFAULT_TAXONOMY_PATH) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    names = {item["name"]: int(item["type_id"]) for item in payload["categories"]}
    for alias, canonical in CATEGORY_ALIASES.items():
        if canonical in names:
            names[alias] = names[canonical]
    return names


def _category_candidates(
    text: str,
    category_name_to_type_id: dict[str, int],
    offset: int = 0,
) -> list[tuple[int, str, int]]:
    matches: list[tuple[int, str, int]] = []
    for name, type_id in category_name_to_type_id.items():
        index = text.find(name)
        if index >= 0:
            matches.append((offset + index, name, type_id))
    return matches


def _find_category(line: str, category_name_to_type_id: dict[str, int]) -> tuple[str, int, int] | None:
    matches: list[tuple[int, str, int]] = []
    action_matches = list(ACTION_RE.finditer(line))
    if action_matches:
        decision_start = action_matches[-1].end()
        decision_text = _strip_notes(line[decision_start:])
        matches = _category_candidates(decision_text, category_name_to_type_id, decision_start)

    if not matches:
        matches = _category_candidates(line, category_name_to_type_id)
    if not matches:
        return None
    # Prefer the rightmost category so context before the final decision does not win.
    index, name, type_id = sorted(matches, key=lambda item: (item[0], len(item[1])))[-1]
    return name, type_id, index


def _extract_name(line: str, category_index: int) -> str:
    prefix = line[:category_index]
    action_matches = list(ACTION_RE.finditer(prefix))
    if action_matches:
        prefix = prefix[: action_matches[-1].start()]
    return _clean_name(_strip_notes(prefix))


def _should_suppress_korean_tag(line: str) -> bool:
    lowered = line.lower()
    return (
        "韓式" in line
        and (
            "移除" in line
            or "刪除" in line
            or "沒有韓式" in line
            or "無韓式" in line
            or "不是韓式" in line
            or "no korean" in lowered
        )
    )


def parse_audit_text(text: str, category_name_to_type_id: dict[str, int] | None = None) -> list[ParsedAuditRow]:
    category_name_to_type_id = category_name_to_type_id or load_category_name_to_type_id()
    rows: list[ParsedAuditRow] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(SKIP_PREFIXES):
            continue
        line = re.sub(r"^\*+\s*", "", line)
        category = _find_category(line, category_name_to_type_id)
        if not category:
            continue
        _category_name, type_id, category_index = category
        match = _extract_name(line, category_index)
        if not match:
            continue
        suppress_tags = ("韓式",) if _should_suppress_korean_tag(line) else ()
        rows.append(
            ParsedAuditRow(
                match=match,
                type_id=type_id,
                suppress_tags=suppress_tags,
                source_line=raw_line,
            )
        )
    return rows


def load_overrides(path: Path = DEFAULT_OVERRIDES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_rows(payload: dict, rows: list[ParsedAuditRow]) -> tuple[dict, dict[str, int]]:
    next_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    stats = {
        "primary_added": 0,
        "primary_updated": 0,
        "primary_unchanged": 0,
        "suppress_added": 0,
        "suppress_unchanged": 0,
    }

    primary_rows = next_payload.setdefault("primary_type_overrides", [])
    primary_by_match = {row["match"]: row for row in primary_rows}
    suppress_rows = next_payload.setdefault("suppress_tags", [])
    suppress_by_match = {row["match"]: row for row in suppress_rows}

    for row in rows:
        if row.type_id is not None:
            existing = primary_by_match.get(row.match)
            if existing is None:
                item = {"match": row.match, "type_id": row.type_id, "source": "manual_audit"}
                primary_rows.append(item)
                primary_by_match[row.match] = item
                stats["primary_added"] += 1
            elif int(existing["type_id"]) != row.type_id:
                existing["type_id"] = row.type_id
                existing["source"] = "manual_audit"
                stats["primary_updated"] += 1
            else:
                stats["primary_unchanged"] += 1

        if "韓式" in row.suppress_tags:
            existing = suppress_by_match.get(row.match)
            if existing is None:
                item = {"match": row.match, "tags": ["韓式"], "source": "manual_audit"}
                suppress_rows.append(item)
                suppress_by_match[row.match] = item
                stats["suppress_added"] += 1
            elif existing.get("tags") == ["韓式"]:
                stats["suppress_unchanged"] += 1
            else:
                existing["tags"] = ["韓式"]
                existing["source"] = "manual_audit"
                stats["suppress_added"] += 1

    return next_payload, stats


def write_overrides(payload: dict, path: Path = DEFAULT_OVERRIDES_PATH) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply human-reviewed taxonomy audit text to manual_overrides.json.")
    parser.add_argument("--input", "-i", default="-", help="Input text file. Use '-' for stdin.")
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES_PATH)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY_PATH)
    parser.add_argument("--write", action="store_true", help="Write manual_overrides.json. Default is dry-run.")
    args = parser.parse_args()

    category_map = load_category_name_to_type_id(args.taxonomy)
    rows = parse_audit_text(_read_input(args.input), category_map)
    payload = load_overrides(args.overrides)
    next_payload, stats = apply_rows(payload, rows)

    print(f"parsed_rows={len(rows)}")
    for key, value in stats.items():
        print(f"{key}={value}")

    if args.write:
        write_overrides(next_payload, args.overrides)
        print(f"written={args.overrides}")
    else:
        print("dry_run=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
