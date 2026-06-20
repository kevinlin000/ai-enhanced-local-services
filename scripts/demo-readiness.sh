#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://localhost:8088}"
WEB_URL="${WEB_URL:-http://127.0.0.1:3000}"
JAVA_HEALTH_URL="${JAVA_HEALTH_URL:-http://127.0.0.1:8081/actuator/health}"
AI_HEALTH_URL="${AI_HEALTH_URL:-http://127.0.0.1:8000/health}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-5}"
LIVE_SMOKE="${LIVE_SMOKE:-false}"
STRICT="${STRICT:-false}"
DRY_RUN="${DRY_RUN:-false}"

usage() {
  cat <<'USAGE'
Usage: scripts/demo-readiness.sh [options]

Checks demo readiness without starting or stopping long-running services.
Use this before a presentation after starting Web, Java, AI, and the
Nginx public-proxy overlay.

Options:
  --base-url URL       Nginx public proxy URL. Default: http://localhost:8088
  --live-smoke        Run scripts/smoke-nginx-public-proxy.sh after preflight.
  --strict            Fail if any live service check is down.
  --dry-run           Print planned checks without making HTTP requests.
  -h, --help          Show this help.

Environment:
  BASE_URL
  WEB_URL
  JAVA_HEALTH_URL
  AI_HEALTH_URL
  TIMEOUT_SECONDS
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-url)
      if [ "$#" -lt 2 ]; then
        printf "--base-url requires a URL\n" >&2
        usage >&2
        exit 2
      fi
      BASE_URL="$2"
      shift 2
      ;;
    --live-smoke)
      LIVE_SMOKE=true
      shift
      ;;
    --strict)
      STRICT=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf "unknown option: %s\n" "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

BASE_URL="${BASE_URL%/}"
FAILED_CHECKS=0

info() {
  printf "INFO %s\n" "$*"
}

pass() {
  printf "PASS %s\n" "$*"
}

warn() {
  printf "WARN %s\n" "$*" >&2
  FAILED_CHECKS=$((FAILED_CHECKS + 1))
}

need_file() {
  local path="$1"
  if [ -f "$ROOT_DIR/$path" ]; then
    pass "found $path"
  else
    warn "missing $path"
  fi
}

check_url() {
  local label="$1"
  local url="$2"
  local expected="${3:-}"
  local tmp
  local status
  tmp="$(mktemp)"
  status="$(curl -sS --max-time "$TIMEOUT_SECONDS" -o "$tmp" -w "%{http_code}" "$url" || true)"
  if [[ "$status" =~ ^[23][0-9][0-9]$ ]]; then
    if [ -n "$expected" ] && ! grep -Fq "$expected" "$tmp"; then
      rm -f "$tmp"
      warn "$label reachable but response did not contain '$expected'"
      return
    fi
    rm -f "$tmp"
    pass "$label reachable ($status)"
    return
  fi
  rm -f "$tmp"
  warn "$label not ready at $url (HTTP $status)"
}

print_start_commands() {
  cat <<COMMANDS

Start commands when a check is down:

  # Infra
  docker compose up -d

  # Java
  cd backend-java
  set -a; [ -f .env ] && source .env; set +a
  TAPPAY_PARTNER_KEY=\${TAPPAY_PARTNER_KEY:-test} TAPPAY_MERCHANT_CREDITCARD=\${TAPPAY_MERCHANT_CREDITCARD:-test} mvn spring-boot:run

  # AI
  cd ai-service-python
  set -a; [ -f .env ] && source .env; set +a
  uv run uvicorn app.main:app --reload --port 8000

  # Web
  cd web
  npm run dev

  # Nginx public proxy
  docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.nginx.yml --profile public-proxy up -d nginx

  # Full public proxy smoke
  scripts/smoke-nginx-public-proxy.sh --base-url $BASE_URL
COMMANDS
}

if [ "$DRY_RUN" = "true" ]; then
  cat <<DRYRUN
Demo readiness dry run
base_url=$BASE_URL
web_url=$WEB_URL
java_health_url=$JAVA_HEALTH_URL
ai_health_url=$AI_HEALTH_URL
live_smoke=$LIVE_SMOKE
strict=$STRICT

Checks:
1. Required deployment scripts and config files exist.
2. Docker Compose public-proxy overlay can be rendered with --profile public-proxy.
3. Web, Java, AI, and Nginx public proxy are reachable.
4. Optional --live-smoke runs scripts/smoke-nginx-public-proxy.sh.
DRYRUN
  exit 0
fi

cd "$ROOT_DIR"
printf "ByteBites demo readiness preflight\n"
printf "base_url=%s\n" "$BASE_URL"

need_file "deploy/nginx/bytebites.conf.template"
need_file "deploy/docker-compose.nginx.yml"
need_file "docs/deployment-nginx.md"
need_file "scripts/smoke-nginx-public-proxy.sh"
need_file "scripts/verify-portfolio.sh"

if command -v docker >/dev/null 2>&1; then
  if docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.nginx.yml --profile public-proxy config >/dev/null; then
    pass "docker compose public-proxy config"
  else
    warn "docker compose public-proxy config failed"
  fi
else
  warn "docker command not found; cannot validate compose overlay"
fi

check_url "Web" "$WEB_URL"
check_url "Java health" "$JAVA_HEALTH_URL" "UP"
check_url "AI health" "$AI_HEALTH_URL" "bytebites-ai"
check_url "Nginx public proxy" "$BASE_URL"
check_url "Nginx Java health route" "$BASE_URL/health/java" "UP"
check_url "Nginx AI health route" "$BASE_URL/health/ai" "bytebites-ai"

if [ "$LIVE_SMOKE" = "true" ]; then
  if "$ROOT_DIR/scripts/smoke-nginx-public-proxy.sh" --base-url "$BASE_URL"; then
    pass "Nginx public proxy live smoke"
  else
    warn "Nginx public proxy live smoke failed"
  fi
else
  info "skip live smoke; pass --live-smoke to run scripts/smoke-nginx-public-proxy.sh"
fi

if [ "$FAILED_CHECKS" -gt 0 ]; then
  print_start_commands
  if [ "$STRICT" = "true" ]; then
    printf "\nDemo readiness failed: %s check(s) need attention.\n" "$FAILED_CHECKS" >&2
    exit 1
  fi
  printf "\nDemo readiness has %s warning(s). Use --strict to fail on warnings.\n" "$FAILED_CHECKS" >&2
  exit 0
fi

printf "Demo readiness preflight passed.\n"
