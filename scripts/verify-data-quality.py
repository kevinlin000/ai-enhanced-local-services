#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CONVERSATION_CASE_IDS = {
    "web_vague_group_need_clarifies",
    "web_exact_recommended_shop_booking_draft",
    "web_booking_draft_edit_time",
    "web_booking_draft_switch_shop",
    "line_exact_recommended_shop_booking_draft",
    "line_booking_draft_edit_time",
    "line_negative_selection_more_results",
    "demo_story_department_group_recommends_with_reasons",
    "demo_story_family_driving_recommends_with_parking",
    "hard_constraint_business_taiwanese",
    "hard_constraint_korean_cuisine",
}

COVERAGE_THRESHOLDS = {
    "Cover image/media": 100.0,
    "Price signal": 85.0,
    "District": 100.0,
    "MRT station": 25.0,
    "AI summary": 100.0,
    "ABSA": 99.0,
    "Mongo reviews": 99.0,
    "Media manifest entry": 100.0,
    "Media manifest reviews": 99.0,
    "Media manifest photos": 100.0,
    "Media manifest overview": 95.0,
}

MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")

MARKDOWN_LINK_ROOTS = (
    "README.md",
    "README.en.md",
    "CONTEXT-MAP.md",
    "docs",
    "ai-service-python/README.md",
    "ai-service-python/CONTEXT.md",
    "ai-service-python/docs",
    "ai-service-python/evals/README.md",
    "backend-java/CONTEXT.md",
    "etl-pipeline/README.md",
    "etl-pipeline/CONTEXT.md",
    "etl-pipeline/data/taxonomy/README.md",
    "web/README.md",
    "web/CONTEXT.md",
    "deploy/grafana/README.md",
    "tools/reviews-scraper/README.md",
    "tools/reviews-scraper/tests/README.md",
)

IGNORED_DOC_PARTS = {"_internal"}


def fail(message: str) -> None:
    print(f"DATA QUALITY GATE FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing file: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")


def read_jsonl(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        fail(f"missing file: {path.relative_to(ROOT)}")
    rows = []
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            fail(f"invalid JSONL at {path.relative_to(ROOT)}:{line_no}: {exc}")
    return rows


def percent_value(value: str | float | int) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).strip().removesuffix("%"))


def public_markdown_files() -> list[Path]:
    files: list[Path] = []
    for root_name in MARKDOWN_LINK_ROOTS:
        root = ROOT / root_name
        if root.is_file():
            files.append(root)
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            relative_parts = path.relative_to(ROOT).parts
            if any(part in IGNORED_DOC_PARTS for part in relative_parts):
                continue
            files.append(path)
    return sorted(set(files))


def markdown_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split()[0]
    return unquote(target.strip())


def is_external_or_anchor(target: str) -> bool:
    lowered = target.lower()
    return (
        not target
        or target.startswith("#")
        or lowered.startswith(("http://", "https://", "mailto:", "tel:"))
    )


def verify_markdown_links() -> None:
    checked = 0
    for path in public_markdown_files():
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in MARKDOWN_LINK_PATTERN.finditer(line):
                target = markdown_link_target(match.group(1))
                if is_external_or_anchor(target):
                    continue
                target_path = target.split("#", 1)[0]
                if not target_path:
                    continue
                resolved = (path.parent / target_path).resolve()
                try:
                    resolved.relative_to(ROOT)
                except ValueError:
                    fail(f"markdown link escapes repo: {path.relative_to(ROOT)}:{line_no} -> {target}")
                if not resolved.exists():
                    fail(f"broken markdown link: {path.relative_to(ROOT)}:{line_no} -> {target}")
                checked += 1
    print(f"markdown links: {checked} local reviewer-facing links passed")


def verify_data_coverage() -> None:
    report = read_json(ROOT / "docs" / "data-coverage-report.json")
    total_shops = int(report.get("total_shops") or 0)
    if total_shops < 600:
        fail(f"expected at least 600 shops, got {total_shops}")

    coverage = {
        str(item.get("label")): percent_value(item.get("percent", 0))
        for item in report.get("coverage", [])
        if isinstance(item, dict)
    }
    for label, minimum in COVERAGE_THRESHOLDS.items():
        actual = coverage.get(label)
        if actual is None:
            fail(f"coverage metric missing: {label}")
        if actual < minimum:
            fail(f"{label} coverage {actual:.1f}% is below {minimum:.1f}%")

    print(f"data coverage: {total_shops} shops, {len(COVERAGE_THRESHOLDS)} metrics passed")


