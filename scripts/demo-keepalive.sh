#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC_URL="${PUBLIC_URL:-https://excursion-reabsorb-stupor.ngrok-free.dev}"
NGROK_URL="${NGROK_URL:-excursion-reabsorb-stupor.ngrok-free.dev}"
WEB_PORT="${WEB_PORT:-3000}"
JAVA_URL="${JAVA_URL:-http://127.0.0.1:8081/actuator/health}"
AI_URL="${AI_URL:-http://127.0.0.1:8000/health}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-30}"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/.demo-logs}"
START_INFRA="${START_INFRA:-false}"

mkdir -p "$LOG_DIR"

WATCHDOG_PID_FILE="$LOG_DIR/watchdog.pid"
if [ -f "$WATCHDOG_PID_FILE" ] && kill -0 "$(cat "$WATCHDOG_PID_FILE")" >/dev/null 2>&1; then
  printf "ByteBites demo keepalive is already running with PID %s\n" "$(cat "$WATCHDOG_PID_FILE")"
  exit 0
fi
echo "$$" >"$WATCHDOG_PID_FILE"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

log() {
  printf "[%s] %s\n" "$(timestamp)" "$*"
}

is_healthy() {
  curl -fsS --max-time 8 "$1" >/dev/null 2>&1
}

start_caffeinate() {
  if [ -f "$LOG_DIR/caffeinate.pid" ] && kill -0 "$(cat "$LOG_DIR/caffeinate.pid")" >/dev/null 2>&1; then
    return
  fi
  log "starting caffeinate; keep Mac awake while lid stays open"
  caffeinate -dimsu >"$LOG_DIR/caffeinate.log" 2>&1 &
  echo "$!" >"$LOG_DIR/caffeinate.pid"
}

start_infra_once() {
  if [ "$START_INFRA" != "true" ]; then
    return
  fi
  if curl -fsS --max-time 5 http://127.0.0.1:6333/ >/dev/null 2>&1; then
    return
  fi
  log "starting docker compose infra"
  (cd "$ROOT_DIR" && docker compose up -d) >>"$LOG_DIR/docker.log" 2>&1
}

restart_web() {
  log "starting web on port $WEB_PORT"
  local existing
  existing="$(lsof -tiTCP:"$WEB_PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$existing" ]; then
    log "killing stale web listener: $existing"
    kill $existing >/dev/null 2>&1 || true
    sleep 2
  fi
  (cd "$ROOT_DIR/web" && npm run dev -- --port "$WEB_PORT") >>"$LOG_DIR/web.log" 2>&1 &
  echo "$!" >"$LOG_DIR/web.pid"
  sleep 8
}

ensure_web() {
  if is_healthy "http://127.0.0.1:$WEB_PORT"; then
    return
  fi
  restart_web
}

ensure_java() {
  if is_healthy "$JAVA_URL"; then
    return
  fi
  log "starting Java backend"
  (
    cd "$ROOT_DIR/backend-java"
    set -a
    [ -f .env ] && source .env
    set +a
    env TAPPAY_PARTNER_KEY="${TAPPAY_PARTNER_KEY:-test}" \
      TAPPAY_MERCHANT_CREDITCARD="${TAPPAY_MERCHANT_CREDITCARD:-test}" \
      mvn spring-boot:run
  ) >>"$LOG_DIR/java.log" 2>&1 &
  echo "$!" >"$LOG_DIR/java.pid"
  sleep 20
}

ensure_ai() {
  if is_healthy "$AI_URL"; then
    return
  fi
  log "starting AI service"
  (
    cd "$ROOT_DIR/ai-service-python"
    set -a
    [ -f .env ] && source .env
    set +a
    uv run uvicorn app.main:app --reload --port 8000
  ) >>"$LOG_DIR/ai.log" 2>&1 &
  echo "$!" >"$LOG_DIR/ai.pid"
  sleep 10
}

restart_ngrok() {
  log "starting ngrok for $PUBLIC_URL -> localhost:$WEB_PORT"
  pkill -f "ngrok.*$NGROK_URL" >/dev/null 2>&1 || true
  sleep 2
  ngrok http --url="$NGROK_URL" "$WEB_PORT" >>"$LOG_DIR/ngrok.log" 2>&1 &
  echo "$!" >"$LOG_DIR/ngrok.pid"
  sleep 8
}

ensure_ngrok() {
  if curl -fsSI --max-time 12 "$PUBLIC_URL" >/dev/null 2>&1; then
    return
  fi
  ensure_web
  restart_ngrok
}

print_status() {
  local public_status="down"
  local web_status="down"
  local java_status="down"
  local ai_status="down"
  curl -fsSI --max-time 12 "$PUBLIC_URL" >/dev/null 2>&1 && public_status="up"
  is_healthy "http://127.0.0.1:$WEB_PORT" && web_status="up"
  is_healthy "$JAVA_URL" && java_status="up"
  is_healthy "$AI_URL" && ai_status="up"
  log "status public=$public_status web=$web_status java=$java_status ai=$ai_status"
}

log "ByteBites demo keepalive started"
log "public URL: $PUBLIC_URL"
log "logs: $LOG_DIR"
log "important: MacBook must stay open and connected to power/network"

start_caffeinate
start_infra_once

while true; do
  ensure_web
  ensure_java
  ensure_ai
  ensure_ngrok
  print_status
  sleep "$CHECK_INTERVAL_SECONDS"
done
