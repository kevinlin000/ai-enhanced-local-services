# CLAUDE.md

> 這份檔案是給所有 AI 編碼工具（Claude Code、Codex 等）讀的脈絡與規範。
> 每次新 session 開始時請先讀完這份檔案。

---

## 1. 開發者背景

我是準備找 **Junior Java 工程師** 的求職者，目標 2026 下半年到 2027 上半年投履歷。同時我是 **輔大 AI 專班** 與 **成大資工所 AI 工程系統課**的修課學生，這個專案會同時當：

1. Junior Java 工程師面試主力作品
2. AI 應用工程師面試加分作品
3. 成大 AI 工程系統課期末專題（需高分）
4. 輔大 AI 專班期末

我已經完成另一個 Java 作品「菜籃日」（生鮮揪團電商，Spring Boot 2.7 + MyBatis + Vue 3 + Redisson + JMeter 壓測 + AWS 部署），所以這個專案要**刻意做出差異化**。

---

## 2. 專案目標

把原版「黑馬點評」（Redis 多數據結構教學專案）魔改成 **台灣在地化點評平台 + AI 應用整合作品**。原始碼基礎是：
- 原版黑馬點評（已敲完，本地端可運行）
- 黑馬點評 plus（高併發加強版，作為功能參考）
- 大麥 AI（Spring AI 應用，作為 AI 概念參考）

---

## 3. 整體架構（**不可變更**）

兩個獨立服務 + 一個前端：

- **Java 後端**：Spring Boot 3.x + Java 21 + Spring Data JPA + Hibernate + Spring Security + JWT + MySQL 8 + Redis 7 + Redisson + RabbitMQ
- **Python AI 服務**：FastAPI + LlamaIndex + Qdrant + LiteLLM + RAGAS + promptfoo
- **前端**：Vue 3 + Vite + Pinia + Element Plus

**通訊方式**：HTTP REST（不用 gRPC、不用 Kafka）。Java 是 source of truth，Python 透過 Java 內部 API 取得資料。

**設計原則**：兩個子系統各自能獨立成立——Java 側「就算把 AI 拿掉，還是合格的 Java 作品」；Python 側「就算 Java 不存在，這個 RAG/Agent 服務拿出去也是合格的 AI 作品」。

---

## 4. 技術選型（**不要建議我改**）

### Java 側

- ORM 用 **Spring Data JPA + Hibernate**（不要建議 MyBatis）
  - 理由：跟菜籃日的 MyBatis 區隔，展示我兩個 ORM 都會
- 安全用 **Spring Security**（不要手刻 JWT 攔截器）
  - 理由：業界硬指標
- 訊息隊列用 **RabbitMQ**（不要建議 Kafka）
  - 理由：場景是業務消息隊列，不是大數據流
- 快取用 **Caffeine + Redis + 空值快取 + 布隆過濾器**
- 鎖用 **Redisson**（含讀寫鎖、註解式鎖）

### Python 側

- LLM Orchestration 用 **LlamaIndex**（不要建議 LangChain）
  - 理由：RAG 抽象更乾淨
- 向量資料庫用 **Qdrant**（不要建議 pgvector、Pinecone）
- LLM Gateway 用 **LiteLLM**
- 評估用 **RAGAS + promptfoo**

---

## 5. 業務功能定案

### 從原版黑馬點評保留

1. 用戶登入（改成 **LINE Login + JWT**）
2. 商家瀏覽 + 多層快取
3. 優惠券秒殺 + 令牌桶限流 + 冪等
4. 附近商家 GEO（**台北捷運站定位**）
5. 達人探店 + 點讚排行
6. 好友關注
7. UV 統計 / 簽到

### 從黑馬點評 plus 抄 5 個進階

1. Spring Boot 3.x 升級
2. 多層快取（Caffeine + Redis + 空值 + 布隆）
3. 令牌前置授權 + 令牌桶限流
4. 分散式冪等註解
5. 讀寫鎖 + 註解式鎖

### 選做（時間允許）

- RabbitMQ + Outbox 模式 + DLQ
- Redisson 延遲隊列

### Python AI 三個核心場景

1. **「附近找店家」自然語言搜尋（RAG）**：用戶說「找個適合約會的安靜咖啡廳」→ embedding query → 向量檢索 → rerank → 結合 GEO → 回傳店家清單
2. **「店家評論智能摘要」**：撈評論 → LLM 摘要 → 整理成「優點/缺點/適合什麼人」
3. **「AI 客服 / 平台規則助手」**：RAG 檢索平台政策 → 回答 + Guardrail

