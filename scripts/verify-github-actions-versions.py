#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

REQUIRED_SNIPPETS = {
    "portfolio checkout": "actions/checkout@v7",
    "portfolio java setup": "actions/setup-java@v5",
    "portfolio python setup": "actions/setup-python@v6",
    "portfolio node setup": "actions/setup-node@v6",
    "portfolio pnpm setup": "pnpm/action-setup@v6.0.9",
    "portfolio uv setup": "astral-sh/setup-uv@v8.2.0",
    "clean smoke checkout": "actions/checkout@v7",
    "clean smoke java setup": "actions/setup-java@v5",
}

BANNED_SNIPPETS = (
    "actions/checkout@v4",
    "actions/setup-java@v4",
    "actions/setup-python@v5",
    "actions/setup-node@v4",
    "pnpm/action-setup@v4",
    "astral-sh/setup-uv@v5",
)


def fail(message: str) -> None:
    print(f"GITHUB ACTIONS VERSION CHECK FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not WORKFLOW_DIR.exists():
        fail("missing .github/workflows")

    workflows = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(WORKFLOW_DIR.glob("*.yml"))
    }
    joined = "\n".join(workflows.values())

    for label, snippet in REQUIRED_SNIPPETS.items():
        if snippet not in joined:
            fail(f"missing {label}: {snippet}")

    for snippet in BANNED_SNIPPETS:
        if snippet in joined:
            fail(f"deprecated Node 20-era action remains: {snippet}")

    print("github actions versions: Node 24-compatible action majors passed")


if __name__ == "__main__":
    main()
