# Roadmap

> This roadmap is presentation-oriented. It separates what is already demo-ready, what is intentionally shown as a prototype, and what should become the next product moat.

## Current Demo Baseline — 2026-06-11

| Area | Status |
|---|---|
| Data | 600 active Taipei shops, crawler coverage reports, Qdrant payload sync, legacy seed cleanup |
| Web | Premium app shell, discovery, AI chat, shop detail, booking/payment, favorites, notifications, merchant console |
| LINE | Messaging bot, LINE Login, recommendation cards, booking/payment/cancel/incident notifications |
| AI | Semantic search, hard constraints, dialogue state, private preference memory, private AI-matched offers, incident routing, clarification policy, response contract, regression tests |
| Booking | Web/LINE booking lifecycle, demo payment, conversational reschedule, incident handling, cancellation, availability release |
| Parking | Nearby parking data, driving preference, scheduled reminders, demo spot hold concept |
| Deployment | Docker Compose infra, ngrok local tunnel for temporary demos, Nginx stable public reverse-proxy blueprint with Compose public-proxy overlay, demo readiness preflight, public-proxy smoke runner, clean MySQL migration smoke runner, and manual GitHub Actions clean-schema smoke |

## Highest-CP Work Before Presentation

- ✅ Keep demo URL, Java, AI, and Web health stable.
- ✅ Keep ngrok and Nginx responsibilities explicit: ngrok for local temporary tunnels, Nginx for stable public routing and proxy headers.
- ✅ Keep the Nginx route contract runnable through Docker Compose on `localhost:8088`.
- ✅ Keep demo readiness executable through `scripts/demo-readiness.sh`.
- ✅ Keep Nginx public-proxy smoke checks executable through `scripts/smoke-nginx-public-proxy.sh`.
- ✅ Keep fresh-schema Java/Flyway startup verifiable through `scripts/smoke-clean-mysql-migrations.sh`.
- ✅ Keep fresh-schema Java/Flyway startup reproducible in GitHub Actions through `.github/workflows/clean-mysql-migration-smoke.yml`.
- ✅ Use the public presentation guide and case studies as the core story.
- ✅ Demo AI with one clear query, one vague query, and one context-heavy query.
- 🚧 Tighten security boundaries where possible without breaking the public demo.
- 🚧 Keep README, case studies, and report narrative synchronized with current features.

## Next Product Moats

These are the highest-value next steps after the presentation.

1. **Private Preference Memory — first slice completed**
   - ✅ Remember post-meal tags, 1-3 rating, notes, and "do not recommend again" from My Bookings.
   - ✅ Persist in Java and let AI recommendation validation avoid user-marked shops.
   - Next: add ingredient dislikes, seat preferences, and group-level shared memories.

2. **Conversational Booking Changes — first slice completed**
   - ✅ Support "改 8 點，同樣 4 位" and "換成明天晚上" from the latest valid booking.
   - ✅ Java checks availability transactionally, confirms the new state, and notifies LINE.
   - ✅ Guard paid-booking reschedules that would require deposit top-up or refund, instead of silently changing payment obligations.
   - ✅ Create merchant manual deposit-adjustment tasks and apply the reschedule only after external top-up/refund handling is confirmed.
   - ✅ Track PSP settlement status, provider, transaction id, amount, and completion time before applying a deposit-delta reschedule.
   - ✅ Let customers complete TOP_UP adjustments from My Bookings through the TapPay iframe checkout.
   - ✅ Connect REFUND adjustments to a request -> reconciliation success/failure state machine.
   - ✅ Add refund reconciliation event-key idempotency and audit events.
   - ✅ Add optional HMAC signature verification for refund reconciliation callbacks.
   - ✅ Support current/previous webhook secrets for refund callback rotation.
   - ✅ Surface merchant refund SLA reporting for FAILED or stale PROCESSING refunds.
   - ✅ Let merchants mark failed/stuck refunds as escalated, with note and audit event.
   - ✅ Add merchant refund operations digest for pending escalation and escalated follow-up.
   - ✅ Let merchants trigger LINE refund operations digest notifications from the report.
   - ✅ Add scheduler-ready refund operations digest due policy with cooldown and dispatch audit.
   - ✅ Add optional source allowlist validation for production refund callbacks.
   - Next: add merchant notification preferences and provider-specific refund operations.

3. **Private AI-Matched Offers — first slice completed**
   - ✅ Avoid public coupon pages by storing offers in `tb_private_ai_offer`, separate from public voucher/Hot Seat tables.
   - ✅ Trigger private offers only for explicit discount/save-money/off-peak intent from AI recommendation flow.
   - ✅ Reuse active per-user/per-shop offers instead of creating duplicates.
   - Next: add restaurant-side quota controls, redemption at checkout, and merchant analytics for off-peak fill rate.

