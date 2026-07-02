# ByteBites Project Journey — 從後端基礎到 AI 用餐營運平台

> This document summarizes the full engineering journey behind ByteBites. It is written for presentation, review, and future handoff: what changed, why it changed, what trade-offs were made, and what the project proves.

## 0. 一句話版本

ByteBites 從一個本地生活服務後端，演進成完整 AI 用餐營運平台：台灣化資料模型、LINE Login、捷運 GEO、多層快取、RabbitMQ/Outbox、Google Maps 爬蟲、ABSA 評論分析、Qdrant 語意搜尋、Web/LINE AI agent、訂位付款同步、候補通知、停車提醒、商家後台與公開 demo 部署。到目前為止，專案已累積 522 次 commit，重點不是 commit 數字本身，而是每一輪都把「能跑」往「可靠、可展示、可解釋」推進。

## 1. Stage 0 — 接手、體檢、現代化

### 起點

最初專案已經有一組 Spring Boot 後端基礎，包含登入、店家、優惠券、秒殺、社群等模組。它的優點是功能範圍廣，能支撐後續產品化；風險則是安全洞、死代碼、舊框架、硬編碼設定與環境可攜性不足。

### 做了什麼

- Repo 結構重整。
- 初始 code review。
- 修安全問題：Lua 秒殺結果未判斷、logout token 未失效、path traversal、SMS code log、DB credentials。
- 清死代碼：MD5 password encoder、空 module、舊註解實作。
- Java 17 + Spring Boot 3.2 + Jakarta migration。

### 為什麼重要

這一階段不是最炫的功能，但它建立了可信地基。沒有先處理安全、版本、結構與設定，後面所有 AI 和 LINE 功能都只是堆在不穩的基礎上。

## 2. Stage 1 — 台灣在地化

### 起點

餐廳產品如果資料模型、分類、地理語意仍停留在不相符的場景，就算 UI 很漂亮也不像台灣產品。

### 做了什麼

- Flyway 接入 migration 流程。
- 資料表與欄位台灣化。
- 餐廳分類改成台灣飲食場景。
- LINE Login 取代簡訊登入。
- 台北捷運資料進 Redis GEO。
- 店家分類、區域、捷運篩選 API。

### 產品意義

台灣使用者不是只用行政區找店，很多時候會說「中山站附近」「信義安和附近」。捷運 GEO 讓搜尋更貼近真實語言。

## 3. Stage 1.5 — 進階工程能力

### 做了什麼

- Caffeine + Redis 多層快取。
- Bloom filter 防穿透。
- Redis token bucket rate limit。
- Idempotency annotation。
- Redisson read-write lock。
- RabbitMQ + Outbox + DLQ。

### 為什麼不是過度工程

這些能力一開始看起來和 AI 推薦無關，但它們是交易系統的基礎。訂位、付款、取消、通知都需要：

- 防止重複請求。
- 保證事件不靜默消失。
- 支援 eventual consistency。
- 在 demo 壓力下保持可解釋。

## 4. Stage 2 — 資料產品化

### 起點

AI 推薦不可能只靠 prompt。資料少、分類錯、照片缺、評論不足，模型就會亂猜。

### 做了什麼

- Google Places / Maps crawler。
- Google Maps review tab hardening。
- query normalization 與 SEO suffix cleanup。
- Mongo review sync。
- media manifest。
- data coverage report。
- taxonomy audit。
- Qdrant payload sync。
- legacy seed cleanup。

### 重要數字

- 599 active Taipei shops。
- media coverage 100%。
- AI summary coverage 100%。
- ABSA / Mongo review coverage 99.8%。
- price signal coverage 86.3%。

### 關鍵學習

資料工程不是「抓到資料」就結束。真正重要的是覆蓋率、可追蹤性、可重跑、可修正與可驗證。

## 5. Stage 3 — AI Agent 與推薦體驗

### 起點

最初的 AI 推薦能回答，但不穩：

- 假串流。
- 推薦文字和卡片數量不一致。
- 模型有時亂 call tool。
- 語意搜尋會把分類不符的店混進來。
- 使用者 follow-up 會被當成新問題。

### 做了什麼

- 真 SSE streaming。
- Gemini model ablation。
- ABSA pipeline。
- structured recommendation contract。
- hard constraints：district / cuisine / taxonomy。
- Agent response contract。
- ordinal follow-up。
- exact shop booking。
- booking draft memory。
- clarification policy。

### 產品取捨

