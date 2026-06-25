# Case Study 06: 資料爬蟲與覆蓋率 — 從 seed 資料到 599 家可用店

**TL;DR** ByteBites 一開始只有少量 seed 店家，推薦看起來像原型。後來我把資料工作當成產品核心：Google Places / Maps crawler、review sync、media manifest、coverage audit、query normalization、taxonomy backfill。資料恢復後保留 599 家 active Taipei shops，並把 legacy seed 從 MySQL/Qdrant 推薦路徑移除。

**Tech:** Google Places / Google Maps / MongoDB / MySQL / Qdrant / Python ETL / Playwright-style crawler hardening  
**Repo:** `etl-pipeline/`, `tools/`, `docs/data-coverage-report.md`, `docs/taxonomy-audit.md`

## 1. 起點：seed 資料看起來能跑，但不能支撐 AI

早期 25 家 seed 店可以讓 UI 有內容，但 AI 推薦很快會出問題：

- query 範圍稍微變大，結果開始重複。
- 使用者問「中山」「大安」「商務」「台菜」時，資料不足會讓模型硬湊答案。
- seed shop 沒有完整照片、評論、ABSA、分類與 Qdrant payload。
- legacy seed 混在真實資料中，會污染推薦品質。

這不是 UI 問題，也不是模型問題。AI 推薦的上限先被資料覆蓋率決定。

## 2. 決策：資料 pipeline 要可審計，不只是能抓

我沒有只寫一支 crawler 然後把資料塞進 DB。整個資料工作被拆成幾層：

| Layer | Purpose |
|---|---|
| Places crawler | 取得候選店家與基本欄位 |
| Maps detail crawler | 補照片、評論、地址、營業資訊 |
| Mongo review sync | 保存評論與中間資料，避免每次重抓 |
| MySQL loader | 供 Java API 與 Web 查詢 |
| Qdrant loader | 供 AI semantic search |
| Coverage audit | 量化資料缺口，決定下一批補哪裡 |
| Manual taxonomy audit | 修分類錯誤，避免 AI filter 被髒資料拖垮 |

這讓資料不只是「抓到了」，而是能回答：「哪些店缺照片？哪些店缺價位？哪些店沒有 MRT？哪些分類可信？」

## 3. Crawler hardening：Google Maps 不是穩定 API

Google Maps 頁面不是為批次爬蟲設計的，實作過程遇到很多不穩定點：

- review tab 有時找不到或延遲載入。
- 店名有 SEO suffix，直接搜尋會導到錯店。
- query 裡的括號、標點、分店資訊會降低命中率。
- 部分店只能看到 limited-view reviews。
- SQLite-to-Mongo sync 曾出現 review 對不上 shop id 的問題。
- detail coverage gap 需要 retry queue，而不是人工重跑全部。

因此 commit history 裡有一長串不是「新增資料」，而是「讓抓資料變可靠」：

- `fix(scraper): harden Google Maps review navigation`
- `fix(scraper): harden Google Maps review tab detection`
- `fix(scraper): sanitize Google Maps search queries`
- `fix(scraper): clean Google Maps detail queries`
- `fix(scraper): verify review batches by shop id`
- `fix(scraper): repair SQLite-to-Mongo review sync`
- `fix(scraper): generate place-id detail retry queues`

這些 commit 不華麗，但它們是資料產品能成立的原因。

## 4. Coverage audit：用數字決定下一步

抓完資料後，我產出 coverage report，而不是憑感覺說「資料差不多了」。

當時報告記錄：

| Area | Coverage |
|---|---:|
| Cover image/media | 100.0% |
| District | 100.0% |
| AI summary | 100.0% |
| ABSA | 99.8% |
| Mongo reviews | 99.8% |
| Media manifest photos | 100.0% |
| Media manifest overview | 95.3% |
| Price signal | 86.3% |
| MRT station | 29.7% |

這份表直接影響產品決策：

- MRT coverage 不足，所以 Web 不應只靠捷運作為主入口。
- price signal 有缺口，所以卡片要能 graceful fallback。
- ABSA coverage 高，可以放心把評論分析放進 detail page。
- media coverage 夠高，首頁和推薦卡才有視覺品質。

## 5. Legacy seed cleanup：不讓 seed 資料污染真實推薦

當真實資料達到可用規模後，最早的 25 家 seed shop 反而變成風險。它們存在於：

- MySQL active shops
- Qdrant payload
- AI hard-coded supplement
- Web card fallback
- user favorite / availability watch 關聯

我沒有直接硬刪 DB row，因為舊 booking 可能仍有 foreign key 參照。最後策略是：

- MySQL row 保留，但設為 inactive。
- source 標成 `legacy_seed_removed`。
- 清掉 badge/tag/AI metadata/ABSA/favorites/watch。
- Qdrant 刪除 `shop_id 10001-10025`。
- AI layer 加 legacy seed guard。
- 回歸測試鎖住 `10009`, `10014` 不會再回推薦。

這是典型資料治理 trade-off：保留歷史一致性，但從產品推薦面移除。

## 6. 我學到的事

**AI 產品不是 prompt 寫好就會好。** 推薦品質首先取決於資料覆蓋率、分類正確性與 payload 一致性。

**Crawler 的難點不是第一筆資料。** 第一筆通常很快；難的是第 400 筆、第 500 筆、第 600 筆仍然可驗證。

**coverage report 是產品工具。** 它不只是工程報表，而是決定 UI fallback、推薦策略與簡報可信度的依據。

**清資料比加資料難。** legacy seed 移除牽涉 MySQL、Qdrant、AI fallback、測試與外鍵策略，不能只 `DELETE FROM shop`。

## English Version

# Case Study 06: Data Crawling and Coverage — From Seed Data to 599 Usable Shops

ByteBites started with a small seed dataset. That was enough for a UI prototype, but not enough for trustworthy AI recommendations. The real work was building a data pipeline: Places crawling, Maps detail crawling, review extraction, Mongo sync, MySQL loading, Qdrant payload sync, media manifests, coverage reports, and manual taxonomy audits.

The crawler had to be hardened against real Google Maps behavior: unstable review tabs, noisy shop names, SEO suffixes, limited review views, detail retry queues, and shop-id mismatches between intermediate storage and final payloads.

The key shift was treating data coverage as a measurable product surface. A report showed 100% media coverage, 99.8% ABSA/review coverage, 86.3% price signal coverage, and only 29.7% MRT coverage. Those numbers directly informed UI and recommendation decisions.

Finally, once real data was strong enough, the original legacy seed shops were removed from the recommendation path without breaking historical references. MySQL rows were kept inactive, Qdrant vectors were deleted, AI fallbacks were guarded, and regression tests ensured the removed shops no longer appeared.

The lesson: a serious AI product is a data product first.
