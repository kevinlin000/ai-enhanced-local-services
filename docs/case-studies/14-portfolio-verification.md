# Case Study 14: Portfolio Verification — 從很多亮點到可審查作品

**TL;DR** ByteBites 的問題不是沒有亮點，而是亮點太分散：Java booking、AI agent、資料品質、Web/LINE、停車提醒、UI positioning 各自都能講，但審查者很難在短時間內確認哪些是真的。這輪把作品整理成可審查的 evidence chain：單一驗證入口、CI matrix、資料品質 gate、release boundary，並把訂位庫存與 booking payload 抽成更深的 Java Module。

**Tech:** GitHub Actions / Bash / Python standard library / Maven / pytest / pnpm / Next.js build / Spring Boot contract tests
**Repo:** `scripts/verify-portfolio.sh`, `scripts/release-readiness.sh`, `scripts/verify-data-quality.py`, `scripts/verify-nginx-template.py`, `scripts/verify-clean-migration-workflow.py`, `scripts/verify-release-boundary.py`, `scripts/smoke-clean-mysql-migrations.sh`, `.github/workflows/portfolio-ci.yml`, `.github/workflows/clean-mysql-migration-smoke.yml`, `README.md`, `docs/architecture-overview.md`

## 1. 起點：功能很多，但評審不一定看得到

專案已經包含：

- Java booking/payment/cancel/LINE notification；
- Python AI concierge、semantic search、booking draft；
- ETL data coverage、taxonomy audit、Qdrant payload sync；
- Web AI、booking UI、notifications、merchant console；
- 13 篇 case studies。

但如果沒有一條清楚的審查路線，這些亮點會變成「散在 repo 裡的功能」。讀者不會幫你慢慢挖。

## 2. 決策：把作品變成可驗證，而不是只靠 README 說服

我新增一個單一入口：

```bash
scripts/verify-portfolio.sh
```

它依序跑：

```text
Backend Java contract tests
AI service tests
ETL data-quality tests
Portfolio data-quality gate
Nginx deployment template contract
Clean MySQL migration smoke contract
Clean MySQL migration workflow contract
Release boundary contract
Web unit/design contract tests
Web production build
```

這讓作品從「我說有測試」變成「你可以直接跑」。

其中 deployment 和 clean migration smoke 在 portfolio gate 只跑離線 contract：template verifier、`bash -n`、`--dry-run`。真正需要 Docker、MySQL、Redis、RabbitMQ 和 Java process 的 live smoke，保留給正式 demo rehearsal 執行，避免日常 portfolio verification 被本機服務狀態綁架。

後續再補 release boundary 和 `scripts/release-readiness.sh`，把 demo 前檢查整理成四層：dry-run、offline、full portfolio、live-local。這讓發表前不需要憑記憶找命令。

## 3. CI matrix：把本機驗證搬到 reviewer 熟悉的形狀

GitHub Actions 拆成清楚的 jobs：

- Backend Java
- AI Service Python
- ETL Pipeline
- Data Quality Gate
- Web
- Clean MySQL Migration Smoke, manual

這對面試作品很重要，因為 reviewer 看到的是工程習慣：每個子系統有自己的驗證，跨系統又有一個 portfolio-level gate。

Clean MySQL Migration Smoke 沒有放進每次 push 的 matrix，而是手動觸發。原因是它會啟 MySQL、Redis、RabbitMQ 和 Java live process；它的價值是正式 demo 前或 reviewer 想看 fresh-schema startup 時，一鍵在 GitHub runner 重現。

## 4. Data quality gate：AI 作品不能只驗程式

AI 產品的風險常常不是 syntax error，而是資料證據掉了：

- 店家數不足；
- media coverage 退化；
- taxonomy 決策被改壞；
- eval manifest 消失；
- case study 索引漏掉；
- README 宣稱和 repo 內容不一致。

所以 `scripts/verify-data-quality.py` 不依賴外部服務，只用 repo 內資料檢查：

- 599 active shops；
- 11 個 coverage threshold；
- conversation quality cases；
- agent concierge / RAG eval manifests；
- taxonomy primary categories；
- case-study links；
- portfolio evidence map；
- reviewer-facing Markdown links。

這是 AI application engineer 面試很值得講的點：AI 可靠性不只靠 model，也靠資料、文件連結與評估 gate。

## 5. Java Module 深化：把訂位庫存從 controller 拿出來

同一輪也把 booking capacity 從 controller SQL 抽成：

```text
BookingSlotInventory
```

它的 Interface 很小：

```text
reserve(shopId, date, time, tableType, people)
release(shopId, date, time, tableType, people)
```

但 Implementation 藏住：

- slot inventory auto-create；
- table type normalization；
- default capacity；
- atomic capacity update；
- cancel release 不低於 0。

這提升了 Locality：訂位容量規則不再散在 controller。測試也可以直接跨這個 Seam 驗證。

## 6. AI Module 深化：booking draft 從 main.py 抽出

AI 對話狀態也做了類似處理：

```text
booking_draft.py
```

它集中處理：

- compact prefill；
- merge missing fields；
- edit override；
- missing field detection；
- confirmation answer。

這讓 booking follow-up 不再只是 `main.py` 裡的一堆分支，而是有可測 Interface 的任務狀態 Module。

## 7. 下一個亮點落地：對話式改單

後續又把 roadmap 上的「對話式改單」做成完整 vertical slice：

```text
AI: "改成明晚 8 點，同樣 4 位"
  -> update_booking tool
  -> Java BookingRescheduleService
  -> reserve new slot first
  -> release old slot only after success
  -> LINE booking updated notification
  -> Web My Bookings reloads backend state
```

