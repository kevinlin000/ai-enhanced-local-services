# 台灣在地點評平台 + AI 應用整合作品（v1.0 開發中）

以台灣使用者為主要服務對象的店家點評與發現平台，整合 LINE Login、台北捷運 GEO 搜尋、在地店家分類，並逐步引入 AI 搜尋、評論摘要與平台助手能力。

## 為什麼這個專案

台灣的店家發現與評論資訊分散在不同平台，使用者要在 Google Maps、社群、論壇之間切換才能做選擇。本專案的目標是把「在地店家發現、評論瀏覽、AI 智能搜尋」整合在同一個介面。

技術定位上，這是一個**以 Java 後端為核心、Python AI 服務為延伸**的整合作品，重點在 Spring Boot 3 工程實踐、Redis 多元應用、與 AI 應用架構的雙服務拆分。

## 差異化定位

本專案刻意做出以下設計選擇，呈現對「為什麼這樣做」的取捨思考：

- **LINE Login** 作為主要登入方式（非簡訊、非密碼）
- **台北捷運站 GEO** 作為地理搜尋的核心索引（非縣市行政區）
- **Java + Python 雙服務架構**，AI 服務獨立部署（非 Java 內嵌 LLM 框架）
- **Spring Data JPA**（規劃中）作為主要 ORM（與作者另一個作品的 MyBatis 形成對照）

## 技術棧

| 類別 | 技術 |
| --- | --- |
| Java | Java 17 |
| Backend | Spring Boot 3.2 |
| Security | Spring Security + JWT |
| ORM | MyBatis-Plus（TODO: 將遷移到 JPA） |
| Migration | Flyway |
| Cache / GEO | Redis 7 |
| Local Cache | Caffeine |
| Bloom Filter | Redisson |
| Distributed Lock | Redisson |
| MQ | RabbitMQ 3.13 |
| Database | MySQL 8 |

## 目前進度（Stage 1 完成）

- Spring Boot 3.2.5 + Java 17 + Jakarta 遷移完成，先把專案升到現代 Spring 生態，後續功能開發不用背舊包袱。
- Repo 結構、`.gitignore`、內部文件邊界與初始體檢完成，讓專案能持續演進，不會一開始就把工作區搞亂。
- Flyway 接管 schema，並完成台灣化 migration、12 個在地分類、25 家台北店家種子資料，資料層已具備在地 demo 所需的資料基底。
- LINE Login OAuth 2.0、Spring Security、JWT 驗證鏈打通，登入入口已從簡訊登入轉向真實 OAuth 流程。
- 台北捷運 GEO 已接上 Redis，能查捷運站、附近捷運站與捷運站周邊店家，完成 Stage 1 的地理能力基底。
- 分類 API 與店家台灣欄位映射完成，前端已可直接用 slug 查分類店家、熱門店家與完整台灣化店家資料。

## 進階工程能力（Stage 1.5）

在 Stage 1 完成台灣在地化基礎後，補上對應 Junior Java 面試常考的進階工程能力：

| 能力 | 實作 | 設計取捨 |
| --- | --- | --- |
| 多層快取 | Caffeine（L1） + Redis（L2） + Bloom Filter + 空值快取 | 避免穿透、擊穿、雪崩三大問題 |
| 限流 | Lua 令牌桶 + 註解式 `@RateLimit` + AOP | 原子性扣減；支援多維度 |
| 冪等 | Redis SETNX + 註解式 `@Idempotent` + SpEL key | TTL 過期自動釋放，避免持久污染 |
| 讀寫鎖 | Redisson 註解式 `@DistributedLock(type=READ/WRITE)` | 讀並行寫互斥 |
| 可靠消息 | RabbitMQ + Outbox 模式 + 死信佇列（DLQ） | DB transaction + 背景 publisher 保證一致性 |

完整 commit 流水與「為什麼這樣做」見 [CHANGELOG.md](./CHANGELOG.md)。

## 已實作 API

| 功能 | Endpoint | 說明 |
| --- | --- | --- |
| LINE Login | `GET /api/auth/line/login` | 導向 LINE OAuth 授權頁 |
| LINE Callback | `GET /api/auth/line/callback` | LINE 回調後交換 profile 並發 JWT |
| MRT Stations | `GET /api/mrt/stations` | 取得捷運站列表 |
| MRT Nearby | `GET /api/mrt/stations/nearby?lng=121.5&lat=25.0&radius=500` | 查半徑內捷運站 |
| Nearby Shops by MRT | `GET /api/shop/nearby-mrt/{station}` | 查指定捷運站附近店家 |
| Category List | `GET /api/category/list` | 取得 12 個 active 在地分類 |
| Category Shops | `GET /api/category/{slug}/shops?page=1&size=10` | 依 slug 分頁查分類店家 |
| Category Popular Shops | `GET /api/category/{slug}/shops/popular` | 查分類熱門店家 Top 5 |
| Shop Detail | `GET /api/shop/{id}` | 取得店家明細，含 `mrtStation`、`district`、`priceRange`、`businessHours` |
| MQ Publish Demo | `POST /api/demo/mq` | 直接發 MQ（教學用） |
| MQ Publish via Outbox | `POST /api/demo/mq-outbox` | 透過 outbox 發 MQ |

## 本地啟動

```bash
cp .env.example .env
# 先準備 MySQL 8 與 Redis 7，並確認 .env 內連線資訊正確
cd backend-java
set -a; source ../.env; set +a
mvn spring-boot:run
```

啟動後可先訪問 `http://localhost:8081/api/category/list` 或 `http://localhost:8081/api/mrt/stations`。

## 規劃路線

詳見 [docs/roadmap.md](./docs/roadmap.md)。
