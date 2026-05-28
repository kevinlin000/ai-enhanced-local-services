#!/usr/bin/env bash
set -uo pipefail

SCRAPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRAPER_DIR/.venv/bin/python"
SHOPS_FILE="$SCRAPER_DIR/shops_next30.txt"
PROGRESS_FILE="${CRAWL_PROGRESS_FILE:-/tmp/crawl-next30.progress}"

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
MAX_REVIEWS=${MAX_REVIEWS:-20}
write_progress

mongo_count() {
  local company="$1"
  "$PYTHON" -c "
from pymongo import MongoClient
try:
    c = MongoClient('mongodb://localhost:27017', connectTimeoutMS=3000)
    n = c['bytebites_reviews']['google_reviews'].count_documents({'company': '$company'})
    print(n); c.close()
except: print(0)
" 2>/dev/null || echo 0
}

run_shop() {
  local place_id="$1" name="$2" shop_id="$3"
  local url="https://www.google.com/maps/place/?q=place_id:${place_id}"
  local rc=0

  pkill -f "chromedriver" 2>/dev/null || true
  pkill -f "Google Chrome Helper" 2>/dev/null || true
  sleep 3

  cat > "$SCRAPER_DIR/config_single.yaml" << YAML
headless: true
sort_by: "relevance"
scrape_mode: "full"
max_reviews: ${MAX_REVIEWS}
max_scroll_attempts: 30
stop_threshold: 3
scroll_idle_limit: 10
db_path: "reviews.db"
convert_dates: true
download_images: false
backup_to_json: false
use_mongodb: true
mongodb:
  uri: "mongodb://localhost:27017"
  database: "bytebites_reviews"
  collection: "google_reviews"
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

  cnt=$(mongo_count "$name")
  log "mongo count company='$name' count=$cnt"
  [ "$rc" -eq 0 ] && [ "$cnt" -gt 0 ]
}

for entry in "${SHOPS[@]}"; do
  IFS='|' read -r place_id name shop_id <<< "$entry"
  idx=$((SUCCESS+FAIL+1))
  CURRENT_IDX=$idx
  CURRENT_SHOP="$name"
  CURRENT_SHOP_ID="$shop_id"
  write_progress
  echo ""
  log "=== [$idx/$TOTAL] $name (shop_id=$shop_id) ==="

  attempt=1
  while true; do
    if run_shop "$place_id" "$name" "$shop_id"; then
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