這個功能對 Java / full-stack 面試很有價值，因為它展示的不只是 AI 文字理解，而是交易一致性：新時段滿位時，原訂位不能被破壞；同一時段只改人數時，也不能用錯誤的 full-reserve/full-release 演算法誤判容量。

## 8. 第二個亮點落地：私人偏好記憶

接著把「食記不是公開評論，而是讓 AI 更懂你」做成第一個可測版本：

```text
My Bookings post-meal tags
  -> Java DiningMemoryService
  -> tb_dining_memory
  -> AI reads /api/dining-memory/me
  -> validator removes do-not-recommend shops from recommendations
```

這個切法刻意不做公開評分牆。使用者只記錄給下次自己的決策標籤，例如「安靜」「太吵」「不再推薦」。AI 端也不是只把記憶塞進 prompt，而是在 validator 裡強制避開私人標記的店，避免 LLM 忘記規則。

## 9. 第三個亮點落地：AI 私密配對優惠

再把「優惠券不是公開撒錢，而是 AI 精準救轉換」做成第一個可審查版本：

```text
discount/off-peak intent
  -> AI recommendation enrichment
  -> Java PrivateAiOfferService
  -> tb_private_ai_offer
  -> per-user/per-shop active offer reuse
  -> AI recommendation card shows private offer only to that user
```

這個切法刻意不複用公開 `Voucher` / `Hot Seat` 表。原因是產品語意不同：公開券是廣告，私密 offer 是 AI 根據使用者需求與離峰時段做的決策輔助。第一版先做可測的觸發、持久化、重複防護與前端私密展示，沒有誇大成完整商家結算或防詐系統。

## 10. 第四個亮點落地：臨場救場通知

再把「出事時 AI 比介面更快」做成可測 workflow：

```text
user says "我塞車會晚到 20 分鐘"
  -> deterministic booking incident route
  -> Java BookingIncidentService
  -> tb_booking_incident
  -> BookingLineNotificationService
  -> AI internal LINE rescue Flex card
  -> My Bookings shows latest open incident
  -> Merchant console shows open incident
  -> Java suggests same-day alternative slots from inventory
  -> merchant sends pending proposal
  -> AI internal LINE proposal Flex card
  -> customer accepts or declines proposal in LINE or My Bookings
  -> accepted proposal uses BookingRescheduleService to change the booking
  -> Java blocks paid-booking deposit top-up/refund deltas before slot mutation
  -> blocked deposit deltas create merchant manual adjustment tasks
  -> customer completes TOP_UP from My Bookings through TapPay checkout
  -> merchant creates REFUND request before any refund-based apply
  -> PSP refund reconciliation marks REFUND as COMPLETED or FAILED
  -> duplicate PSP refund event keys are treated as idempotent replay
  -> refund request and reconciliation attempts are written to an audit table
  -> configured refund webhook secret requires HMAC signature and fresh timestamp
  -> current/previous refund webhook secrets allow rotation without callback downtime
  -> configured refund webhook source allowlist rejects unknown callback sources
  -> merchant console surfaces failed or stale processing refund SLA
  -> merchant marks a failed or stuck refund as escalated with audit trail
  -> merchant refund operations digest separates pending escalation from escalated follow-up
  -> merchant can trigger a LINE refund operations digest for linked manager accounts
  -> scheduler-ready policy decides due dispatch with cooldown and audit trail
  -> Java only allows apply after settlement is completed
  -> Java applies the reschedule and resolves the related incident proposal
  -> declined/expired proposal keeps incident OPEN so merchant can propose again
```

這個功能的重點不是多一則通知，而是把現場狀況變成後端狀態：OPEN / RESOLVED、原時間、新預估時間、顧客可讀訊息、商家提案，以及 ACCEPTED / DECLINED / EXPIRED 的顧客回覆都可追蹤。AI 只負責理解「我會晚到」這種自然語言與組 LINE 卡片；真正的 incident 建立、通知、替代時段建議、顧客確認、訂金差額防護、PSP settlement tracking、退款 reconciliation idempotency / audit / signature verification / secret rotation / source allowlist、refund SLA visibility / escalation tracking / operations digest notification / scheduled policy 與改單仍由 Java contract 驗證。

## 11. Reviewer Evidence Chain

最後整理一份內部證據地圖，目標不是放在公開入口，而是確保每個 claim 都能回到 code、test、data 或 case study：

```text
claim -> code anchor -> test/eval -> public evidence doc
```

它不是一般文件，而是審查準備用索引：

- Java backend track；
- AI application track；
- full-stack track；
- code anchors；
- tests；
- demo script；
- what not to overclaim。

這直接解決「亮點被埋沒」的問題。不同職缺可以用同一個專案講不同能力，但都回到同一組證據。

## 12. 我學到的事

**頂級作品不是功能越多越好，而是證據越清楚越好。** 讀者需要快速看到 claim、code、test、demo 的連線。

**CI 不是形式。** 對 portfolio 來說，CI 是可信度的一部分。

**資料 gate 是 AI 作品的核心。** AI 系統的 regression 不一定是程式壞掉，也可能是資料覆蓋、taxonomy 或 eval case 退化。

**文件不是裝飾。** 好文件能把分散的工程深度變成可理解的作品敘事。

## English Version

# Case Study 14: Portfolio Verification — From Many Highlights to Reviewable Evidence

ByteBites did not lack features. The risk was that the strongest parts were scattered across Java backend code, Python AI flows, ETL data quality, Web/LINE sync, and case studies.

The fix was to build a portfolio evidence chain: one verification command, a CI matrix, a manual clean-schema migration smoke workflow, an offline data-quality gate, a reviewer evidence map, and deeper modules for booking inventory and booking drafts.

The important shift is from claims to proof. A reviewer can now trace the project through code anchors, tests, data evidence, and demo flows. This makes the repository stronger for Java backend, AI application, and full-stack interviews.
