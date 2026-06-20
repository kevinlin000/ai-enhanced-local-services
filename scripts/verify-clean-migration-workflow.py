#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "clean-mysql-migration-smoke.yml"
SMOKE = ROOT / "scripts" / "smoke-clean-mysql-migrations.sh"


def fail(message: str) -> None:
    print(f"CLEAN MIGRATION WORKFLOW CHECK FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(text: str, snippet: str, label: str) -> None:
    if snippet not in text:
        fail(f"missing {label}: {snippet}")


def main() -> None:
    try:
        workflow = WORKFLOW.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing workflow: {WORKFLOW.relative_to(ROOT)}")

    try:
        smoke = SMOKE.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing smoke script: {SMOKE.relative_to(ROOT)}")

    required_workflow_snippets = {
        "manual trigger": "workflow_dispatch:",
        "timeout input": "timeout_seconds:",
        "ubuntu runner": "runs-on: ubuntu-latest",
        "job timeout": "timeout-minutes: 15",
        "java 17": 'java-version: "17"',
        "maven cache": "cache: maven",
        "redis service": "image: redis:7-alpine",
        "rabbitmq service": "image: rabbitmq:3.13-management-alpine",
        "rabbitmq admin user": "RABBITMQ_DEFAULT_USER: admin",
        "rabbitmq admin password": "RABBITMQ_DEFAULT_PASS: admin",
        "mysql container name": "--name bytebites-ci-mysql",
        "mysql root password": "-e MYSQL_ROOT_PASSWORD=password",
        "mysql health": "mysqladmin ping -uroot -ppassword --silent",
        "mysql image": "mysql:8.0",
        "wait mysql": "docker inspect -f '{{.State.Health.Status}}' bytebites-ci-mysql",
        "smoke invocation": "scripts/smoke-clean-mysql-migrations.sh",
        "mysql container option": "--mysql-container bytebites-ci-mysql",
        "timeout input usage": "${{ github.event.inputs.timeout_seconds || '180' }}",
        "java smoke port": "--java-port 18081",
        "tappay partner key": "TAPPAY_PARTNER_KEY: test",
        "tappay merchant": "TAPPAY_MERCHANT_CREDITCARD: test",
    }
    for label, snippet in required_workflow_snippets.items():
        require(workflow, snippet, label)

    required_smoke_snippets = {
        "mysql container option": "--mysql-container",
        "database option": "--database",
        "java port option": "--java-port",
        "timeout option": "--timeout",
        "keep db option": "--keep-database",
        "dry run option": "--dry-run",
        "temp db prefix": "bytebites_migration_smoke_",
        "health wait": "/actuator/health",
        "cleanup drop": "DROP DATABASE IF EXISTS",
        "tcp mysql client": "mysql -h127.0.0.1 -P3306",
    }
    for label, snippet in required_smoke_snippets.items():
        require(smoke, snippet, label)

    subprocess.run(["bash", "-n", str(SMOKE)], check=True)
    subprocess.run([str(SMOKE), "--dry-run"], check=True, stdout=subprocess.DEVNULL)

    print("clean migration workflow: manual CI smoke contract passed")


if __name__ == "__main__":
    main()
