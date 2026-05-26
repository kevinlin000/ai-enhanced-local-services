# ByteBites Reviews Scraper

Google Maps 評論補強工具——繞過 Google Places API 5 則硬上限。

基於 [georgekhananaev/google-reviews-scraper-pro](https://github.com/georgekhananaev/google-reviews-scraper-pro)（MIT）。

## 用途

- 學術與個人作品集資料補強（非商業、非公開分發）
- 一次性批次跑；不持續輪詢 Google Maps
- 取得的評論寫入 SQLite + MongoDB，供 ETL pipeline 讀取

## 快速啟動

```bash
# 0. 啟動 MongoDB（macOS，背景執行）
~/mongodb/bin/mongod --dbpath ~/mongodb/data --logpath /tmp/mongod.log &

# 1. 進目錄、啟虛擬環境
cd tools/reviews-scraper
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 2. 編輯 config.yaml（填入 businesses + place_id）
cp config.sample.yaml config.yaml
# 在 businesses: 區塊填入 Google Maps URL

# 3a. 單家跑
python start.py scrape --config config.yaml

# 3b. 批次跑（含 retry + MongoDB count 偵測）
bash run_batch.sh
```

## Output

| 位置 | 說明 |
|------|------|
| `reviews.db` | SQLite primary（`review_text` 欄 JSON-encoded） |
| `google_reviews.json` | 最後一家的 JSON snapshot（被 .gitignore 排除） |
| `mongodb://localhost:27017/bytebites_reviews.google_reviews` | 跨家匯總 |

## 已驗證數據

- 5 家 × 20 則 = 100 reviews / 380 秒
- `description` 欄格式：`{"zh": "...", "en": "..."}` dict
- 語言分佈：zh 67%、en 8%、純評分（無文字）24%

## 取文字方法

```python
import json
text = json.loads(row["review_text"])  # {'zh': '...'}
body = text.get("zh") or text.get("en") or ""
```

## 注意事項

- `config.yaml`、`reviews.db`、`.venv/`、`*.json` 全在 `.gitignore`
- 第一家 Chrome 初始化約 50-120 秒（後續各家 ~50 秒）
- pymongo 4.x fix：`modules/data_storage.py` 已修正 TLS 誤觸發 bug
