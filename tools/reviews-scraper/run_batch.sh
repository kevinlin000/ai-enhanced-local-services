#!/usr/bin/env bash
# 每家 shop 單獨跑，Chrome 間歇清理，失敗自動 retry 一次
set -uo pipefail

SCRAPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRAPER_DIR/.venv/bin/python"
DB="$SCRAPER_DIR/reviews.db"

SHOPS=(
  "ChIJQ3XJ-sWrQjQRQmpEkoaT3FI|海底撈火鍋 信義微風南山店|10102"
  "ChIJUW0K4lepQjQRecSOtncaPnM|和牛涮 台北羅斯福店|10152"
  "ChIJFap94WarQjQR8xORzmAVd88|雙月食品社 森林公園店|10132"
  "ChIJDRg6PQCrQjQRF5UBQT_vCSE|老井極上燒肉 台北信義店|10107"
  "ChIJY3YUcaKrQjQRZ1OTdcQlbEo|二本松涮涮屋 本館|10144"
)

TOTAL=${#SHOPS[@]}
SUCCESS=0
FAIL=0

# Return current review count for a place_id in SQLite
db_count() {
  local place_id="$1"
  "$PYTHON" -c "
import sqlite3, sys
try:
    conn = sqlite3.connect('$DB')
    row = conn.execute(\"SELECT COUNT(*) FROM reviews WHERE place_id=(SELECT place_id FROM places WHERE place_name LIKE '%$place_id%' LIMIT 1)\").fetchone()
    print(row[0] if row else 0)
    conn.close()
except: print(0)
" 2>/dev/null || echo 0
}

# Check by shop company name in MongoDB
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

  # Kill leftover Chrome
  pkill -f "chromedriver" 2>/dev/null || true
  pkill -f "Google Chrome Helper" 2>/dev/null || true
  sleep 3

  cat > "$SCRAPER_DIR/config_single.yaml" << YAML
headless: true
sort_by: "relevance"
scrape_mode: "full"
max_reviews: 20
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

  local t0 t1
  t0=$(date +%s)
  "$PYTHON" "$SCRAPER_DIR/start.py" scrape --config "$SCRAPER_DIR/config_single.yaml" 2>&1
  t1=$(date +%s)
  echo "  elapsed: $((t1-t0))s"

  # Detect success: MongoDB must have reviews for this shop
  local cnt
  cnt=$(mongo_count "$name")
  echo "  mongo count for '$name': $cnt"
  [ "$cnt" -gt 0 ]
}

for entry in "${SHOPS[@]}"; do
  IFS='|' read -r place_id name shop_id <<< "$entry"
  idx=$((SUCCESS+FAIL+1))

  echo ""
  echo "=== [$idx/$TOTAL] $name (shop_id=$shop_id) ==="

  if run_shop "$place_id" "$name" "$shop_id"; then
    echo "  ✓ SUCCESS"
    SUCCESS=$((SUCCESS+1))
  else
    echo "  ✗ FAIL — retrying once after 10s..."
    sleep 10
    if run_shop "$place_id" "$name" "$shop_id"; then
      echo "  ✓ RETRY SUCCESS"
      SUCCESS=$((SUCCESS+1))
    else
      echo "  ✗ RETRY ALSO FAILED"
      FAIL=$((FAIL+1))
    fi
  fi

  sleep 3
done

echo ""
echo "=== 完成: $SUCCESS 成功 / $FAIL 失敗 / $TOTAL 家 ==="
