# 餐廳資料恢復紀錄（2026-06-24）

> 給之後接手的人（含 Codex）：先讀這份，別再跑壞掉的腳本。

## 症狀

餐廳頁的「餐廳介紹、評論、餐廳特色」消失或停在很舊/很空的版本。

## 根因（Codex 造成）

`etl-pipeline/scripts/restore_active_600_shops.py`（已停用）有兩個嚴重 bug：

1. **編號錯位（張冠李戴）**：它把 `shop-media.json` 的 manifest 編號和 extracted 店家
   **按位置（position）** 配對，而非按身分（place_id）。結果 DB 的 `shop_id` 跟所有
   檔案資料（manifest 照片、extracted 評論/metadata、Mongo 評論——這些全用「原始編號」）
   錯開，前端用 DB 新編號去查 → ~480 家的照片/評論/特色掛到別家店上。
2. **灌淺層佔位**：`ai_summary` 全被蓋成「…適合用於推薦、訂位與候位通知 demo」，
   `signature_dishes=[]`，且完全沒有重算 ABSA（`tb_shop_absa` 因 `ON DELETE CASCADE`
   隨 `tb_shop` 重灌被清空）。
3. **灌錯 catalog**：塞進 71 家新北店 + 7 家雜項（月子餐/電競館），擠掉 82 家正牌台北店。

> 註：使用者刪掉的數 GB 舊備份與本事故無關。Mongo 原始評論（`~/mongodb/data`）完好。

## 資料來源關係（重要）

| 存儲 | 鍵 | 內容 |
|---|---|---|
| MySQL `hmdp` | DB shop_id（被 Codex 重編） | 店家主檔、AI metadata、ABSA |
| `web/data/shop-media.json` | **原始編號** | 照片、overview、評論快照 |
| `etl-pipeline/data/raw/places_extracted_*.json` | place_id / 名稱 | AI metadata 來源、地址、座標 |
| Mongo `bytebites_reviews.google_reviews` | **原始編號** | 12,616 則原始評論（599 台北店） |
| `tools/reviews-scraper/reviews.db` | 0x place_id | scraper 主存儲；review_id 與 Mongo 共通 |

原始編號 = Mongo shop_id = manifest key = 抓評論當時的 DB 編號。

## 修法（Strategy A：把 DB 編號改回原始編號）

依執行順序：

1. **備份**：`backups/20260624_*/hmdp_full.sql`、`hmdp_pre_rebuild.sql`、`google_reviews.json.gz`。
2. **重建 catalog**：`etl-pipeline/scripts/rebuild_catalog_correct_ids.py`
   —— 每家店 id 設回原始編號（身分用 Mongo company → extracted 名稱對應）。
   599 台北店，DB id ↔ Mongo ↔ manifest **599/599 對齊**。78 新北/雜項淘汰，82 台北店復原。
   FK demo 資料（券/商家/訂位）用 `mongo_shop_id_map.json.applied` remap，孤兒列刪除。
3. **重載 metadata**：`etl-pipeline/scripts/restore_ai_metadata_from_extracted.py`
   —— 以 place_id join，寫真實 `ai_summary`/`signature_dishes`/`atmosphere_tags`，
   `model_version='extracted-restore-v1'`。
4. **重算 ABSA**：`ai-service-python/scripts/absa_backfill_missing_from_mongo.py`
   —— 對齊後 db_id = mongo_id，直連查評論。`gemini-3.1-flash-lite`，成本 $0.42。
5. **補捷運站**：`etl-pipeline/scripts/backfill_mrt_from_geo.py --apply`
   —— 重建時 `mrt_station` 被設 NULL，首頁「精選餐廳 / 捷運熱門」兩區靠它，會空掉。
   依座標補回（177 家在 8 站 1km 內）。**重建 catalog 後務必補跑這支。**

## 最終狀態

- 599 台北店，全部 id 對齊；照片/評論/介紹/特色端到端正確。
- `tb_shop_ai_metadata`: 599（真實，非佔位）
- `tb_shop_absa`: 586。未涵蓋 13 家＝12 家未過防幻覺品質門檻 + 1 家（10130 MAJI MAJI）評論<5。

## 已知限制 / 待辦

- **45 家評論 <20 則**：Google 反爬「limited-view」造成（非 Google 沒有；一蘭別館 Google 有 7,605 則只抓到 10）。
  scraper 已記錄 `known_limited_view_review_shops.txt`（41 家）+ rescue config（10119、10156）。
  之後可針對「非 limited-view 的熱門低評論店」用 reviews-scraper 小批補抓，再 `--force` 重算 ABSA。
- 補抓後重算單店 ABSA：`absa_backfill_missing_from_mongo.py --shop-id <id> --force`。

## 不要再做

- ❌ 不要跑 `restore_active_600_shops.py`（已加 `SystemExit` 硬擋）。
- ❌ 不要按 extracted 的 `shop_id` 欄位 join（那欄是舊編號，會張冠李戴）；用 place_id 或名稱。

---

## 接手起手清單（下一位請先照這跑）

### 0. 現況快照（2026-06-24 重建後）
- `tb_shop` is_active=1：**599**（不是 600；已無 inactive legacy）
- `tb_shop_ai_metadata`：599（真實，`model_version='extracted-restore-v1'`）
- `tb_shop_absa`：586（其餘 12 未過品質門檻 + 1 家評論<5）
- Qdrant `shops`/`bytebites_shops`：599 點，已對齊，已刪過時點 10701
- merchant demo user：`1001`，擁 14 家有效店

### 1. 先驗「599」一致（不要信任何單一數字）
四者一致才算數：
- DB：`SELECT COUNT(*) FROM tb_shop WHERE is_active=1`
- API：`curl localhost:8081/api/shop/count`
- 前台搜尋 total
- 抽 3 家詳情頁渲染正確（介紹/照片/評論/特色）

### 2. 清快取（外科式，**禁止 FLUSHALL**）
本次重建在前一次清快取之後 → Redis/Caffeine 可能又髒。
- 刪 `cache:shop:*`（+ 任何 shop list/search 相關 key）
- 重啟 Java（清 Caffeine）
- 不動其他業務 key
- 清完重驗 API + ngrok

### 3. 破壞性 DB 操作鐵規（restore / remap / seed / migration）
**這次災難就是跳過這流程造成的，必照：**
1. `mysqldump` 備份 →（`backups/` 已 gitignore）
2. dry-run 印出 affected rows
3. 只改目標表 / 目標 id
4. 改後 count + sample verify
5. 留 recovery note

### 4. Demo 收尾範圍（錄影/面試前）
- ✅ authenticated smoke（訂位→TapPay 沙箱→我的訂位→商家後台→異常/退款）
- ✅ 最小 demo seed（我的訂位/商家/異常/押金 各 1-2 筆，綁**有效** shop_id）
- ❌ 不重構大模組（押金/退款）、不清死碼（Blog/Follow）、不大改 DB
