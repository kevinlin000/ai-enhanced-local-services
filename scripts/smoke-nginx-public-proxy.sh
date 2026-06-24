#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8088}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-8}"
STREAM_TIMEOUT_SECONDS="${STREAM_TIMEOUT_SECONDS:-4}"
INCLUDE_STREAM="${INCLUDE_STREAM:-true}"
EXPECTED_LINE_COOKIE_PATH="${EXPECTED_LINE_COOKIE_PATH:-/api/java/api/auth/line}"
EXPECTED_LINE_REDIRECT_URI="${EXPECTED_LINE_REDIRECT_URI:-}"
STREAM_QUERY="${STREAM_QUERY:-daan dinner for 2}"
DRY_RUN="${DRY_RUN:-false}"

usage() {
  cat <<'USAGE'
Usage: scripts/smoke-nginx-public-proxy.sh [options]

Checks the ByteBites public Nginx proxy after Web, Java, AI, and the
Nginx compose overlay are already running.

Options:
  --base-url URL       Public proxy base URL. Default: http://localhost:8088
  --skip-stream        Skip the SSE start-frame check.
  --dry-run            Print planned checks without making HTTP requests.
  -h, --help           Show this help.

Environment:
  BASE_URL
  TIMEOUT_SECONDS
  STREAM_TIMEOUT_SECONDS
  INCLUDE_STREAM
  EXPECTED_LINE_COOKIE_PATH
  EXPECTED_LINE_REDIRECT_URI
  STREAM_QUERY
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --skip-stream)
      INCLUDE_STREAM=false
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
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

pass() {
  printf "PASS %s\n" "$*"
}

fail() {
  printf "FAIL %s\n" "$*" >&2
  exit 1
}

planned_checks() {
  cat <<CHECKS
Nginx public-proxy smoke checks
base_url=$BASE_URL

1. GET / -> 2xx/3xx
2. GET /health/java -> 200 and body contains UP
3. GET /health/ai -> 200 and body contains bytebites-ai
4. GET /api/line/webhook -> 200 and body contains bytebites-line-bot
5. GET /api/java/api/auth/line/login -> 3xx, Location present, Set-Cookie Path=$EXPECTED_LINE_COOKIE_PATH
   Optional: EXPECTED_LINE_REDIRECT_URI must appear in the LINE authorize URL.
6. POST /api/ai/agent/stream -> text/event-stream and initial agent_start frame
CHECKS
}

if [ "$DRY_RUN" = "true" ]; then
  planned_checks
  exit 0
fi

check_http() {
  local label="$1"
  local path="$2"
  local status_regex="$3"
  local expected_body="${4:-}"
  local headers="$TMP_DIR/${label//[^A-Za-z0-9_]/_}.headers"
  local body="$TMP_DIR/${label//[^A-Za-z0-9_]/_}.body"
  local status

  status="$(curl -sS --max-time "$TIMEOUT_SECONDS" -D "$headers" -o "$body" -w "%{http_code}" "$BASE_URL$path" || true)"
  if ! [[ "$status" =~ $status_regex ]]; then
    printf "Response body for %s:\n" "$label" >&2
    sed -n '1,20p' "$body" >&2 || true
    fail "$label expected HTTP $status_regex, got $status at $path"
  fi

  if [ -n "$expected_body" ] && ! grep -Fq "$expected_body" "$body"; then
    printf "Response body for %s:\n" "$label" >&2
    sed -n '1,20p' "$body" >&2 || true
    fail "$label expected body to contain: $expected_body"
  fi

  pass "$label ($status)"
}

check_line_login() {
  local headers="$TMP_DIR/line_login.headers"
  local body="$TMP_DIR/line_login.body"
  local status
  local location

  status="$(curl -sS --max-time "$TIMEOUT_SECONDS" -D "$headers" -o "$body" -w "%{http_code}" "$BASE_URL/api/java/api/auth/line/login" || true)"
  if ! [[ "$status" =~ ^30[1278]$ ]]; then
    printf "Response body for line login:\n" >&2
    sed -n '1,20p' "$body" >&2 || true
    fail "LINE login expected 3xx redirect, got $status"
  fi

  location="$(grep -i '^location:' "$headers" | sed 's/^[Ll]ocation:[[:space:]]*//' | tr -d '\r' | tail -1)"
  if [ -z "$location" ]; then
    fail "LINE login redirect did not include Location header"
  fi

  if ! grep -Eiq "set-cookie: .*Path=${EXPECTED_LINE_COOKIE_PATH}([;[:space:]]|$)" "$headers"; then
    printf "Headers for line login:\n" >&2
    sed -n '1,20p' "$headers" >&2 || true
    fail "LINE login state cookie path did not match $EXPECTED_LINE_COOKIE_PATH"
  fi

  if [ -n "$EXPECTED_LINE_REDIRECT_URI" ]; then
    if ! python3 - "$location" "$EXPECTED_LINE_REDIRECT_URI" <<'PY'
import sys
from urllib.parse import parse_qs, urlparse

location, expected = sys.argv[1], sys.argv[2]
actual = parse_qs(urlparse(location).query).get("redirect_uri", [""])[0]
if actual != expected:
    print(f"expected redirect_uri={expected}", file=sys.stderr)
    print(f"actual redirect_uri={actual}", file=sys.stderr)
    sys.exit(1)
PY
    then
      fail "LINE login redirect_uri did not match EXPECTED_LINE_REDIRECT_URI"
    fi
  fi

  pass "line login redirect ($status -> $location)"
}

check_stream_start() {
  if [ "$INCLUDE_STREAM" != "true" ]; then
    printf "SKIP AI SSE stream start check\n"
    return
  fi

  local output="$TMP_DIR/agent_stream.out"
  local error="$TMP_DIR/agent_stream.err"
  local body
  body="$(printf '{"query":"%s","session_id":"nginx-smoke"}' "$STREAM_QUERY")"

  curl -sS -i --no-buffer --max-time "$STREAM_TIMEOUT_SECONDS" \
    -H "Content-Type: application/json" \
    -X POST \
    --data "$body" \
    "$BASE_URL/api/ai/agent/stream" >"$output" 2>"$error" || true

  if ! grep -Eiq "content-type: text/event-stream" "$output"; then
    printf "Stream output:\n" >&2
    sed -n '1,30p' "$output" >&2 || true
    printf "Stream error:\n" >&2
    sed -n '1,10p' "$error" >&2 || true
    fail "AI stream did not return text/event-stream"
  fi

  if ! grep -Fq '"type": "agent_start"' "$output"; then
    printf "Stream output:\n" >&2
    sed -n '1,30p' "$output" >&2 || true
    printf "Stream error:\n" >&2
    sed -n '1,10p' "$error" >&2 || true
    fail "AI stream did not emit initial agent_start frame within ${STREAM_TIMEOUT_SECONDS}s"
  fi

  pass "AI SSE stream starts"
}

printf "Nginx public-proxy smoke: %s\n" "$BASE_URL"
check_http "web root" "/" "^[23][0-9][0-9]$"
check_http "java health" "/health/java" "^200$" "UP"
check_http "ai health" "/health/ai" "^200$" "bytebites-ai"
check_http "line webhook check" "/api/line/webhook" "^200$" "bytebites-line-bot"
check_line_login
check_stream_start
printf "Nginx public-proxy smoke passed.\n"
