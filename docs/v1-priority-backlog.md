# V1 Priority Backlog

> 依 2026-05-26 repo 現況重排。目標不是再開新戰線，而是先把 v1 主線做成「可 demo、可面試、可自圓其說」。

---

## 判斷原則

1. 先做 **Inline-like 主流程閉環**，再做包裝。
2. 先做 **資料語意密度**，再做資料量擴張。
3. 先做 **業務語意一致**，再做部署與影片。
4. `Phase 2` 先不開發，只保留設計研究。

---

## Claude task 重排

### P0 — 現在就該做

#### 1. Voucher → HotSeatVoucher 業務語意（rename + 故事）

- **結論**：要做，而且應該先做。
- **原因**：
  - 現在 Java / Python / 前端混用 `voucher`、`seckill`、`hot-seat`，對外敘事不一致。
  - 對使用者與面試官來說，「Hot Seat / 熱門時段搶位券」比「優惠券秒殺」更貼近 Inline-like 餐廳場景。
  - 這是後續文件、demo、影片、AWS 展示的語意底座。
- **現況證據**：
  - Java 秒殺入口仍是 `/voucher-order/seckill/{id}`。
  - Python tool 已開始用 `hot_seat_vouchers` 語意，但 message 仍寫 voucher。
  - 店家頁與 Agent 已有訂位 / 熱座概念，尚未完全統一。
- **完成定義**：
  - 使用者可見文案統一為 `Hot Seat` / `熱門時段搶位`。
  - README / roadmap / API 敘事一致。
  - 程式內部可暫保留舊欄位與資料表名，先做 façade rename，不急著大搬 schema。

#### 2. ETL 補 20 則評論（提升 price_per_person 抽取率）

- **結論**：要做，但重點不是「20 則」本身，是 **把抽取結果吃進檢索與展示**。
- **原因**：
  - 現在 extractor 已能抽 `ai_summary`、`signature_dishes`、`atmosphere_tags`、`booking_difficulty`、`price_per_person`。
  - 但 ingest 進 Qdrant 時只吃 `name/area/address/district/mrtStation`，浪費評論語意。
  - 若不補這段，103 家再加到 300 家，AI 搜尋品質也不會明顯變好。
- **建議拆成兩步**：
  - A. 補 20 則評論，提高抽取成功率與 metadata 完整度。
  - B. 讓 metadata 進 DB / Qdrant / rerank / detail page。
- **完成定義**：
  - `price_per_person`、`signature_dishes`、`atmosphere_tags` 的非空率提升。
  - AI 搜尋對「約會 / 商務 / 聚餐 / 高價位 / 安靜」類 query 有明顯改善。

#### 3. SSE streaming（chat 真打字機）

- **結論**：可做，排 P0 後段。
- **原因**：
  - 這直接改善 AI 體感，且與你現有 Agent 頁面高度相關。
  - 對 demo 很有感，比 AWS 部署更能讓使用者覺得「像產品」。
  - 但前提是回答品質先過關，否則只是把普通回答變成打字動畫。
- **完成定義**：
  - 前端 `AI Chat` 改為串流顯示。
  - 中途錯誤、取消、session 延續要可處理。
  - 不破壞現有 tool-calling 與 Redis session 流程。

### P1 — 主線穩後再做

#### 4. Caffeine 1000 → 30（OOM 故事、有 GC 圖佐證）

- **結論**：先不要急著改數字，先補證據。
- **原因**：
  - `maximumSize(1000)` 目前存在，但 repo 內我還沒看到 GC / heap 證據鏈。
  - 如果你沒有圖、壓測條件、命中率與 heap 對照，這故事會很虛。
  - 30 這個值太小，若無 workload 根據，面試會被追問為何不是 50 / 100 / 300。
- **正確做法**：
  - 先量測：命中率、GC、heap、shop detail 熱點數。
  - 再決定是 `30`、`100`，還是不同 profile 用不同設定。
- **完成定義**：
  - 有圖、有數字、有決策理由。
  - README / 面試稿可講清楚「為何縮 cache size」。

#### 5. 面試話術 doc

- **結論**：重要，但是收尾項，不是現在最優先。
- **原因**：
  - 話術應建立在系統語意統一、主流程穩、資料閉環完成之後。
  - 現在先寫，之後還會重寫。
- **完成定義**：
  - 每個主題都能回答：為何這樣設計、替代方案、取捨、失敗案例。

### P2 — 可以延後

#### 6. I2 demo 影片

- **結論**：延後。
- **原因**：
  - 現在錄，之後 HotSeat 故事、SSE、資料展示一變，影片就報廢。

#### 7. I3 AWS 部署

- **結論**：延後。
- **原因**：
  - 目前不是交付瓶頸。
  - 若主站體驗與資料語意還沒收斂，上雲只是把未完成品搬上去。

---

## 我另外加的 3 個必要 task

### A. AI metadata → 檢索閉環

- **為何要加**：
  - 這是現在 repo 最大技術缺口。
  - 你已有評論抽取，但未餵回向量檢索主鏈路。
- **要做什麼**：
  - 更新 ingest 文本，納入 `ai_summary`、`signature_dishes`、`atmosphere_tags`、`price_per_person`、`booking_difficulty`。
  - 加 metadata-aware rerank。
  - 讓 `/shops` AI 模式排序能吃這些訊號。

### B. 店家 detail 頁升級為「決策頁」

- **為何要加**：
  - Inline-like 核心不是只有能搜尋，而是 detail 頁要讓人「敢下決定」。
- **要做什麼**：
  - 強化價位、氛圍、適合誰、預約難度、熱門時段、招牌菜的可讀性。
  - 補「為什麼推薦這家」與「附近替代選項」。

### C. `CLAUDE.md` / `roadmap.md` 校正

- **為何要加**：
  - 現有文件落後 code，會持續污染之後的 AI 協作品質。

---

## 建議執行順序

1. 統一 HotSeat 業務語意與文案
2. 打通 ETL metadata → DB / Qdrant / AI 搜尋排序
3. 補強店家 detail 頁的決策資訊
4. 做 SSE streaming
5. 量測 Caffeine 與 GC，再決定是否改 1000 → 30
6. 最後才做面試稿、影片、AWS

---

## Phase 2 Gate

以下條件未滿足前，不建議正式開做 `Phase 2`：

- `/shops` 與 `/ai` 的主流程已穩
- 103 家資料展示沒有明顯破洞
- AI 搜尋能合理回答場景型 query
- HotSeat / 訂位 / 支付 demo 故事已一致
- README / roadmap / demo script 已同步

滿足後，才評估 LIFF、跨縣市、店家後台、自動化爬蟲。
