# ByteBites — AI Dining Operations Platform

> **中文摘要**：ByteBites 不只是餐廳推薦系統，而是一個 AI 用餐營運流程：餐廳搜尋、AI 推薦、AI 私密配對優惠、訂位、對話式改單、臨場救場通知、私人偏好記憶、訂金付款、LINE 通知、候補、取消、停車提醒與 demo 車位保留。
> **English summary**: ByteBites is not only a restaurant recommender. It is an AI-assisted dining operations flow: search, recommendation, private AI-matched offers, booking, conversational rescheduling, real-time incident handling, private preference memory, deposit payment, LINE notification, waitlist, cancellation, parking reminder, and demo parking spot hold.

## 產品定位 / Product Thesis

多數餐廳產品停在 discovery：使用者瀏覽餐廳、打開詳情頁，後面的判斷、訂位、付款、提醒與交通安排都交回給使用者。ByteBites 的目標是往後多走一步：使用者用自然語言描述需求，系統協助整理候選餐廳、保留座位、處理 demo 訂金付款、同步 LINE 狀態、建立候補通知，並在訂位前提醒附近停車資訊。

Most restaurant products stop at discovery: browse restaurants, open a detail page, and leave the rest to the user. ByteBites goes further. A user can describe a dining need in natural language, receive structured recommendations, reserve a table, pay a demo deposit, receive LINE status updates, set availability notifications, and get parking guidance before the booking.

這個專案不是靜態展示頁。它累積了 **522 commits**，從 Spring Boot 在地化後端，演進成包含資料爬蟲、語意搜尋、評論分析、跨通路身份同步、交易狀態 contract、LINE bot、停車提醒與公開 demo 部署的完整 AI 產品。

This is not a static showcase. Across **522 commits**, the system evolved from a localized Spring Boot backend into a full-stack AI product with data pipelines, semantic search, review intelligence, cross-channel identity sync, transaction contracts, LINE bot integration, parking reminders, and demo deployment.

## 發表重點 / Presentation Focus

ByteBites 最值得展示的不是「有聊天機器人」，而是把 AI 放進真實用餐流程：從模糊需求、資料檢索、候選餐廳、私密配對優惠、訂位、付款、對話式改單、臨場救場通知、私人偏好記憶、取消、候補、LINE 通知到停車提醒，全部有狀態、有 contract、有測試。這讓它更像一個 AI dining operations product，而不是 prompt demo。

The key presentation point is not that ByteBites has a chatbot. It is that AI is embedded into an operational dining workflow: ambiguous intent, retrieval, recommendations, booking, payment, rescheduling, incident handling, cancellation, waitlist, LINE notifications, and parking reminders all share state, contracts, and tests.

Fast links:

- [Presentation Guide / 發表指南](docs/presentation-guide.md)
- [Portfolio Readiness Scorecard / 作品成熟度評分](docs/portfolio-readiness-scorecard.md)
- [Portfolio 100 Roadmap / 100 分路線圖](docs/portfolio-100-roadmap.md)
- [Demo Evidence Package / 展示證據包](docs/demo-evidence-package.md)
- [Architecture Overview / 架構總覽](docs/architecture-overview.md)
- [Release Boundary / 發表交付邊界](docs/release-boundary.md)
- [Nginx Public Deployment Boundary](docs/deployment-nginx.md)
- [Portfolio Evidence Map / 面試證據地圖](docs/portfolio-evidence-map.md)
- [Project Journey / 專案演進總覽](docs/project-journey.md)
- [Case Studies Index / 工程案例索引](docs/case-studies/README.md)

## Portfolio Verification / 作品驗證

The repository has a single verification entry point for portfolio review:

```bash
scripts/verify-portfolio.sh
```

It runs the same core checks protected by CI:

| Area | Command | Purpose |
|---|---|---|
| Backend Java | `mvn test` | Booking/payment/LINE/parking contract tests; manual Redis/MySQL cache warm-up tests are explicitly skipped |
| AI service | `uv run --no-sync pytest tests -q` | Agent conversation, LINE flow, guardrail, internal notification contract tests |
| ETL pipeline | `uv run --no-sync pytest tests -q` | Taxonomy, normalizer, audit sync, data-quality tests |
| Data quality gate | `python3 scripts/verify-data-quality.py` | Offline checks for coverage thresholds, eval manifests, taxonomy decisions, case-study links, evidence map anchors, and reviewer-facing Markdown links |
| Nginx deployment contract | `python3 scripts/verify-nginx-template.py` | Offline contract check for stable public reverse-proxy routes, Docker Compose proxy overlay, demo-readiness and smoke-runner syntax/dry-run, headers, LINE URLs, and source-allowlist guidance |
| Clean MySQL migration smoke contract | `bash -n scripts/smoke-clean-mysql-migrations.sh && scripts/smoke-clean-mysql-migrations.sh --dry-run` | Offline syntax/dry-run guard for the live clean-schema Flyway smoke runner |
| Clean MySQL migration workflow contract | `python3 scripts/verify-clean-migration-workflow.py` | Offline contract check for the manual GitHub Actions clean-schema smoke workflow |
| Release boundary contract | `python3 scripts/verify-release-boundary.py` | Offline contract check for the release handoff, readiness script, verification ladder, and production-gap framing |
| Web | `pnpm test` | UI contract and design guard tests |
| Web build | `pnpm build:ci` | Offline-friendly production build using Next.js webpack mode |

CI lives in `.github/workflows/portfolio-ci.yml` and runs the same matrix with locked dependency installation. The live clean-schema migration smoke has its own manual workflow at `.github/workflows/clean-mysql-migration-smoke.yml`, because it starts MySQL, Redis, RabbitMQ, and Java. Local verification assumes dependencies have already been installed in each module; CI performs the install step.

## 核心能力 / What It Does

- **AI 用餐助理 / AI dining concierge**  
  理解模糊需求、記住推薦上下文、支援「第 2 家」「明晚 7 點 4 人」這類 follow-up，並在資訊不足時追問。

- **餐廳探索 / Restaurant discovery**  
  依料理、行政區、捷運、評分、價位、資料品質與 AI metadata 篩選和排序。

- **結構化推薦卡 / Structured recommendation cards**
  推薦文字與卡片使用同一份 `recommended_shop_ids`，避免「文字講 2 家、UI 顯示 3 家」的 AI 產品常見錯誤。

- **訂位、改單與付款 / Booking, rescheduling, and payment flow**
  建立訂位、保留座位、對話式改單、demo 訂金付款、取消訂位，並讓 Web / LINE 狀態一致；已付款訂位若改單會產生訂金加收或退款，Java 會阻擋自動改單、建立訂金差額項目，TOP_UP 可由顧客在 My Bookings 走 TapPay checkout，REFUND 需先建立退款請求並等待 PSP reconciliation 成功後才允許套用改單；退款 callback 支援 event key 去重、audit trail、可選 HMAC webhook signature、secret rotation 與 source allowlist，商家後台也會顯示 FAILED 或超時 PROCESSING refund SLA、營運摘要，可手動發送 LINE digest，並以 scheduler-ready policy 判斷 cooldown / due dispatch，再標記已升級處理。

- **臨場救場通知 / Real-time incident handling**
  使用者可對 AI 說「我會晚到 20 分鐘」，或在我的訂位建立救場通知；Java 會記錄 incident，LINE 會推送現場狀況與替代時段提案卡片，商家後台可提出替代時段，顧客可從 Web 或 LINE 接受、拒絕或讓提案逾期，只有接受後才正式改單。

- **私人偏好記憶 / Private preference memory**
  用餐後記錄 1-3 顆星、短標籤與「不再推薦」，下次 AI 推薦會避開使用者私人標記的店。

- **AI 私密配對優惠 / Private AI-matched offers**
  不做公開優惠券頁；當使用者明確想省錢、離峰用餐或可能流失時，AI 透過 Java 建立只對本人可見的限時 offer。

- **LINE 雙整合 / LINE dual integration**  
  LINE Login 負責 Web 身份；Messaging API bot 負責聊天推薦、Flex cards、通知與提醒。

- **候補與通知 / Availability notifications**  
  可追蹤已滿時段，空位釋出後通知使用者。

- **停車提醒 / Parking flow**  
  訂位可選是否開車；系統在訂位前提醒附近停車場資訊，並提供 demo 車位保留概念。

- **資料品質層 / Data quality layer**  
  Google Places / Maps crawler、Mongo review sync、media manifest、ABSA、taxonomy audit、Qdrant payload sync、legacy seed cleanup。

## 展示路線 / Demo Path

