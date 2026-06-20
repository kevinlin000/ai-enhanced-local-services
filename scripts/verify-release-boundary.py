#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "release-boundary.md"
SCORECARD = ROOT / "docs" / "portfolio-readiness-scorecard.md"
ROADMAP_100 = ROOT / "docs" / "portfolio-100-roadmap.md"
EVIDENCE_PACKAGE = ROOT / "docs" / "demo-evidence-package.md"
ARCHITECTURE_OVERVIEW = ROOT / "docs" / "architecture-overview.md"
SCRIPT = ROOT / "scripts" / "release-readiness.sh"


def fail(message: str) -> None:
    print(f"RELEASE BOUNDARY CHECK FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(text: str, snippet: str, label: str) -> None:
    if snippet not in text:
        fail(f"missing {label}: {snippet}")


def main() -> None:
    try:
        doc = DOC.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing release boundary doc: {DOC.relative_to(ROOT)}")

    try:
        script = SCRIPT.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing release readiness script: {SCRIPT.relative_to(ROOT)}")

    try:
        scorecard = SCORECARD.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing portfolio readiness scorecard: {SCORECARD.relative_to(ROOT)}")

    try:
        roadmap_100 = ROADMAP_100.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing portfolio 100 roadmap: {ROADMAP_100.relative_to(ROOT)}")

    try:
        evidence_package = EVIDENCE_PACKAGE.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing demo evidence package: {EVIDENCE_PACKAGE.relative_to(ROOT)}")

    try:
        architecture_overview = ARCHITECTURE_OVERVIEW.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing architecture overview: {ARCHITECTURE_OVERVIEW.relative_to(ROOT)}")

    required_doc_snippets = {
        "release thesis": "AI can orchestrate the dining workflow, but Java remains the source of truth",
        "dry run": "scripts/release-readiness.sh --dry-run",
        "offline gate": "scripts/release-readiness.sh --offline",
        "full gate": "scripts/release-readiness.sh --full",
        "live local": "scripts/release-readiness.sh --live-local --base-url http://localhost:8088",
        "portfolio verifier": "scripts/verify-portfolio.sh",
        "readiness scorecard": "docs/portfolio-readiness-scorecard.md",
        "portfolio 100 roadmap": "docs/portfolio-100-roadmap.md",
        "demo evidence package": "docs/demo-evidence-package.md",
        "architecture overview": "docs/architecture-overview.md",
        "readiness score": "88 / 100",
        "clean mysql smoke": "scripts/smoke-clean-mysql-migrations.sh --timeout 180",
        "demo readiness": "scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict",
        "github workflow": ".github/workflows/clean-mysql-migration-smoke.yml",
        "commit grouping": "Commit Grouping",
        "production gaps": "Production Gaps",
    }
    for label, snippet in required_doc_snippets.items():
        require(doc, snippet, label)

    required_scorecard_snippets = {
        "overall score": "Portfolio readiness: 88 / 100",
        "portfolio yes": "Yes for portfolio interviews.",
        "production no": "Not yet for production SaaS rollout.",
        "java score": "Java backend",
        "ai score": "AI application engineer",
        "full stack score": "Full-stack engineer",
        "evidence package": "Step 1: Evidence Package",
        "100-point path": "Step 0: Define The 100-Point Path",
        "portfolio 100 roadmap": "docs/portfolio-100-roadmap.md",
        "demo evidence package": "docs/demo-evidence-package.md",
        "architecture overview": "docs/architecture-overview.md",
        "stop feature creep": "Stop Adding Features For Now",
    }
    for label, snippet in required_scorecard_snippets.items():
        require(scorecard, snippet, label)

    required_roadmap_100_snippets = {
        "two 100s": "Two Different 100s",
        "portfolio 100": "Portfolio 100",
        "production saas 100": "Production SaaS 100",
        "current score": "88 / 100",
        "evidence package": "docs/demo-evidence-package.md",
        "architecture overview": "docs/architecture-overview.md",
        "production roadmap": "Production 100 Roadmap",
    }
    for label, snippet in required_roadmap_100_snippets.items():
        require(roadmap_100, snippet, label)

    required_evidence_package_snippets = {
        "ai screenshot": "01-ai-recommendation.png",
        "incident screenshot": "03-realtime-incident.png",
        "line screenshot": "05-line-rescue-card.png",
        "ci screenshot": "07-ci-portfolio-green.png",
        "architecture screenshot": "09-architecture-overview.png",
        "live fallback": "scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict",
        "production gap answer": "Production Gap Answer",
    }
    for label, snippet in required_evidence_package_snippets.items():
        require(evidence_package, snippet, label)

    required_architecture_snippets = {
        "state boundary": "AI orchestrates the dining workflow.",
        "java owns state": "Java owns business state.",
        "mermaid": "flowchart LR",
        "nginx": "Nginx public boundary",
        "java source of truth": "Spring Boot Java",
        "critical flow": "Real-time incident handling is the best single architecture example",
        "verification": "scripts/verify-portfolio.sh",
    }
    for label, snippet in required_architecture_snippets.items():
        require(architecture_overview, snippet, label)

    required_script_snippets = {
        "dry run option": "--dry-run",
        "offline option": "--offline",
        "full option": "--full",
        "live local option": "--live-local",
        "base url option": "--base-url",
        "portfolio invocation": "scripts/verify-portfolio.sh",
        "nginx verifier": "python3 scripts/verify-nginx-template.py",
        "clean workflow verifier": "python3 scripts/verify-clean-migration-workflow.py",
        "release verifier": "python3 scripts/verify-release-boundary.py",
        "data verifier": "python3 scripts/verify-data-quality.py",
        "clean mysql live": "scripts/smoke-clean-mysql-migrations.sh --timeout",
        "demo readiness live": "scripts/demo-readiness.sh --base-url",
        "dry run checklist": "ByteBites release readiness dry run",
    }
    for label, snippet in required_script_snippets.items():
        require(script, snippet, label)

    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    subprocess.run([str(SCRIPT), "--dry-run"], check=True, stdout=subprocess.DEVNULL)

    print("release boundary: readiness contract passed")


if __name__ == "__main__":
    main()
