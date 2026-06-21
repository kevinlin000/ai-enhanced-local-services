# ByteBites — AI 用餐營運平台

[English version](README.en.md)

ByteBites 是一個以台灣用餐場景為核心的 AI 輔助用餐營運系統。它不只回答「哪家餐廳適合我」，而是把推薦、訂位、付款狀態、對話式改單、臨場救場、LINE 通知、商家處理與退款營運串成同一個可驗證流程。

核心原則很簡單：

```text
AI 負責理解需求與協調流程。
Java 後端負責訂位、付款、臨場事件、退款等業務狀態。
```

這個專案的重點不是展示模型文字能力，而是展示一個 AI 應用如何在真實交易流程中維持狀態邊界、資料品質與可驗證性。

## 快速判讀

| 面向 | ByteBites 的做法 |
|---|---|
| 產品定位 | AI 用餐營運平台，不是單輪餐廳推薦聊天機器人。 |
| 狀態邊界 | Web / LINE / AI 都只是入口；Java 是訂位、付款、臨場事件與退款的權威資料來源。 |
| AI 可靠性 | 模型負責理解語意；訂位、改單、臨場救場都走可重現的後端合約。 |
| 資料基礎 | 600 家台北 active shops，含 media coverage、review sync、ABSA、taxonomy audit、Qdrant payload sync。 |
| 驗證方式 | `scripts/verify-portfolio.sh`、Portfolio CI、release readiness、clean MySQL migration smoke。 |
| 設計證據 | 架構文件、dbdiagram DBML ER Model、hot query / index evidence、14 篇工程案例。 |

## 審查路線

| 時間 | 建議閱讀 |
|---|---|
| 30 秒 | 本 README 的「快速判讀」與「核心流程」。 |
| 3 分鐘 | [架構總覽](docs/architecture-overview.md)、[訂位營運 ER Model](docs/er-model-booking-operations.md)、[資料覆蓋率報告](docs/data-coverage-report.md)。 |
| 10 分鐘 | [效能與查詢證據](docs/performance-query-evidence.md)、[Nginx 公開部署邊界](docs/deployment-nginx.md)、[工程案例索引](docs/case-studies/README.md)。 |
| 實際驗證 | 執行 `scripts/verify-portfolio.sh`，或查看 GitHub Actions 的 Portfolio CI。 |

## 核心流程

```text
自然語言需求
  -> 餐廳檢索與推薦
  -> 結構化推薦卡
  -> 訂位與 demo 訂金付款
  -> Web / LINE 狀態同步
  -> 對話式改單
  -> 臨場救場與商家替代時段提案
  -> 補款 / 退款 / 營運摘要
  -> 私人偏好記憶與私密 offer
```

最能代表系統邊界的流程是臨場救場：

1. 使用者對 AI 說：`我塞車會晚到 20 分鐘`。
2. AI 不自行猜測訂位，而是從 Java 查詢最近有效訂位。
3. Java 建立 `tb_booking_incident`，並透過 LINE / Web 顯示最新臨場事件。
4. 商家後台提出替代時段。
5. 顧客可從 Web 或 LINE 接受 / 拒絕。
6. Java 驗證座位、身份與訂金政策後才改單；若涉及差額，建立 TOP_UP / REFUND adjustment。

## 工程重點

### Java 擁有交易狀態

訂位、付款、改單、臨場事件、替代時段提案、補款、退款與通知狀態都由 Spring Boot 後端維護。AI service 不直接改交易狀態，前端也不保存權威狀態。

相關證據：

- [訂位營運 ER Model](docs/er-model-booking-operations.md)，含 dbdiagram DBML source 與 1NF / 2NF / 3NF 設計說明。
- [Web / LINE 訂位同步案例](docs/case-studies/07-web-line-booking-sync.md)
- [Portfolio Verification 案例](docs/case-studies/14-portfolio-verification.md)

### AI 負責協調，後端負責決策

AI 層處理語意理解、推薦整理、對話上下文與 LINE Flex cards；但涉及訂位、改單、臨場救場和退款的操作，都回到 Java 合約。這讓 AI 應用不是只靠 prompt，而是由狀態機、資料約束與測試保護。

相關證據：

- [AI 對話狀態案例](docs/case-studies/10-ai-dialogue-state.md)
- [AI Concierge 品質硬化案例](docs/case-studies/13-ai-concierge-quality-hardening.md)
- `ai-service-python/evals/`

### 先有資料品質，再談推薦品質

