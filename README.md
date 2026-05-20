# 台灣在地點評平台 + AI 應用整合作品（v1.0 開發中）

把原版黑馬點評改造成台灣在地化店家點評平台，並逐步接上 AI 搜尋、評論摘要與平台助手能力。

## 為什麼這個專案

這個專案想解決「台灣在地店家發現與評論資訊分散」問題，先從台北店家、捷運站與分類瀏覽做出可 demo 的產品骨架。  
技術上，它是以 Java 後端為主體、AI 服務為延伸的整合作品，重點放在 Spring Boot 3、Spring Security、Redis、Flyway 與可持續演進的資料模型。  
和原版黑馬點評相比，這版不做中國場景複刻，而是改成 LINE Login、台北捷運 GEO、台灣店家分類與台灣種子資料。

## 技術棧

| 類別 | 技術 |
| --- | --- |
| Java | Java 17 |
| Backend | Spring Boot 3.2 |
| Security | Spring Security + JWT |
| ORM | MyBatis-Plus（TODO: 將遷移到 JPA） |
| Migration | Flyway |
| Cache / GEO | Redis 7 |
| Distributed Lock | Redisson |
| Database | MySQL 8 |

## 目前進度（Stage 1 完成）

- Spring Boot 3.2.5 + Java 17 + Jakarta 遷移完成，先把專案升到現代 Spring 生態，後續功能開發不用背舊包袱。
- Repo 結構、`.gitignore`、內部文件邊界與初始體檢完成，讓專案能持續演進，不會一開始就把工作區搞亂。
- Flyway 接管 schema，並完成台灣化 migration、12 個在地分類、25 家台北店家種子資料，資料層已脫離原版中國場景。
- LINE Login OAuth 2.0、Spring Security、JWT 驗證鏈打通，登入入口已從簡訊登入轉向真實 OAuth 流程。
- 台北捷運 GEO 已接上 Redis，能查捷運站、附近捷運站與捷運站周邊店家，完成 Stage 1 的地理能力基底。
- 分類 API 與店家台灣欄位映射完成，前端已可直接用 slug 查分類店家、熱門店家與完整台灣化店家資料。

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

## 本地啟動

```bash
cp .env.example .env
# 先準備 MySQL 8 與 Redis 7，並確認 .env 內連線資訊正確
cd backend-java
set -a; source ../.env; set +a
mvn spring-boot:run
```

啟動後可先訪問 `http://localhost:8081/api/category/list` 或 `http://localhost:8081/api/mrt/stations`。

## Roadmap

後續規劃見 [docs/roadmap.md](docs/roadmap.md)。