1. 首頁：展示 ByteBites 的定位「會推薦，也會安排」。
2. Web AI：輸入 `大安區 7 人 適合聊天` 或 `中山區 商務宴請 台菜 安靜包廂`。
3. 推薦卡：展示 AI 理由、照片、招牌菜、評論亮點與詳情頁。
4. 訂位：選日期、人數、是否開車，完成 demo 訂金付款。
5. 改單：對 AI 說 `改成明晚 8 點，同樣 4 位`，或在「我的訂位」頁修改時間。
6. 救場：對 AI 說 `我塞車會晚到 20 分鐘`，或在「我的訂位」建立店家延誤 demo 通知，展示 LINE rescue card；商家後台提出替代時段後，LINE proposal card 和「我的訂位」都可接受/拒絕，真正改單仍由 Java contract 完成，且已付款訂位的補款差額可在 My Bookings 走 TapPay checkout，退款差額則需完成 PSP reconciliation，商家後台會標示卡住或失敗的退款 SLA、營運摘要，並可留下升級處理備註。
7. 私人記憶：在「我的訂位」頁記錄 `太吵` / `不再推薦`，再展示 AI 推薦會避開。
8. 私密 offer：輸入 `想找有優惠、比較省錢的日式料理` 或 `明天下午 5:30 離峰火鍋`，展示 AI 推薦卡上的私密 offer。
9. LINE：展示訂位、付款、改單、取消、候補或停車提醒訊息。
10. 商家後台：展示 slot inventory、open incident queue、替代時段提案與訂位管理不是純前端假資料。

Before a formal live demo, run the clean migration smoke once against local Docker infra:

```bash
scripts/smoke-clean-mysql-migrations.sh --timeout 180
```

It creates a temporary MySQL database, starts Java on a temporary port, waits for `/actuator/health`, then stops Java and drops the database. This catches Flyway clean-schema regressions that normal unit tests can miss.

For a cloud-side rehearsal, trigger the **Clean MySQL Migration Smoke** workflow in GitHub Actions. It boots CI MySQL/Redis/RabbitMQ and runs the same smoke script.

1. Homepage: show the positioning, "AI recommends and arranges."
2. Web AI: ask realistic needs such as `大安區 7 人 適合聊天`.
3. Recommendation cards: show AI reasons, photos, dishes, review highlights, and detail pages.
4. Booking: choose date, party size, driving preference, and demo deposit payment.
5. Rescheduling: ask the AI to change the latest booking to another time.
6. Incident handling: tell the AI `我塞車會晚到 20 分鐘`, show the LINE rescue card, then show the merchant proposal card with LINE accept/decline actions backed by Java.
7. Private memory: tag a previous booking as `太吵` / `不再推薦`, then show the AI avoids it.
8. Private offer: ask for a discount or off-peak dining need and show the private offer badge on the AI card.
9. LINE: show booking/payment/cancel/waitlist/parking notifications.
10. Merchant console: show that slot inventory and bookings are not just front-end mockups.

## 系統快照 / Current System Snapshot

| Area | Status |
|---|---|
| Frontend | Next.js app with discovery, AI chat, bookings, favorites, notifications, merchant console |
| Backend | Spring Boot 3.2 / Java 17 / MySQL / Redis / RabbitMQ / Flyway |
| AI service | FastAPI, Gemini agent, semantic search, private memory/offers, rescue incident routing, streaming responses, LINE bot integration |
| Vector DB | Qdrant collection with enriched shop payloads |
| Data | 600 active Taipei shops, curated media coverage, Mongo-backed reviews, ABSA metadata |
| LINE | Separate LINE Login and Messaging API integrations |
| Observability | Docker Compose infra, Prometheus, Grafana, health endpoints |
| Deployment | ngrok local tunnel for temporary demos; Nginx stable public reverse-proxy blueprint and Docker Compose public-proxy overlay |
| Validation | Java, Python, and Web build/test coverage for critical contracts |

## 架構 / Architecture

```text
Browser / LINE
  |
  v
Next.js Web
  |-- discovery, AI chat, booking/payment UI
  |-- proxy to Java and AI services for demo deployment
  |
  +--> Spring Boot backend
  |      |-- auth, shop, booking, payment, cancellation APIs
  |      |-- LINE Login identity and notification contracts
  |      |-- MySQL / Flyway / Redis / RabbitMQ / scheduled reminders
  |
  +--> FastAPI AI service
         |-- Gemini agent and dialogue policy
         |-- Qdrant semantic search
         |-- cuisine/district/category constraints
         |-- LINE Messaging webhook and Flex cards

ETL / data quality
  |-- Google Places / Maps crawler
  |-- Mongo review sync
  |-- ABSA pipeline
  |-- taxonomy audit and Qdrant payload sync
```

## 工程亮點 / Engineering Highlights