推薦品質不是只靠模型。ByteBites 將店家資料、照片、評論、taxonomy、ABSA 與 Qdrant payload 都納入可驗證資料管線。

目前資料證據：

| 指標 | 狀態 |
|---|---|
| Active Taipei shops | 600 |
| Cover image / media manifest | 100% |
| AI summary coverage | 100% |
| ABSA / Mongo review coverage | 99%+ |
| Price signal coverage | 85%+ |

完整報告：[資料覆蓋率報告](docs/data-coverage-report.md)

### 可被審查的交付路徑

作品不是只在本機「剛好能跑」。Repo 內有單一 portfolio gate、GitHub Actions、Nginx route contract、clean-schema migration smoke 與 release readiness。

```bash
scripts/verify-portfolio.sh
scripts/release-readiness.sh --offline
```

## 系統架構

```text
Browser / LINE
  |
  v
Next.js Web
  |-- 餐廳探索、AI chat、我的訂位、商家後台
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

完整說明：[架構總覽](docs/architecture-overview.md)

## 技術棧

| 區塊 | 技術與責任 |
|---|---|
| Frontend | Next.js，餐廳探索、AI chat、我的訂位、收藏、通知、商家後台 |
| Backend | Spring Boot 3.2 / Java 17，auth、shop、booking、payment、incident、refund、parking APIs |
| AI service | FastAPI，Gemini agent、語意搜尋、LINE bot、Flex cards、private memory / offers |
| Data / ETL | Python ETL，crawler、review sync、taxonomy、ABSA、Qdrant payload |
| Storage | MySQL / Flyway、Redis、RabbitMQ、Qdrant、Mongo-backed reviews |
| LINE | LINE Login 與 Messaging API 分離整合 |
| Deployment | Nginx reverse-proxy blueprint、Docker Compose public-proxy overlay、本機 ngrok demo |
| Verification | Java / Python / Web tests、Portfolio CI、release readiness、clean MySQL migration smoke |

## 展示路線

1. Web AI：輸入 `大安區 7 人 適合聊天` 或 `中山區 商務宴請 台菜 安靜包廂`。
2. 推薦卡：展示 AI 理由、照片、招牌菜、評論亮點與詳情頁。
3. 訂位：選日期、人數、是否開車，完成 demo 訂金付款。
4. 改單：對 AI 說 `改成明晚 8 點，同樣 4 位`。
5. 救場：對 AI 說 `我塞車會晚到 20 分鐘`，展示 Java incident、LINE rescue card、商家替代時段提案與顧客接受 / 拒絕。
6. 退款營運：展示商家後台 refund operations digest、FAILED / stale refund SLA、升級處理狀態。
7. 私人記憶：記錄 `太吵` / `不再推薦`，再展示 AI 推薦避開該店。
8. 驗證：展示 Portfolio CI、release readiness、clean migration smoke。

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

## 精選工程案例

- [AI Agent 真實串流 — 從假串流到可量測 TTFT](docs/case-studies/01-sse-streaming-debug.md)
- [ABSA 評論分析 Pipeline — 可溯源評論智能](docs/case-studies/02-absa-pipeline.md)
- [資料爬蟲與覆蓋率 — 600 家可用店的資料基礎](docs/case-studies/06-data-crawler-coverage.md)
- [Web / LINE 訂位同步 — 從兩套身份到同一個交易狀態](docs/case-studies/07-web-line-booking-sync.md)
- [AI 對話狀態 — 從單輪問答到可完成任務的 Agent](docs/case-studies/10-ai-dialogue-state.md)
- [公開展示部署 — 從本機可跑到外部可開](docs/case-studies/11-demo-deployment.md)

完整列表：[工程案例索引](docs/case-studies/README.md)

## 本機啟動

```bash
docker compose up -d

cd backend-java
set -a; source .env; set +a
mvn spring-boot:run

cd ../ai-service-python
set -a; source .env; set +a
uv run uvicorn app.main:app --reload --port 8000

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

正式 demo 前：

```bash
scripts/release-readiness.sh --offline
scripts/smoke-clean-mysql-migrations.sh --timeout 180
```

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

## 上線邊界

這是已具備作品展示品質、並由合約測試保護的專案，不宣稱已完成正式 SaaS 上線。真正上線仍需要受管祕密、雲端資料庫與備份還原策略、觀測儀表板、真實 PSP 退款供應商整合、商家通知偏好與營運手冊。

## 聯絡

- GitHub: [@kevinlin000](https://github.com/kevinlin000)
