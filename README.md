# ByteBites — AI 用餐營運平台

ByteBites 不是單純的餐廳推薦或聊天機器人。它把「找餐廳」往後延伸到訂位、付款狀態、對話式改單、臨場救場、LINE 通知、商家後台、退款營運與資料品質驗證。

核心設計原則：

```text
AI 負責理解與協調流程。
Java 負責訂位、付款、救場、退款等核心狀態。
```

這份專案以台灣用餐場景為主：LINE Login / Messaging API、台北店家資料、捷運與行政區、TapPay demo 訂金流程、候補通知、停車提醒，以及商家端營運處理。

英文版：[README.en.md](README.en.md)

## 專案定位

多數餐廳產品停在 discovery：使用者看完餐廳資訊後，後面的訂位、付款、提醒、臨時狀況與交通安排都交回給使用者。ByteBites 的目標是讓 AI 進入完整用餐流程：

```text
自然語言需求
  -> 餐廳檢索與推薦
  -> 結構化推薦卡
  -> 訂位與 demo 訂金付款
  -> LINE / Web 狀態同步
  -> 對話式改單
  -> 臨場救場與商家替代時段提案
  -> 補款 / 退款 / 營運摘要
  -> 私人偏好記憶與私密 offer
```

這個專案的展示重點不是「模型會回答」，而是模型只能協調流程；真正會影響訂位、付款與退款的狀態，都由 Java 後端持久化、驗證與測試保護。

## 審查入口

以下文件適合快速理解系統設計、資料證據、部署邊界與工程案例。

- [專案演進總覽](docs/project-journey.md)
- [架構總覽](docs/architecture-overview.md)
- [訂位營運 ER Model](docs/er-model-booking-operations.md)（含 dbdiagram DBML source）
- [效能與查詢證據](docs/performance-query-evidence.md)
- [資料覆蓋率報告](docs/data-coverage-report.md)
- [Nginx 公開部署邊界](docs/deployment-nginx.md)
- [工程案例索引](docs/case-studies/README.md)

## 核心能力

- **AI 用餐助理**：理解模糊需求、保留推薦上下文、支援「第 2 家」「明晚 7 點 4 人」這類 follow-up，資訊不足時會追問。
- **餐廳探索**：依料理、行政區、捷運、評分、價位、資料品質與 AI metadata 篩選排序。
- **結構化推薦卡**：推薦文案與 UI 卡片共用 `recommended_shop_ids`，降低模型文字與產品狀態分裂的風險。
- **訂位與付款狀態**：建立訂位、保留座位、demo 訂金付款、取消與 LINE 通知都由 Java contract 保護。
- **對話式改單**：使用者可對 AI 說「改成明晚 8 點，同樣 4 位」，但真正改單仍由 Java 驗證座位、身份與訂金政策。
- **臨場救場**：顧客說「我塞車會晚到 20 分鐘」時，系統會從最近有效訂位建立 incident；商家可提出替代時段，顧客可在 Web 或 LINE 接受 / 拒絕。
- **退款與補款營運**：已付款訂位若改單產生差額，Java 會建立 TOP_UP 或 REFUND adjustment；退款 reconciliation 支援 event key 去重、audit trail、HMAC signature、secret rotation、source allowlist、SLA visibility 與 escalation。
- **私人偏好記憶**：用餐後可記錄「太吵」「不再推薦」等私人標籤，下次 AI 推薦會用 deterministic validator 避開。
- **AI 私密配對優惠**：不做公開優惠券頁；當使用者明確想省錢或離峰用餐時，AI 透過 Java 建立只對本人可見的限時 offer。
- **LINE 雙整合**：LINE Login 負責 Web 身份；Messaging API 負責聊天、Flex cards、通知與提醒。
- **資料品質層**：Google Places / Maps crawler、Mongo review sync、media manifest、ABSA、taxonomy audit、Qdrant payload sync、legacy seed cleanup。

## 系統快照

