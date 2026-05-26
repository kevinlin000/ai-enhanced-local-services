# ByteBites · 台灣在地 AI 點評平台

> Java 後端 + Python AI 服務 + Next.js 前端的三服務整合作品，台北場景。

## 為什麼這個專案

台灣在地店家發現分散在 Google Maps、社群、論壇之間。本專案做一個整合「在地店家發現、語意搜尋、AI 推薦」的平台，並以此展示後端工程實踐與 AI 應用整合的雙能力。

## 三大差異化

- **Java + Python 雙服務**：Java 處理核心業務（用戶、店家、訂位、Hot Seat 限時搶位），Python 負責 AI（RAG、Agent、Eval）
- **LINE Login + 台北捷運 GEO**：對齊台灣使用情境，非 Google OAuth、非縣市行政區
- **Strangler Fig 漸進遷移**：MyBatis-Plus 與 Spring Data JPA 並存，Hot Seat 搶位路徑保留 MyBatis 因 AOP 整合穩定，是有意的工程取捨

## 技術棧

### 後端 (Java)
| 類別 | 技術 |
|------|------|
| 語言 / 框架 | Java 17 · Spring Boot 3.2 |
| 安全 | Spring Security · OAuth 2.0 (LINE) · JWT |
| ORM | Spring Data JPA · MyBatis-Plus（並存） |
| Migration | Flyway |
| 快取 | Caffeine (L1) · Redis 7 (L2) · Bloom Filter (Redisson) |
| 鎖 | Redisson 讀寫鎖 |
| MQ | RabbitMQ 3.13 · Outbox 模式 · DLQ |
| Database | MySQL 8 |
| 可觀測性 | Micrometer · Prometheus |

### AI 服務 (Python)
| 類別 | 技術 |
|------|------|
| 語言 / 框架 | Python 3.12 · FastAPI · uv |
| LLM | Gemini 3.1 Flash Lite · Function Calling |
| Embedding | Gemini Embedding 001 (768d) |
| 向量庫 | Qdrant 1.13 |
| 監控 | prometheus-client · token tracking |
| 評估 | 自寫 hit@k · 10 案例 dataset |
| 安全 | Input injection guardrail · Output filter |

### 前端 (Web)
| 類別 | 技術 |
|------|------|
| 框架 | Next.js 15 · React 19 · TypeScript |
| 樣式 | Tailwind v4 · shadcn-ui |
| 字型 | Geist Sans · Geist Mono · Noto Sans TC |
| 圖示 | Lucide |

## 目前進度

- Spring Boot 3.2.5 + Java 17 + Jakarta 遷移完成，底座已升到現代 Spring 生態。
- Flyway 接管 schema，完成 V1-V7 migration、12 個在地分類、25 家台北店家與捷運站種子資料。
- LINE Login OAuth 2.0、Spring Security、JWT 驗證鏈打通，登入流程已對齊實際台灣使用情境。
- JPA 遷移已切完 User、ShopType、Shop、Review、Voucher 系列，保留 Hot Seat 高風險搶位路徑的漸進式切換。
- Python AI 服務已完成 Qdrant ingest、語意搜尋、RAG 推薦、Function Calling Agent、輕量 eval、guardrail、Prometheus。
- Next.js 前端已完成商家瀏覽、AI 搜尋頁、AI Concierge 浮窗、首頁視覺 polish 與手機版調整。

## 進階工程能力

### 後端層

| 能力 | 實作 | 設計取捨 |
|------|------|----------|
| 多層快取 | Caffeine + Redis + Bloom + 空值快取 | 避免穿透、擊穿、雪崩 |
| 限流 | Lua 令牌桶 + 註解式 `@RateLimit` + AOP | 原子性扣減；支援多維度 |
| 冪等 | Redis SETNX + 註解式 `@Idempotent` + SpEL key | TTL 過期自動釋放 |
| 讀寫鎖 | Redisson 註解式 `@DistributedLock(type=READ/WRITE)` | 讀並行寫互斥 |
| 可靠消息 | RabbitMQ + Outbox 模式 + DLQ | DB transaction + 背景 publisher 保證一致性 |
| 可觀測性 | Actuator + Prometheus + 業務 counter | seckill / ratelimit / outbox metric |

### AI 層

| 能力 | 實作 | 重點 |
|------|------|------|
| 語意搜尋 | Gemini Embedding + Qdrant cosine | task_type 區分 query/document |
| RAG | Embedding + 檢索 + LLM 生成 | tenacity retry on 429/503 |
| Agent | Function Calling (2 tools) | LLM 自動決定查 GEO 或語意檢索 |
| 評估 | hit@5 dataset (10 case) | baseline 80%、失敗案例有 root cause |
| Guardrail | Regex input filter + output blocklist | 中英文 injection pattern |
| Observability | Prometheus + token tracking | prompt / output token by model |

完整 commit 流水與「為什麼這樣做」見 [CHANGELOG.md](./CHANGELOG.md)。

## 已實作 API

### Java Backend (8081)

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/auth/line/login` | LINE OAuth 起點（302 到 LINE） |
| GET | `/api/auth/line/callback` | OAuth callback、回傳 JWT |
| GET | `/api/category/list` | 12 個在地分類 |
| GET | `/api/category/{slug}/shops` | 分類下店家（分頁） |
| GET | `/api/category/{slug}/shops/popular` | 分類熱門 top 5 |
| GET | `/api/shop/{id}` | 單店詳情（多層快取 + 讀寫鎖） |
| GET | `/api/mrt/stations` | 8 個捷運站 |
| GET | `/api/mrt/stations/nearby` | GEO 半徑搜尋 |
| GET | `/api/mrt/{station}/popular-shops` | 捷運站附近熱門 |
| GET | `/api/shop/nearby-mrt/{station}` | 該站附近店家 |
| POST | `/voucher-order/seckill/{id}` | Hot Seat 限時搶位（限流 + 冪等） |
| POST | `/api/demo/mq-outbox` | Outbox demo |

### Python AI Service (8000)

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/health` | 健康檢查 |
| POST | `/api/ai/search` | 純向量檢索 top-k |
| POST | `/api/ai/recommend` | RAG 完整閉環 |
| POST | `/api/ai/agent` | Function Calling Agent |
| GET | `/metrics` | Prometheus metrics |

## 本地啟動

### 1. 啟動依賴服務

```bash
cd deploy
docker compose up -d mysql redis rabbitmq qdrant
```

### 2. Java Backend (port 8081)

```bash
cd backend-java
cp ../.env.example ../.env  # 填入 LINE_CHANNEL_ID / SECRET / JWT_SECRET
set -a; source ../.env; set +a
mvn spring-boot:run
```

首次啟動會跑 Flyway migration（V1-V7）。

### 3. Python AI Service (port 8000)

```bash
cd ai-service-python
cp .env.example .env  # 填入 GEMINI_API_KEY
uv sync
uv run uvicorn app.main:app --port 8000
```

一次性 ingest 25 家種子店家到 Qdrant：

```bash
uv run python -m app.ingest
```

### 4. 前端 (port 3000)

```bash
cd web
pnpm install
pnpm dev
```

訪問 http://localhost:3000

## Gemini Quota 注意

Google 從 2025/12 大幅砍 free tier：
- gemini-2.5-flash / 2.5-flash-lite: **20 RPD**（過小、不堪用）
- gemini-3.1-flash-lite: **500 RPD**（推薦）

預設值已設為 `gemini-3.1-flash-lite`、不要改回 2.5 系列。

## 規劃路線

詳見 [docs/roadmap.md](./docs/roadmap.md)。