4. **Incident Handling — first slice completed**
   - ✅ Persist booking incidents in `tb_booking_incident` with OPEN/RESOLVED status.
   - ✅ Support user late arrival and restaurant delay messages from My Bookings.
   - ✅ Route "我會晚到 20 分鐘" through AI deterministic booking action and push LINE rescue cards.
   - ✅ Add merchant-side open incident console and resolve action under `/merchant`.
   - ✅ Suggest same-day alternative slots from Java slot inventory in the merchant incident console.
   - ✅ Let merchants send a pending alternative-time proposal and let customers accept it from My Bookings.
   - ✅ Add customer decline and proposal expiry handling so `PENDING` proposals can become `ACCEPTED`, `DECLINED`, or `EXPIRED`.
   - ✅ Push LINE proposal cards with accept/decline links that call back into Java.
   - ✅ Reuse the Java reschedule contract to block paid proposal acceptance when it would create deposit top-up or refund work.
   - ✅ Surface merchant-facing manual deposit adjustment notes and apply approved changes from the merchant console.
   - ✅ Require PSP settlement tracking before merchant adjustment resolution can apply the booking change.
   - ✅ Add customer top-up payment from My Bookings while keeping merchant-side apply as the final booking mutation.
   - ✅ Add refund settlement reconciliation so failed refunds cannot be applied as completed booking changes.
   - ✅ Store refund request/reconciliation audit events and ignore duplicate PSP event keys.
   - ✅ Add merchant SLA reporting for stuck refunds.
   - ✅ Add escalation tracking for failed or stuck refunds.
   - ✅ Add merchant operations digest for refund escalation follow-up.
   - ✅ Add triggerable LINE digest notification for refund operations.
   - ✅ Add scheduled notification policy contract for repeated failed refunds.
   - ✅ Add provider callback source validation with allowlist and trusted proxy handling.
   - Next: add merchant notification preferences and provider-specific refund operations.

5. **Group Dining Decision Flow**
   - Share link in group chat.
   - Members vote on time, budget, district, dietary restrictions.
   - AI returns top options and one-click booking.

## Demo Boundaries

- Demo payment proves state transition and notification contract; deposit-delta TOP_UP now has customer checkout, and REFUND has demo/internal reconciliation with idempotency/audit, optional HMAC signature verification with secret rotation and source allowlist, merchant SLA visibility, manual escalation tracking, operations digest, triggerable LINE digest notification, and scheduler-ready due policy with cooldown dispatch audit. Production refund rollout still needs merchant notification preferences and provider-specific refund operations.
- Demo parking spot hold shows product direction, not confirmed operator-side parking reservation.
- Parking availability depends on upstream/cache update cadence.
- Recommendation is advisory; store announcements and real venue policies remain the source of truth.
- Stable public deployment should use the Nginx route contract rather than a long-lived ngrok URL; ngrok remains useful for local LINE webhook/Login testing.

---

## Historical Planning Notes

The section below preserves earlier planning context. Some items have already been completed or superseded by the current demo baseline above.

---

## v1.0 — 主線（進行中，預計 2026 年 10 月完成）

> 目標：完成一個可投履歷、可公開展示、可作為 portfolio-grade product demo 的完整版本。

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

幾個關鍵的「為什麼不做」決策，這裡簡要說明；完整演進脈絡見 [Project Journey](project-journey.md)，跨服務責任分工見 [ADR 0001](adr/0001-java-python-frontend-split.md)：

**為什麼用 RabbitMQ 不用 Kafka？**
本專案的消息使用場景是業務消息（訂單狀態、通知、補償），不是高吞吐量資料流。Kafka 的核心優勢（partition、stream）在本場景發揮不出來，RabbitMQ + Outbox 模式更適合。

**為什麼用 JPA 不用 MyBatis？**
台灣業界 JPA 與 MyBatis 並存，本人另一個作品「菜籃日」已使用 MyBatis 並展示其能力，本專案刻意選擇 JPA + Spring Data 以展示對兩種 ORM 哲學的理解。

**為什麼 AI 部分用 Python 不用 Spring AI？**
業界 AI 應用 95% 在 Python 生態（LangChain、LlamaIndex、Hugging Face）。本專案採用 Java 後端 + Python AI 服務的微服務拆分，符合業界實際分工。

**為什麼先聚焦台北 600 家，而不是全台店家？**
AI 推薦 demo 的關鍵不是把地圖鋪滿，而是讓每一家進入推薦池的店有足夠 metadata：分類、行政區、捷運、照片、評論、AI summary、ABSA、價格訊號與 Qdrant payload。先把台北資料做深，能比全台淺資料更穩定地展示 grounded recommendation。