### 台灣化改造

- LINE Login（取代簡訊）
- 台幣 + 繁中
- 台北捷運站 GEO
- 在地店家分類（牛肉麵、滷味、手搖飲、夜市小吃）

---

## 6. **絕對不做**的清單

> 以下事項不論你看到原版黑馬點評 plus 或大麥 AI 怎麼做，都不要在這個專案做。

| 不做的事 | 理由 |
|---|---|
| 分庫分表 | 資料量沒到、面試會被問「為什麼需要」答不出來 |
| Kafka | 場景不合、RabbitMQ 更合適 |
| 完整鏈路追蹤（SkyWalking） | 運維成本不合理 |
| 微服務拆得更細 | Java + Python 已是合理拆分 |
| K8s 部署 | EC2 + Docker Compose 已夠 |
| GraphQL / CQRS / Event Sourcing | 過度設計 |
| 大麥 AI 的運維助手功能 | 跟業務無關 |
| Spring AI / Java 串 LLM | AI 部分一律走 Python |
| 多語言 i18n | 跟「台灣在地化」主軸衝突 |

---

## 7. AI 工具協作規範

### 你（Claude Code / Codex）寫 code 時的鐵則

1. **先講設計再寫**：除非是純 boilerplate，否則先用幾句話講「我準備這樣寫，理由是 X」，等我確認後再寫
2. **逐個檔案改**：不要一次改 10 個檔案，一次 1-3 個就好，方便我跟讀
3. **每寫完一個 Service / 模組，主動問**：「這個設計有什麼權衡？我選擇 A 而不選 B 的理由是什麼？」——這是我準備面試 Q&A 的素材
4. **遇到原版黑馬點評的寫法你覺得不對**，**不要直接改**，先提出來讓我決定
5. **Spring Boot 2.7 寫法**（`javax.*`、舊版 Spring Security 配置）一律按 3.x（`jakarta.*`、新版 Security）改

### 不要做的事

1. ❌ **不要建議我改技術棧**（第 4 節已定案）
2. ❌ **不要建議我加新功能**（第 5 節已定案）
3. ❌ **不要參考黑馬點評 plus 的所有功能照抄**，只抄第 5 節列出的 5 個
4. ❌ **不要把 Python 該做的事用 Java 做**（例如不要在 Java 裡寫 RAG，那是 Python 的工作）

---

## 8. 我目前的狀態

- ✅ 原版黑馬點評已敲完，本地端可運行，頁面功能手動測過
- ⚠️ 我**不確定**現有 code 有沒有隱藏問題（沒做併發測試、沒做邊界測試）
- ⏳ Spring Boot 還是 2.7，**尚未升級到 3.x**
- ⏳ 還沒有任何 Python AI 服務代碼
- ⏳ 前端還是原版 Vue 2 手機版，**還沒換成 Vue 3**

**目前第一階段任務**：請先對現有 Java 代碼做完整體檢（見 `docs/code-review-request.md`），找出問題、列出 Spring Boot 3 升級會壞掉的地方，**先不要動代碼**，等我看完報告再決定哪些先改。

---

## 9. 溝通語言

- 跟我對話用**繁體中文**
- 程式碼註解用**繁體中文**
- 變數名、類別名、API 路徑用**英文**
- Git commit message 用**英文**（業界慣例）
## 10. 參考資料位置

以下原始碼**不在本 repo 內**，位於與本 repo 同層的目錄：

- `~/projects/_references/hmdp-plus-master/` — 黑馬點評 plus 源碼（功能參考）
- `~/projects/_references/damai-ai-master/` — 大麥 AI 源碼（AI 概念參考）

**規則**：

1. 不要主動去讀這些檔案，除非我明確要求
2. 我說「參考 plus 的 XXX」時，才去讀對應檔案，理解後**用本專案的架構（JPA、Spring Boot 3、台灣化）重寫**
3. 功能地圖在 `docs/_internal/`：
   - `plus-feature-map.md`（之後產出）
   - `damai-ai-concept-map.md`（之後產出）
4. **絕對禁止**：
   - 把 plus 或大麥 AI 的代碼直接複製到本專案
   - 讓本專案代碼風格跟原版 100% 一致
   - 把這些目錄 commit 進本 repo（`.gitignore` 已擋）