推薦卡不展示 raw ABSA negative/mixed bars，因為推薦頁的任務是「給出選擇理由」，完整評論透明度放在 detail page。這是產品語境的取捨，不是隱藏資料。

## 6. Stage 4 — Web / LINE / Booking 交易閉環

### 起點

Web AI、LINE bot、LINE Login、Java booking、付款和取消如果各自為政，demo 很容易破：

- Web 顯示已付款，LINE 沒收到。
- LINE bot 推薦店，但訂位 owner 對不上。
- 取消訂位沒有釋放或通知。
- AI 說第 2 家，但系統不知道第 2 家是哪家。

### 做了什麼

- LINE Login identity 與 Messaging API identity sync。
- booking owner binding。
- payment notification to LINE。
- cancel notification to LINE。
- availability released notification。
- Web my-bookings 狀態同步。
- LINE Flex card action。
- Contract tests。

### 關鍵原則

Web 和 LINE 是入口，不是資料來源。交易狀態以 Java backend 為準。

## 7. Stage 5 — 停車提醒與差異化

### 做了什麼

- 店家詳情頁顯示附近停車場。
- 訂位選擇是否開車。
- Java 排程在訂位前約 2 小時掃描 reminder。
- LINE 推送附近停車空位資訊。
- demo parking spot hold：展示未來可預約車位的產品方向。

### 為什麼有價值

這讓 ByteBites 不只是「找餐廳」，而是處理「準時抵達」這個真實痛點。這是簡報中最容易被記住的差異化。

## 8. Stage 6 — UI/UX 與品牌定位

### 做了什麼

- inline-style IA 研究後，改回 ByteBites 自己定位。
- Premium dining surfaces。
- 更安靜的 app shell。
- Shop card data quality ranking。
- AI page、explore page、detail page、booking/payment page polish。
- 中英定位與更精緻的中文字體節奏。

### 現在的定位

ByteBites 不是 inline clone，也不是普通 chatbot。它是：

```text
會推薦，也會安排的 AI 用餐營運平台。
```

## 9. Stage 7 — 發表前品質硬化

### 做了什麼

- 移除 Web AI 右下角浮動球，避免與主介面衝突。
- 修復公開 demo 下 LINE Login callback / proxy path / mobile rendering 問題。
- 強化 AI dining intent routing：明確餐飲需求先查資料，模糊需求先追問。
- 強化情境 rerank：聊天、商務、家庭、聚餐等場景不被一般熱門度覆蓋。
- 更新 README、Case Studies、Presentation Guide，讓專案故事能被快速理解。
- 建立 `scripts/verify-portfolio.sh`，把 Java、AI、ETL、data gate、Web tests 和 production build 收斂成單一作品驗證入口。
- 新增 GitHub Actions portfolio CI matrix，讓 reviewer 能用熟悉的方式確認每個子系統。
- 新增內部 portfolio evidence map，整理 Java backend、AI application、full-stack 三種職缺的 code anchors 和測試證據。
- 將訂位庫存與 booking payload 抽成更深的 Module，讓交易流程的 Locality 和 test surface 更清楚。

### 為什麼重要

發表前最怕的不是少一個功能，而是：

- 同學打不開；
- AI 卡在處理中；
- 手機畫面變成未套 CSS；
- 評審聽不出工程深度；
- Demo 功能和真實邊界沒有說清楚。

這一階段把產品從「功能很多」整理成「現場可被理解、可被相信、可被驗證」。

## 10. 最值得在報告裡講的抉擇

1. **先補安全與框架，再做 AI**：避免在不穩基礎上堆亮點。
2. **資料 coverage 優先於 prompt magic**：AI 推薦的上限由資料品質決定。
3. **推薦卡不展示完整負面 ABSA**：推薦頁和詳情頁責任不同。
4. **交易狀態以後端為準**：Web / LINE 只是入口。
5. **停車提醒採負責任 demo**：展示產品願景，但不誇大即時車位能力。
6. **不做 inline clone**：吸收質感，但主張 ByteBites 自己的 AI operations 定位。
7. **作品要有證據鏈**：README、case studies、code anchors、tests、CI 和 data gate 要能互相指向。

## 11. What This Project Proves

ByteBites proves that an AI product project can go beyond a prompt demo. It contains:

- real backend modernization;
- real data engineering;
- real vector search and taxonomy constraints;
- real AI agent contract design;
- real Web / LINE identity sync;
- real booking and notification lifecycle;
- real product judgment around UX, data transparency, and demo honesty.

The strongest story is not "we used AI." The strongest story is:

```text
We used AI to connect a fragmented dining journey into one coherent product workflow.
```