| 區塊 | 技術與責任 |
|---|---|
| Frontend | Next.js，餐廳探索、AI chat、我的訂位、收藏、通知、商家後台 |
| Backend | Spring Boot 3.2 / Java 17，auth、shop、booking、payment、incident、refund、parking APIs |
| AI service | FastAPI，Gemini agent、語意搜尋、LINE bot、Flex cards、private memory / offers |
| Data / ETL | Python ETL，crawler、review sync、taxonomy、ABSA、Qdrant payload |
| Storage | MySQL / Flyway、Redis、RabbitMQ、Qdrant、Mongo-backed reviews |
| LINE | LINE Login 與 Messaging API 分離整合 |
| Deployment | 本機 ngrok demo、Nginx reverse-proxy blueprint、Docker Compose public-proxy overlay |
| Observability | health endpoints、Prometheus / Grafana compose support |
| Verification | Java / Python / Web tests、Portfolio CI、release readiness、clean MySQL migration smoke |

## 架構

```text
Browser / LINE
  |
  v
Next.js Web
  |-- 餐廳探索、AI chat、訂位與商家後台
  |
  +--> Spring Boot Java
  |      |-- auth / shop / booking / payment / incident / refund / parking
  |      |-- MySQL / Flyway / Redis / RabbitMQ
  |      |-- LINE identity and notification contracts
  |
  +--> FastAPI AI service
         |-- Gemini agent and dialogue policy
         |-- Qdrant semantic search
         |-- LINE Messaging webhook and Flex cards

ETL / data quality
  |-- Google Places / Maps crawler
  |-- Mongo review sync
  |-- ABSA pipeline
  |-- taxonomy audit and Qdrant payload sync
```

完整架構說明見 [docs/architecture-overview.md](docs/architecture-overview.md)。

## 展示路線

1. 首頁：展示 ByteBites 的定位「會推薦，也會安排」。
2. Web AI：輸入 `大安區 7 人 適合聊天` 或 `中山區 商務宴請 台菜 安靜包廂`。
3. 推薦卡：展示 AI 理由、照片、招牌菜、評論亮點與詳情頁。
4. 訂位：選日期、人數、是否開車，完成 demo 訂金付款。
5. 改單：對 AI 說 `改成明晚 8 點，同樣 4 位`。
6. 救場：對 AI 說 `我塞車會晚到 20 分鐘`，展示 Java incident、LINE rescue card、商家替代時段提案與顧客接受 / 拒絕。
7. 退款營運：展示商家後台 refund operations digest、FAILED / stale refund SLA、升級處理狀態。
8. 私人記憶：記錄 `太吵` / `不再推薦`，再展示 AI 推薦會避開。
9. 私密 offer：輸入 `想找有優惠、比較省錢的日式料理`，展示只對本人可見的 AI offer。
10. 驗證：展示 CI、release readiness、clean migration smoke。

## 驗證

單一作品驗證入口：

```bash
scripts/verify-portfolio.sh
```

主要檢查：

| 區塊 | 指令 | 目的 |
|---|---|---|
| Backend Java | `mvn test` | 訂位、付款、LINE、incident、refund、parking contract tests |
| AI service | `uv run --no-sync pytest tests -q` | agent conversation、LINE flow、guardrail、internal notification contracts |
| ETL pipeline | `uv run --no-sync pytest tests -q` | taxonomy、normalizer、audit sync、data-quality tests |
| Data quality gate | `python3 scripts/verify-data-quality.py` | 覆蓋率、eval manifests、taxonomy、case studies、Markdown links |
| Nginx contract | `python3 scripts/verify-nginx-template.py` | public reverse-proxy routes、LINE URLs、proxy headers |
| Clean migration smoke contract | `scripts/smoke-clean-mysql-migrations.sh --dry-run` | live clean-schema smoke runner 的離線合約 |
| Release boundary | `python3 scripts/verify-release-boundary.py` | release handoff、verification ladder、production-gap framing |
| Query evidence | `python3 scripts/verify-performance-query-evidence.py` | hot query paths、indexes、code anchors |
| Web | `pnpm test` / `pnpm build:ci` | UI contract tests 與 production build |