- **AI agent as workflow, not chatbot**  
  Agent 不是只回答問題，而是會保留推薦上下文、處理 ordinal follow-up、鎖定訂位選擇、確認取消、保存 booking draft。

- **Cross-channel identity sync**  
  LINE Login 與 LINE bot user identity 被收斂到同一個 ByteBites user，讓 Web 訂位、LINE 通知與付款/取消狀態一致。

- **Structured AI contract**  
  Agent narrative、推薦卡、比較表、booking CTA 使用同一份結構化 payload，降低 AI 自由文字和 UI 狀態分裂的風險。

- **Taxonomy hard constraints**  
  明確料理與地區意圖不能被向量相似度覆蓋；例如台菜 query 不應混入韓式或居酒屋結果。

- **Crawler-driven data quality**  
  爬蟲不是一次性工具，而是包含 query cleanup、retry queue、review sync repair、coverage audit、manual taxonomy audit 的資料工程流程。

- **Booking lifecycle consistency**
  訂位、付款、對話式改單、臨場救場、訂金差額 PSP settlement tracking、退款 reconciliation idempotency / audit / signature verification / secret rotation / source allowlist / SLA visibility / escalation tracking / operations digest notification / scheduled policy、取消、LINE notification、availability release 都有後端 contract 與測試保護。

- **Refund webhook boundary**
  Demo 環境不設定 `bytebites.refund.webhook.secret` 與 `bytebites.refund.webhook.allowed-sources` 時可直接測試退款對帳；production 設定 secret 後，退款 callback 必須帶 `X-ByteBites-Webhook-Timestamp` 與 `X-ByteBites-Webhook-Signature`，Java 會驗證 5 分鐘時間窗與 HMAC-SHA256。輪替 secret 時可同時設定 `bytebites.refund.webhook.previous-secret`，讓舊簽章在 provider 切換期間仍可通過。若設定 `bytebites.refund.webhook.allowed-sources`，Java 會用 direct remote address 或受信任 proxy 的 `bytebites.refund.webhook.source-header` 檢查來源；proxy 必須先命中 `bytebites.refund.webhook.trusted-proxies` 才會信任 forwarded source。

- **Refund SLA visibility**
  商家後台會聚合 FAILED refund 與超過門檻仍在 PROCESSING 的 refund，並提供 operations digest 區分未升級、已升級、失敗與逾時項目；商家可將摘要送到綁定 LINE，也可執行 scheduler-ready due dispatch policy，Java 會以 cooldown、lastSentAt、nextEligibleAt 判斷是否該推播並記錄 dispatch audit，或標記已升級處理、留下備註與 audit event，讓退款 reconciliation 不只安全，也能被營運追蹤。

- **Private memory as AI moat**
  私人偏好不是 prompt 暫存，而是 Java 持久化資料；AI 讀取後用 deterministic validator 避開使用者標記「不再推薦」的店。

- **Private offers without public coupon leakage**
  AI 私密 offer 有獨立 Java table、trigger reason、有效期限與 per-user/per-shop 重複防護；前端只在符合條件的 AI 推薦卡顯示，不做公開優惠券入口。

- **Parking as product differentiation**  
  ByteBites 把用餐流程延伸到出發前，讓停車提醒成為「推薦網站」之外的記憶點。

- **Presentation-ready deployment**  
  Web、Java、AI 可透過公開 HTTPS demo URL 展示，並透過 health endpoint 驗證；ngrok 保留為本機臨時 tunnel，Nginx template 與 Docker Compose public-proxy overlay 則定義穩定公開網域的 reverse-proxy、LINE callback/webhook 與 refund source allowlist 邊界。

## Case Studies / 工程案例

完整演進總覽：  
[ByteBites Project Journey — 從後端基礎到 AI 用餐營運平台](docs/project-journey.md)

1. [AI Agent 真實串流 — 三層 debug 走完](docs/case-studies/01-sse-streaming-debug.md)  
   Fake streaming, function-call history contamination, context compression, and model latency measurement.

2. [ABSA Pipeline — 從模板到 LLM, F1 0.955](docs/case-studies/02-absa-pipeline.md)  
   Aspect-level sentiment extraction, evidence verification, gold set design, and quality measurement.

3. [Model 選擇不是「越貴越好」](docs/case-studies/03-model-ablation.md)  
   Task-specific model ablation across latency, quality, routing reliability, and cost.

4. [Taxonomy 從 0 到 production](docs/case-studies/04-taxonomy-migration.md)  
   V15-V19 Flyway migrations, third-party validation anchors, and JSON-vs-normalized ABSA trade-offs.