def verify_conversation_quality_cases() -> None:
    cases = read_jsonl(ROOT / "ai-service-python" / "evals" / "conversation_quality_cases.jsonl")
    ids = {str(case.get("id")) for case in cases}
    if ids != EXPECTED_CONVERSATION_CASE_IDS:
        missing = sorted(EXPECTED_CONVERSATION_CASE_IDS - ids)
        extra = sorted(ids - EXPECTED_CONVERSATION_CASE_IDS)
        fail(f"conversation quality case ids changed; missing={missing}, extra={extra}")
    for case in cases:
        if not case.get("surface") or not case.get("query") or not case.get("quality_gate"):
            fail(f"conversation case is missing surface/query/quality_gate: {case.get('id')}")
    print(f"conversation quality cases: {len(cases)} cases passed")


def verify_agent_eval_manifests() -> None:
    concierge_cases = read_jsonl(ROOT / "ai-service-python" / "evals" / "agent_concierge_cases.jsonl")
    rag_cases = read_jsonl(ROOT / "ai-service-python" / "evals" / "dataset.jsonl")
    if len(concierge_cases) < 10:
        fail(f"expected at least 10 concierge eval cases, got {len(concierge_cases)}")
    if len(rag_cases) < 15:
        fail(f"expected at least 15 RAG eval cases, got {len(rag_cases)}")
    concierge_ids = [case.get("id") for case in concierge_cases]
    if len(set(concierge_ids)) != len(concierge_ids):
        fail("agent_concierge_cases.jsonl contains duplicate ids")
    print(f"agent eval manifests: {len(concierge_cases)} concierge + {len(rag_cases)} RAG cases passed")


def verify_taxonomy_docs() -> None:
    taxonomy = read_json(ROOT / "shared" / "taxonomy.json")
    categories = {item.get("name") for item in taxonomy.get("categories", []) if isinstance(item, dict)}
    for required in ("中式料理", "日式料理", "韓式料理", "火鍋"):
        if required not in categories:
            fail(f"taxonomy missing category: {required}")
    if "日韓料理" in categories:
        fail("obsolete combined category 日韓料理 should not exist")

    spec = (ROOT / "docs" / "taxonomy-spec.md").read_text(encoding="utf-8")
    if "`韓式料理` is already a primary category" not in spec:
        fail("taxonomy spec is missing Korean primary-category decision note")
    print("taxonomy docs: categories and spec decisions passed")


def verify_case_studies() -> None:
    index_path = ROOT / "docs" / "case-studies" / "README.md"
    index = index_path.read_text(encoding="utf-8")
    for number in range(1, 15):
        matches = sorted((ROOT / "docs" / "case-studies").glob(f"{number:02d}-*.md"))
        if not matches:
            fail(f"missing case study {number:02d}")
        relative_name = matches[0].name
        if relative_name not in index:
            fail(f"case study {relative_name} is not linked from docs/case-studies/README.md")
    print("case studies: 14 linked engineering cases passed")


def verify_portfolio_evidence_map() -> None:
    evidence_path = ROOT / "docs" / "portfolio-evidence-map.md"
    try:
        evidence = evidence_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail("missing portfolio evidence map")
    required_phrases = (
        "Java Backend Track",
        "AI Application Track",
        "Full-Stack Track",
        "scripts/verify-portfolio.sh",
        "scripts/release-readiness.sh",
        "docs/release-boundary.md",
        "BookingSlotInventory",
        "booking_draft.py",
        ".github/workflows/portfolio-ci.yml",
        ".github/workflows/clean-mysql-migration-smoke.yml",
    )
    for phrase in required_phrases:
        if phrase not in evidence:
            fail(f"portfolio evidence map missing phrase: {phrase}")
    print("portfolio evidence map: reviewer anchors passed")


def main() -> None:
    verify_data_coverage()
    verify_conversation_quality_cases()
    verify_agent_eval_manifests()
    verify_taxonomy_docs()
    verify_case_studies()
    verify_portfolio_evidence_map()
    verify_markdown_links()
    print("Data quality gate passed.")


if __name__ == "__main__":
    main()
