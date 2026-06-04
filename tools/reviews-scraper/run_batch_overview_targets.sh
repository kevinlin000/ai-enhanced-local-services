#!/usr/bin/env bash
set -uo pipefail

SCRAPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRAPER_DIR/.venv/bin/python"
SHOPS_FILE="${SHOPS_FILE:-$SCRAPER_DIR/shops_overview_targets.txt}"
PROGRESS_FILE="${CRAWL_PROGRESS_FILE:-/tmp/crawl-overview-targets.progress}"

export PYTHONUNBUFFERED=1
export NO_COLOR=1
export TERM=dumb

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

log() {
  printf '[%s] %s\n' "$(timestamp)" "$*"
}

write_progress() {
  cat > "$PROGRESS_FILE" <<EOF
pid=$$
updated_at=$(timestamp)
success=$SUCCESS
fail=$FAIL
total=$TOTAL
current_idx=${CURRENT_IDX:-0}
current_shop=${CURRENT_SHOP:-}
current_shop_id=${CURRENT_SHOP_ID:-}
EOF
}

on_exit() {
  local exit_code=$?
  log "batch exit code=$exit_code success=$SUCCESS fail=$FAIL total=$TOTAL current_idx=${CURRENT_IDX:-0} current_shop=${CURRENT_SHOP:-}"
  write_progress
}

trap on_exit EXIT

if [[ ! -f "$SHOPS_FILE" ]]; then
  echo "missing shops file: $SHOPS_FILE"
  exit 1
fi

SHOPS=()
while IFS= read -r line || [[ -n "$line" ]]; do
  SHOPS+=("$line")
done < "$SHOPS_FILE"

TOTAL=${#SHOPS[@]}
SUCCESS=0
FAIL=0
CURRENT_IDX=0
CURRENT_SHOP=""
CURRENT_SHOP_ID=""
MAX_ATTEMPTS=${MAX_ATTEMPTS:-3}
write_progress

sqlite_overview_count() {
  local shop_id="$1"
  "$PYTHON" -c "
import json
import sqlite3
import sys

db_path = sys.argv[1]
target_shop_id = str(sys.argv[2])

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT overview_metadata FROM places WHERE overview_metadata IS NOT NULL')
    count = 0
    for (raw,) in cur.fetchall():
        try:
            data = json.loads(raw) if isinstance(raw, str) else {}
        except Exception:
            continue
        if str(data.get('shop_id') or '') == target_shop_id:
            count += 1
    conn.close()
    print(count)
except Exception:
    print(0)
" "$SCRAPER_DIR/reviews.db" "$shop_id" 2>/dev/null || echo 0
}

build_search_url() {
  local name="$1" address="$2"
  "$PYTHON" - "$name" "$address" <<'PY'
import re
import sys
import urllib.parse

name = sys.argv[1]
address = sys.argv[2]

def clean_name(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.split(r"[｜|]", text, maxsplit=1)[0].strip()
    text = re.split(
        r"\s+(?:台北|臺北|士林區|大安區|信義區|中山區|餐廳|餐酒館|酒吧|活動|生日|企業|推薦|包場)",
        text,
        maxsplit=1,
    )[0].strip()
    text = text.strip(" -—－｜|")
    return text or (value or "").strip()

def area_hint(value: str) -> str:
    match = re.search(r"(?:台北市|臺北市)([^市縣]{1,4}區)", value or "")
    if match:
        return f"台北市 {match.group(1)}"
    if "台北" in (value or "") or "臺北" in (value or ""):
        return "台北市"
    return ""

query_text = " ".join(part for part in (clean_name(name), area_hint(address)) if part).strip()
query = urllib.parse.quote(query_text)
print(f"https://www.google.com/maps/search/{query}")
PY
}

run_shop() {
  local shop_id="$1" name="$2" address="$3"
  local url
  local rc=0

  url="$(build_search_url "$name" "$address")"

  pkill -f "chromedriver" 2>/dev/null || true
  pkill -f "Google Chrome Helper" 2>/dev/null || true
  sleep 3

  cat > "$SCRAPER_DIR/config_single.yaml" <<YAML
headless: true
sort_by: "relevance"
overview_only: true
scrape_mode: "update"
max_reviews: 0
max_scroll_attempts: 1
stop_threshold: 0
scroll_idle_limit: 1
db_path: "reviews.db"
convert_dates: true
download_images: false
backup_to_json: false
use_mongodb: false
businesses:
  - url: "$url"
    custom_params:
      company: "$name"
      shop_id: $shop_id
YAML

  local t0 t1 cnt
  t0=$(date +%s)
  log "launch scraper shop_id=$shop_id name=$name"
  "$PYTHON" -u "$SCRAPER_DIR/start.py" scrape --config "$SCRAPER_DIR/config_single.yaml" 2>&1
  rc=$?
  t1=$(date +%s)
  log "scraper exit rc=$rc elapsed=$((t1-t0))s shop_id=$shop_id"

  cnt=$(sqlite_overview_count "$shop_id")
  log "sqlite overview count shop_id=$shop_id count=$cnt"
  [ "$rc" -eq 0 ] && [ "$cnt" -gt 0 ]
}

for entry in "${SHOPS[@]}"; do
  IFS='|' read -r shop_id name address <<< "$entry"
  idx=$((SUCCESS+FAIL+1))
  CURRENT_IDX=$idx
  CURRENT_SHOP="$name"
  CURRENT_SHOP_ID="$shop_id"
  write_progress
  echo ""
  log "=== [$idx/$TOTAL] $name (shop_id=$shop_id) ==="

  attempt=1
  while true; do
    if run_shop "$shop_id" "$name" "$address"; then
      if [ "$attempt" -eq 1 ]; then
        log "shop success shop_id=$shop_id"
      else
        log "shop success_after_retry shop_id=$shop_id attempt=$attempt"
      fi
      SUCCESS=$((SUCCESS+1))
      break
    fi

    if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
      log "shop failed_all_attempts shop_id=$shop_id attempts=$attempt"
      FAIL=$((FAIL+1))
      break
    fi

    backoff=$((attempt * 10))
    log "shop attempt_failed shop_id=$shop_id attempt=$attempt retry_after=${backoff}s"
    sleep "$backoff"
    attempt=$((attempt+1))
  done

  write_progress
  sleep 3
done

echo ""
log "=== 完成: $SUCCESS 成功 / $FAIL 失敗 / $TOTAL 家 ==="