5. [推薦卡 UX — 從暴露 ABSA 到正面 framing](docs/case-studies/05-recommendation-ux.md)  
   Why accurate data can still be wrong for the current user context.

6. [資料爬蟲與覆蓋率 — 從 demo seed 到 600 家可用店](docs/case-studies/06-data-crawler-coverage.md)  
   Google Maps crawling, review extraction repair, media coverage, query cleanup, and audit reports.

7. [Web / LINE 訂位同步 — 從兩套身份到同一個交易狀態](docs/case-studies/07-web-line-booking-sync.md)  
   Identity binding, booking ownership, payment/cancel notifications, and contract tests.

8. [停車提醒與車位預約 demo — 把用餐流程延伸到出發前](docs/case-studies/08-parking-reminder-demo.md)  
   Parking preference, scheduled reminders, Taipei parking data, and responsible demo reservation design.

9. [從代碼體檢到 Spring Boot 3 — 先把地基補好](docs/case-studies/09-modernization-security.md)  
   Security review, framework modernization, configuration cleanup, and why foundation work came before AI features.

10. [AI 對話狀態 — 從單輪問答到可完成任務的 Agent](docs/case-studies/10-ai-dialogue-state.md)  
    Recommendation context, ordinal follow-ups, booking drafts, clarification policy, and cancellation safety.

11. [公開 Demo 部署 — 最後一哩不是上線，是可被同學打開](docs/case-studies/11-demo-deployment.md)  
    ngrok deployment, Nginx stable routing boundary, LINE Login callback, proxy cookie paths, Docker Compose naming, and public health checks.

12. [Premium UI 不是變成 inline clone — 找回 ByteBites 的品牌定位](docs/case-studies/12-premium-ui-positioning.md)  
    Typography, product copy, visual identity, and the trade-off between premium aesthetics and differentiation.

13. [AI Concierge 品質硬化 — 從會回答到可靠接待](docs/case-studies/13-ai-concierge-quality-hardening.md)
    Dining-intent routing, vague-need clarification, cuisine/district constraints, context reranking, and customer-service tone hardening.

14. [Portfolio Verification — 從很多亮點到可審查作品](docs/case-studies/14-portfolio-verification.md)
    Single verification command, CI matrix, data-quality gate, evidence map, and deeper booking Modules for reviewer trust.

## 專案結構 / Project Structure

```text
ai-enhanced-local-services/
├── backend-java/          # Spring Boot, auth, shop, booking, payment, parking APIs
├── ai-service-python/     # FastAPI, Gemini agent, LINE bot, semantic search, ABSA
├── web/                   # Next.js Web app, discovery, AI chat, booking UI
├── etl-pipeline/          # crawler loaders, Qdrant sync, taxonomy audit tools
├── tools/                 # scraper utilities
├── deploy/                # Prometheus / Grafana support and Nginx reverse-proxy overlay
└── docs/                  # case studies, audit reports, taxonomy specs
```

## 本機啟動 / Local Development

```bash
# 1. Start infra
docker compose up -d

# 2. Backend
cd backend-java
set -a; source .env; set +a
mvn spring-boot:run

# 3. AI service
cd ../ai-service-python
set -a; source .env; set +a
uv run uvicorn app.main:app --reload --port 8000

# 4. Frontend
cd ../web
npm run dev
```

Open:

- Web: `http://localhost:3000`
- Java backend: `http://localhost:8081`
- AI service: `http://localhost:8000`
- RabbitMQ: `http://localhost:15672`
- Qdrant: `http://localhost:6333`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

## 驗證 / Validation

```bash
cd ai-service-python
uv run pytest

cd ../backend-java
TAPPAY_PARTNER_KEY=test TAPPAY_MERCHANT_CREDITCARD=test mvn test

cd ..
scripts/verify-portfolio.sh
```

## AI 協作方式 / Built With AI as a Force Multiplier

Claude and Codex were used for hypothesis generation, code audit, implementation support, and debugging. The project deliberately records not only final features, but also the engineering choices behind them: when an AI suggestion was accepted, when it was challenged, how it was measured, and what trade-off was shipped.

Claude 與 Codex 參與了假設生成、代碼審查、樣板實作與 debug，但最終判斷仍由工程驗證決定。這份專案刻意保留 case studies，是為了說清楚：AI 工具能加速，但產品責任、資料驗證、trade-off 與最後使用者體驗仍由工程師負責。

## Contact

- GitHub: [@kevinlin000](https://github.com/kevinlin000)
