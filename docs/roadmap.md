# Roadmap

> 本專案以 **6 個月主線（v1.0）+ 階段性擴充** 的方式推進。
> 已完成項目以 ✅ 標示；進行中為 🚧；規劃中為 📋。
> 「不會做的事」是刻意排除的範圍，用於說明設計決策。

---

## v1.0 — 主線（進行中，預計 2026 年 10 月完成）

> 目標：完成一個可投履歷、可上線 demo、可作為成大期末作品的完整版本。

### 工程基礎建設
- ✅ Spring Boot 2.7 → 3.2.5 升級
- ✅ Java 11 → 17 升級
- ✅ Jakarta EE 全面遷移
- ✅ Flyway SQL migration 接管
- ✅ 安全修補（路徑穿越、登出 token 失效、密碼硬編碼等）
- ✅ 死代碼清理

### 台灣在地化
- ✅ Schema 台灣化（V2-V5 migration 完成）
- ✅ 台北 25 家店家種子資料（信義 + 中山兩區深耕）
- ✅ 10 個在地店家分類（taxonomy v1，shared/taxonomy.json 為 single source of truth）
- 🚧 LINE Login OAuth 2.0 整合
- 📋 台北捷運站 GEO 查詢
- 📋 業務邏輯本地化（繁中、台幣、台灣手機格式）

### Java 後端核心
- 📋 MyBatis-Plus → Spring Data JPA + Hibernate 遷移
- 📋 Spring Security 整合（取代手刻 JWT 攔截器）
- 📋 多層快取（Caffeine + Redis + 空值快取 + 布隆過濾器）
- 📋 優惠券秒殺 + 令牌桶限流 + 分散式冪等
- 📋 Redisson 進階鎖（讀寫鎖、註解式鎖）
- 📋 RabbitMQ + Outbox 模式 + DLQ
- 📋 評論 Feed 流 + 點讚排行
- 📋 好友關注 + 簽到

### Python AI 服務
- 📋 FastAPI 起手式
- 📋 RAG pipeline（LlamaIndex + Qdrant）
- 📋 商家自然語言搜尋（「適合約會的安靜咖啡廳」）
- 📋 評論智能摘要 + 情感分析
- 📋 平台規則 AI 助手（RAG-based 客服）
- 📋 LLM Gateway（LiteLLM）+ Token 成本記錄
- 📋 Agent workflow（Planner → Tool → Critic）
- 📋 Prompt 評估（RAGAS + promptfoo）
- 📋 Guardrail（prompt injection 防禦）

### 前端
- ✅ Next.js 15 + React 19 + TypeScript 前端已上線，首頁 / 店家列表 / 店家詳情 / AI 搜尋頁已完成
- 🚧 Inline-like 主流程收斂（找店 → 看懂店 → 願意訂位）
- 🚧 AI Chat SSE 串流體驗

### 部署與可觀測性
- ✅ Docker Compose 本地一鍵啟動
- ✅ Prometheus + Grafana（Java / Python / RabbitMQ / business / token metrics）
- 🚧 結構化日誌
- 📋 AWS 部署（EC2 + S3 + CloudFront）
- 📋 Technical Report + Demo 影片

---

## v1.1 — 已規劃擴充（v1.0 完成後評估啟動）

> 目標：在主線穩定後，補上能進一步豐富展示面向的功能。

- 📋 **多元登入策略**：Google OAuth 2.0、Email/密碼登入（含 BCrypt 與找回密碼）
- 📋 **店家資料擴充**：從 25 家擴充至 50-80 家（手動整理或半自動爬蟲）
- 📋 **快取一致性深化**：Canal 監聽 MySQL binlog 同步 Redis
- 📋 **JaCoCo 測試覆蓋率報告**：Service 層目標 ≥ 70%
- 📋 **API 文件**：OpenAPI 3 + Swagger UI 整合

---

## v2.0 — 規劃中（待 v1.0 完成 + 評估時機）

> 目標：較大規模的功能擴充，需重新評估時機與必要性。
> 列在這裡不代表承諾會做，是「未來的我會再評估」。

- 📋 **訂位/預約功能**：時段管理、容量控制、取消政策
- 📋 **LIFF 內嵌**：將前端嵌入 LINE App，提供原生體驗
- 📋 **跨縣市擴充**：高雄、台中店家資料
- 📋 **店家後台**：商家管理界面（目前僅展示用戶端）
- 📋 **自動化爬蟲 Pipeline**：定期從 Google Maps 同步店家更新

---

## 目前 gate

> 2026-05 現階段判斷：`Phase 2` 先不開做，先收斂 `v1.0` 主線。

### v1.0 現在最該補的不是什麼？

- 不是先上 AWS
- 不是先錄 demo 影片
- 不是先擴到 150+ 家店

### v1.0 現在最該補的是什麼？

- HotSeat / 訂位 / 支付 demo 的業務語意一致
- ETL 評論抽取 → AI metadata → 檢索 / rerank / 展示閉環
- Inline-like 主流程體驗
- 文件真實性與面試敘事一致性

---

## 不會做的事（刻意排除）

> 這些功能要嘛跟業務定位衝突，要嘛已經有同類專案展示過，不在本專案範圍。

- ❌ **外送員 app**：本專案是「AI 用餐與訂位平台」，不是外送平台
- ❌ **完整探店筆記**：已被「評論 + AI 摘要」取代，不重複造輪
- ❌ **分庫分表**：資料量級不需要，避免過度設計
- ❌ **Kafka**：本場景是業務消息隊列、不是大數據流，採用 RabbitMQ
- ❌ **完整鏈路追蹤（SkyWalking）**：運維成本不合理，採用 Prometheus + Grafana
- ❌ **K8s 部署**：EC2 + Docker Compose 已足夠 demo
- ❌ **GraphQL / CQRS / Event Sourcing**：過度設計
- ❌ **多語言國際化**：與「台灣在地化」主軸衝突

---

## 設計取捨說明

幾個關鍵的「為什麼不做」決策，這裡簡要說明（詳細討論見 [docs/architecture.md](docs/architecture.md)）：

**為什麼用 RabbitMQ 不用 Kafka？**
本專案的消息使用場景是業務消息（訂單狀態、通知、補償），不是高吞吐量資料流。Kafka 的核心優勢（partition、stream）在本場景發揮不出來，RabbitMQ + Outbox 模式更適合。

**為什麼用 JPA 不用 MyBatis？**
台灣業界 JPA 與 MyBatis 並存，本人另一個作品「菜籃日」已使用 MyBatis 並展示其能力，本專案刻意選擇 JPA + Spring Data 以展示對兩種 ORM 哲學的理解。

**為什麼 AI 部分用 Python 不用 Spring AI？**
業界 AI 應用 95% 在 Python 生態（LangChain、LlamaIndex、Hugging Face）。本專案採用 Java 後端 + Python AI 服務的微服務拆分，符合業界實際分工。

**為什麼種子資料只做 2 個區域？**
RAG 與向量檢索的效果展示不需要大量資料覆蓋，深度（每家店完整評論、菜單、營業時間）比廣度（150+ 家店但每家資訊不全）對 demo 更有幫助。
