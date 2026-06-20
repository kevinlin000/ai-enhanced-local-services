#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "release-boundary.md"
SCORECARD = ROOT / "docs" / "portfolio-readiness-scorecard.md"
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

    required_doc_snippets = {
        "release thesis": "AI can orchestrate the dining workflow, but Java remains the source of truth",
        "dry run": "scripts/release-readiness.sh --dry-run",
        "offline gate": "scripts/release-readiness.sh --offline",
        "full gate": "scripts/release-readiness.sh --full",
        "live local": "scripts/release-readiness.sh --live-local --base-url http://localhost:8088",
        "portfolio verifier": "scripts/verify-portfolio.sh",
        "readiness scorecard": "docs/portfolio-readiness-scorecard.md",
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
        "stop feature creep": "Stop Adding Features For Now",
    }
    for label, snippet in required_scorecard_snippets.items():
        require(scorecard, snippet, label)

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
