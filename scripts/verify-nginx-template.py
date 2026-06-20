#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "deploy" / "nginx" / "bytebites.conf.template"
COMPOSE = ROOT / "deploy" / "docker-compose.nginx.yml"
DOC = ROOT / "docs" / "deployment-nginx.md"
SMOKE = ROOT / "scripts" / "smoke-nginx-public-proxy.sh"
READINESS = ROOT / "scripts" / "demo-readiness.sh"


def fail(message: str) -> None:
    print(f"NGINX TEMPLATE CHECK FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(text: str, snippet: str, label: str) -> None:
    if snippet not in text:
        fail(f"missing {label}: {snippet}")


def main() -> None:
    try:
        template = TEMPLATE.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing template: {TEMPLATE.relative_to(ROOT)}")

    try:
        doc = DOC.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing docs: {DOC.relative_to(ROOT)}")

    try:
        compose = COMPOSE.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing compose overlay: {COMPOSE.relative_to(ROOT)}")

    try:
        smoke = SMOKE.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing smoke script: {SMOKE.relative_to(ROOT)}")

    try:
        readiness = READINESS.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing readiness script: {READINESS.relative_to(ROOT)}")

    required_template_snippets = {
        "web upstream": "upstream bytebites_web",
        "java upstream": "upstream bytebites_java",
        "ai upstream": "upstream bytebites_ai",
        "forwarded source header": "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
        "forwarded proto header": "proxy_set_header X-Forwarded-Proto $scheme;",
        "request id header": "proxy_set_header X-Request-ID $request_id;",
        "websocket/http1 proxying": "proxy_http_version 1.1;",
        "java path": "location /api/java/",
        "java prefix strip": "proxy_pass http://bytebites_java/;",
        "legacy ai smoke path": "location /api/python/",
        "current ai path": "location /api/ai/",
        "ai prefix preserve": "proxy_pass http://bytebites_ai;",
        "line webhook path": "location /api/line/",
        "line action path": "location /line/",
        "java health": "location = /health/java",
        "ai health": "location = /health/ai",
        "sse buffering disabled": "proxy_buffering off;",
    }
    for label, snippet in required_template_snippets.items():
        require(template, snippet, label)

    required_compose_snippets = {
        "nginx service": "nginx:",
        "nginx image": "image: nginx:1.27-alpine",
        "profile": "public-proxy",
        "safe local public port": "${BYTEBITES_PUBLIC_HTTP_PORT:-8088}:80",
        "server name env": 'SERVER_NAME: "${SERVER_NAME:-localhost}"',
        "web upstream env": 'WEB_UPSTREAM: "${WEB_UPSTREAM:-host.docker.internal:3000}"',
        "java upstream env": 'JAVA_UPSTREAM: "${JAVA_UPSTREAM:-host.docker.internal:8081}"',
        "ai upstream env": 'AI_UPSTREAM: "${AI_UPSTREAM:-host.docker.internal:8000}"',
        "template mount": "./nginx/bytebites.conf.template:/etc/nginx/templates/bytebites.conf.template:ro",
        "host gateway": "host.docker.internal:host-gateway",
    }
    for label, snippet in required_compose_snippets.items():
        require(compose, snippet, label)

    required_smoke_snippets = {
        "base url": 'BASE_URL="${BASE_URL:-http://localhost:8088}"',
        "java health": 'check_http "java health" "/health/java" "^200$" "UP"',
        "ai health": 'check_http "ai health" "/health/ai" "^200$" "bytebites-ai"',
        "line webhook": 'check_http "line webhook check" "/api/line/webhook" "^200$" "bytebites-line-bot"',
        "line login route": "$BASE_URL/api/java/api/auth/line/login",
        "oauth cookie path": 'EXPECTED_LINE_COOKIE_PATH="${EXPECTED_LINE_COOKIE_PATH:-/api/java/api/auth/line}"',
        "sse route": "$BASE_URL/api/ai/agent/stream",
        "sse frame check": '"type": "agent_start"',
        "dry run": "--dry-run",
    }
    for label, snippet in required_smoke_snippets.items():
        require(smoke, snippet, label)

    required_readiness_snippets = {
        "base url": 'BASE_URL="${BASE_URL:-http://localhost:8088}"',
        "web url": 'WEB_URL="${WEB_URL:-http://127.0.0.1:3000}"',
        "java health": 'JAVA_HEALTH_URL="${JAVA_HEALTH_URL:-http://127.0.0.1:8081/actuator/health}"',
        "ai health": 'AI_HEALTH_URL="${AI_HEALTH_URL:-http://127.0.0.1:8000/health}"',
        "compose profile config": "docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.nginx.yml --profile public-proxy config",
        "public proxy health": 'check_url "Nginx Java health route" "$BASE_URL/health/java" "UP"',
        "live smoke option": "--live-smoke",
        "smoke invocation": 'scripts/smoke-nginx-public-proxy.sh --base-url $BASE_URL',
        "strict option": "--strict",
        "dry run": "--dry-run",
    }
    for label, snippet in required_readiness_snippets.items():
        require(readiness, snippet, label)

    for forbidden in ("ngrok-free.app", "ngrok-free.dev", "ngrok.io"):
        if forbidden in template:
            fail(f"template must not hard-code ngrok host: {forbidden}")

    required_doc_snippets = {
        "ngrok/nginx boundary": "ngrok | Local, temporary demo tunnels",
        "login callback": "LINE_REDIRECT_URI=https://<domain>/api/java/api/auth/line/callback",
        "oauth cookie path": "LINE_OAUTH_COOKIE_PATH=/api/java/api/auth/line",
        "line webhook": "https://<domain>/api/line/webhook",
        "trusted proxy": "REFUND_WEBHOOK_TRUSTED_PROXIES=127.0.0.1/32",
        "ai public url": "LINE_PUBLIC_WEB_URL=https://<domain>",
        "compose overlay command": "-f deploy/docker-compose.nginx.yml",
        "compose profile": "--profile public-proxy",
        "local compose port": "http://localhost:8088/health/java",
        "smoke script": "scripts/smoke-nginx-public-proxy.sh",
        "readiness script": "scripts/demo-readiness.sh",
    }
    for label, snippet in required_doc_snippets.items():
        require(doc, snippet, label)

    subprocess.run(["bash", "-n", str(SMOKE)], check=True)
    subprocess.run(["bash", "-n", str(READINESS)], check=True)
    env = {**os.environ, "DRY_RUN": "true"}
    subprocess.run(["bash", str(SMOKE)], check=True, env=env, stdout=subprocess.DEVNULL)
    subprocess.run(["bash", str(READINESS)], check=True, env=env, stdout=subprocess.DEVNULL)

    print("nginx template: deployment route contract passed")


if __name__ == "__main__":
    main()