CI 位於 `.github/workflows/portfolio-ci.yml`。乾淨 MySQL schema 啟動驗證位於 `.github/workflows/clean-mysql-migration-smoke.yml`，採手動觸發，因為它會啟 MySQL、Redis、RabbitMQ 與 Java process。

## 本機啟動

```bash
# 1. 啟動基礎服務
docker compose up -d

# 2. Java backend
cd backend-java
set -a; source .env; set +a
mvn spring-boot:run

# 3. AI service
cd ../ai-service-python
set -a; source .env; set +a
uv run uvicorn app.main:app --reload --port 8000

# 4. Web
cd ../web
npm run dev
```

常用入口：

- Web: `http://localhost:3000`
- Java backend: `http://localhost:8081`
- AI service: `http://localhost:8000`
- RabbitMQ: `http://localhost:15672`
- Qdrant: `http://localhost:6333`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

正式 demo 前可執行：

```bash
scripts/release-readiness.sh --offline
scripts/smoke-clean-mysql-migrations.sh --timeout 180
```

## 工程案例

完整演進總覽：
[ByteBites Project Journey — 從後端基礎到 AI 用餐營運平台](docs/project-journey.md)

1. [AI Agent 真實串流 — 三層 debug 走完](docs/case-studies/01-sse-streaming-debug.md)
2. [ABSA Pipeline — 從模板到 LLM, F1 0.955](docs/case-studies/02-absa-pipeline.md)
3. [Model 選擇不是「越貴越好」](docs/case-studies/03-model-ablation.md)
4. [Taxonomy 從 0 到 production](docs/case-studies/04-taxonomy-migration.md)
5. [推薦卡 UX — 從暴露 ABSA 到正面 framing](docs/case-studies/05-recommendation-ux.md)
6. [資料爬蟲與覆蓋率 — 從 demo seed 到 600 家可用店](docs/case-studies/06-data-crawler-coverage.md)
7. [Web / LINE 訂位同步 — 從兩套身份到同一個交易狀態](docs/case-studies/07-web-line-booking-sync.md)
8. [停車提醒與車位預約 demo — 把用餐流程延伸到出發前](docs/case-studies/08-parking-reminder-demo.md)
9. [從代碼體檢到 Spring Boot 3 — 先把地基補好](docs/case-studies/09-modernization-security.md)
10. [AI 對話狀態 — 從單輪問答到可完成任務的 Agent](docs/case-studies/10-ai-dialogue-state.md)
11. [公開 Demo 部署 — 最後一哩不是上線，是可被同學打開](docs/case-studies/11-demo-deployment.md)
12. [Premium UI 不是變成 inline clone — 找回 ByteBites 的品牌定位](docs/case-studies/12-premium-ui-positioning.md)
13. [AI Concierge 品質硬化 — 從會回答到可靠接待](docs/case-studies/13-ai-concierge-quality-hardening.md)
14. [Portfolio Verification — 從很多亮點到可審查作品](docs/case-studies/14-portfolio-verification.md)

## 專案結構

```text
ai-enhanced-local-services/
├── backend-java/          # Spring Boot, auth, shop, booking, payment, incident, refund APIs
├── ai-service-python/     # FastAPI, Gemini agent, LINE bot, semantic search, ABSA
├── web/                   # Next.js Web app, discovery, AI chat, booking UI
├── etl-pipeline/          # crawler loaders, Qdrant sync, taxonomy audit tools
├── tools/                 # scraper utilities
├── deploy/                # Prometheus / Grafana support and Nginx reverse-proxy overlay
└── docs/                  # architecture, data reports, deployment notes, case studies
```

## AI 協作說明

Claude 與 Codex 參與了假設生成、代碼審查、樣板實作與 debug，但最終判斷仍由工程驗證決定。這份專案刻意保留 case studies，是為了說清楚：AI 工具能加速，但產品責任、資料驗證、trade-off 與最後使用者體驗仍由工程師負責。

## 聯絡

- GitHub: [@kevinlin000](https://github.com/kevinlin000)
