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
RECORDING_SCRIPT = ROOT / "docs" / "demo-recording-script.md"
RECORDING_CLOUD_PLAN = ROOT / "docs" / "demo-recording-cloud-plan.md"
ARCHITECTURE_OVERVIEW = ROOT / "docs" / "architecture-overview.md"
SYSTEM_DESIGN_PACK = ROOT / "docs" / "system-design-interview-pack.md"
PERFORMANCE_QUERY_EVIDENCE = ROOT / "docs" / "performance-query-evidence.md"
ER_MODEL = ROOT / "docs" / "er-model-booking-operations.md"
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
        recording_script = RECORDING_SCRIPT.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing recording script: {RECORDING_SCRIPT.relative_to(ROOT)}")

    try:
        recording_cloud_plan = RECORDING_CLOUD_PLAN.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing recording and cloud plan: {RECORDING_CLOUD_PLAN.relative_to(ROOT)}")

    try:
        architecture_overview = ARCHITECTURE_OVERVIEW.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing architecture overview: {ARCHITECTURE_OVERVIEW.relative_to(ROOT)}")

    try:
        system_design_pack = SYSTEM_DESIGN_PACK.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing system design interview pack: {SYSTEM_DESIGN_PACK.relative_to(ROOT)}")

    try:
        performance_query_evidence = PERFORMANCE_QUERY_EVIDENCE.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing performance query evidence: {PERFORMANCE_QUERY_EVIDENCE.relative_to(ROOT)}")

    try:
        er_model = ER_MODEL.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing ER model doc: {ER_MODEL.relative_to(ROOT)}")

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
        "recording script": "docs/demo-recording-script.md",
        "recording cloud plan": "docs/demo-recording-cloud-plan.md",
        "architecture overview": "docs/architecture-overview.md",
        "system design interview pack": "docs/system-design-interview-pack.md",
        "performance query evidence": "docs/performance-query-evidence.md",
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
        "recording script": "docs/demo-recording-script.md",
        "recording cloud plan": "docs/demo-recording-cloud-plan.md",
        "architecture overview": "docs/architecture-overview.md",
        "system design interview pack": "docs/system-design-interview-pack.md",
        "performance query evidence": "docs/performance-query-evidence.md",
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
        "recording cloud plan": "docs/demo-recording-cloud-plan.md",
        "architecture overview": "docs/architecture-overview.md",
        "system design interview pack": "docs/system-design-interview-pack.md",
        "performance query evidence": "docs/performance-query-evidence.md",
        "production roadmap": "Production 100 Roadmap",
    }
    for label, snippet in required_roadmap_100_snippets.items():
        require(roadmap_100, snippet, label)

    required_evidence_package_snippets = {
        "homepage screenshot": "00-homepage-product-thesis.png",
        "ai screenshot": "01-ai-recommendation-cards.png",
        "booking incident screenshot": "02-booking-payment-incident.png",
        "line screenshot": "05-line-rescue-card.png",
        "refund screenshot": "06-refund-operations-digest.png",
        "ci screenshot": "07-ci-portfolio-green.png",
        "clean migration screenshot": "08-clean-migration-smoke.png",
        "architecture screenshot": "09-architecture-overview.png",
        "er model screenshot": "10-er-model-booking-operations.png",
        "er model doc": "docs/er-model-booking-operations.md",
        "live fallback": "scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict",
        "production gap answer": "Production Gap Answer",
        "recording script": "docs/demo-recording-script.md",
        "recording cloud plan": "docs/demo-recording-cloud-plan.md",
        "system design interview pack": "docs/system-design-interview-pack.md",
        "performance query evidence": "docs/performance-query-evidence.md",
    }
    for label, snippet in required_evidence_package_snippets.items():
        require(evidence_package, snippet, label)

    required_recording_script_snippets = {
        "recording goal": "AI orchestrates the workflow, while Java owns booking, payment, incident, and refund state.",
        "5 minute walkthrough": "5-Minute Walkthrough",
        "3 minute cut": "3-Minute Cut",
        "12 minute interview": "12-Minute Interview Version",
        "screenshot order": "Screenshot Capture Order",
        "recording checklist": "Recording Checklist",
        "opening lines": "Opening Lines",
        "closing lines": "Closing Lines",
        "live smoke": "scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict",
    }
    for label, snippet in required_recording_script_snippets.items():
        require(recording_script, snippet, label)

    required_recording_cloud_snippets = {
        "recommended order": "recorded walkthrough first",
        "personal voiceover": "Record it personally with voiceover.",
        "cloud decision": "Cloud Decision",
        "stable portfolio cloud": "Stable portfolio demo cloud",
        "production saas cloud": "Production SaaS cloud",
        "managed secrets": "Managed secrets",
        "observability": "Observability",
        "psp refund": "PSP refund provider",
        "interview answer": "I treated portfolio readiness and production rollout as separate gates.",
    }
    for label, snippet in required_recording_cloud_snippets.items():
        require(recording_cloud_plan, snippet, label)

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

    required_system_design_snippets = {
        "title": "ByteBites System Design Interview Pack",
        "core thesis": "AI orchestrates the dining workflow.",
        "java state": "Java owns booking, payment, incident, and refund state.",
        "architecture boundary": "Architecture Boundary",
        "booking incident flow": "Booking And Incident Flow",
        "consistency model": "Consistency Model",
        "data model defense": "Data Model Defense",
        "ai reliability boundary": "AI Reliability Boundary",
        "failure modes": "Failure Modes",
        "verification story": "Verification Story",
        "production rollout answer": "Production Rollout Answer",
        "question bank": "Interview Question Bank",
    }
    for label, snippet in required_system_design_snippets.items():
        require(system_design_pack, snippet, label)

    required_performance_query_snippets = {
        "title": "ByteBites Performance And Query Evidence",
        "query path map": "Query Path Map",
        "slot reservation": "Slot Reservation",
        "refund operations": "Refund Operations",
        "verifier": "python3 scripts/verify-performance-query-evidence.py",
        "no overclaim": "This evidence does not prove production-scale throughput.",
        "next performance work": "Next Performance Work",
    }
    for label, snippet in required_performance_query_snippets.items():
        require(performance_query_evidence, snippet, label)

    required_er_model_snippets = {
        "er title": "ByteBites Booking Operations ER Model",
        "booking table": "tb_booking",
        "incident table": "tb_booking_incident",
        "deposit adjustment table": "tb_booking_deposit_adjustment",
        "refund audit table": "tb_booking_refund_reconciliation_event",
        "merchant auth table": "tb_merchant_shop",
        "booking code point": "booking_code",
        "proposal tradeoff": "one incident, one pending proposal",
        "money movement separation": "separates booking mutation from money movement",
    }
    for label, snippet in required_er_model_snippets.items():
        require(er_model, snippet, label)

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
        "performance verifier": "python3 scripts/verify-performance-query-evidence.py",
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
