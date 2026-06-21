# ByteBites 展示導覽

[English version](demo-walkthrough.en.md)

這份文件是給 reviewer 或面試官看的展示路線。它不是內部錄影備忘錄，也不是功能清單；目標是用 3 到 5 分鐘證明 ByteBites 的核心工程判斷：

```text
AI 負責理解需求與協調流程。
Java 負責訂位、付款、臨場事件與退款狀態。
```

ByteBites 的展示重點不是「AI 會聊天」，而是 AI 應用如何在真實交易流程中維持狀態邊界、資料品質與可驗證性。

## 3 分鐘版本

| 時間 | 畫面 | 要證明的事 |
|---:|---|---|
| 0:00-0:20 | README 或首頁 | ByteBites 是 AI 用餐營運平台，不是單輪餐廳推薦 chatbot。 |
| 0:20-0:55 | AI 推薦卡 | AI 能理解模糊用餐需求，但回到 UI 時使用結構化推薦店家 id，不讓文字與卡片漂移。 |
| 0:55-1:25 | 我的訂位 | 使用者進入訂位後，Java 成為 source of truth；訂位、付款、改單、訂金狀態都由後端合約維護。 |
| 1:25-2:05 | 臨場救場與商家提案 | 顧客晚到時，系統 deterministic 找最近有效訂位並建立 incident；商家可提出替代時段。 |
| 2:05-2:30 | LINE Flex card | LINE 是 action channel，不是狀態來源；接受或拒絕仍回到 Java transaction 驗證。 |
| 2:30-3:00 | 架構 / CI | 收斂到架構邊界與驗證：AI orchestrates, Java owns state；Portfolio CI 與 release gates 可重現主張。 |

## 5 分鐘版本

| 時間 | 畫面 | 講法 |
|---:|---|---|
| 0:00-0:25 | README / 首頁 | 先講產品定位：推薦只是入口，真正的工程價值在訂位、付款狀態、臨場事件、LINE 協調與營運處理。 |
| 0:25-1:00 | AI chat / 推薦卡 | 展示自然語言查詢、推薦理由、照片與卡片。重點是文字與卡片共享 structured shop ids。 |
| 1:00-1:35 | 訂位 / demo payment | 展示 booking code、付款狀態、人數、時間。強調交易狀態不由模型保存。 |
| 1:35-2:20 | 臨場救場 | 使用「我塞車會晚到 20 分鐘」說明 AI 不猜訂位，Java 從最近有效訂位建立 `tb_booking_incident`。 |
| 2:20-3:00 | 商家後台 | 展示 OPEN incident、替代時段 proposal、PENDING / ACCEPTED / DECLINED / EXPIRED lifecycle。 |
| 3:00-3:30 | LINE card | 說明 Flex card 只提供顧客操作入口，真正狀態轉移仍由 Java 驗證身份、期限、座位與訂金政策。 |
| 3:30-4:05 | 退款營運 | 展示 refund operations digest、FAILED / stale PROCESSING、escalation note，說明 demo reconciliation 與真實 PSP rollout 的邊界。 |
| 4:05-4:35 | 架構總覽 / ER Model | 用架構圖與 ER Model 說明 Web、AI、Java、LINE、ETL、Qdrant、MySQL 與 Nginx 的責任分界。 |
| 4:35-5:00 | CI / release readiness | 展示 `scripts/verify-portfolio.sh`、Portfolio CI、release readiness、clean migration smoke，收斂到可驗證交付。 |

## 可直接照念的短稿

```text
這是 ByteBites。我把它做成一個 AI 用餐營運平台，而不是只有餐廳推薦的 chatbot。

第一段是 discovery。使用者可以用自然語言描述需求，AI service 會理解地點、料理、人數、場合與偏好。但回到產品畫面時，不是只顯示一段模型文字，而是回傳結構化推薦店家 id，讓文字說明和推薦卡片對得起來。

第二段是訂位。只要使用者從推薦進到 booking，Java backend 就是 source of truth。訂位編號、日期時間、人數、付款狀態、改期與訂金調整，都由 Java contract 管，不讓模型直接改核心狀態。

第三段是臨場救場。當顧客說「我塞車會晚到 20 分鐘」，系統不會讓模型猜是哪一筆訂位，而是 deterministic 找最近有效訂位，然後由 Java 建立 incident。商家後台可以看到 open incident，提出替代時段，顧客可以接受或拒絕。

第四段是 LINE。LINE 在這裡是 action channel，不是狀態來源。Flex card 可以把救場通知送到顧客手上，但接受或拒絕仍然會回到 Java transaction，由後端驗證身份、期限、訂位規則和訂金政策。

第五段是營運面。這個專案也處理補款、退款 reconciliation、失敗退款、SLA、escalation note，以及 refund operations digest。我沒有把 demo callback 假裝成真實 PSP rollout；production 版本會另外接真實 refund provider。

最後是架構和驗證。Next.js 是產品介面，FastAPI AI service 做 orchestration 和 LINE card，Java Spring Boot 擁有 booking、payment、incident、refund state，ETL 把餐廳與評論資料整理進 MySQL 和 Qdrant，Nginx 定義公開路由邊界。

所以這個作品我會定位成 portfolio-ready：功能是完整縱切，而且有 CI、release readiness、clean MySQL migration smoke 和測試保護。但我不會誇口說它已經是 production SaaS。真的上線下一步會是 managed secrets、cloud runtime、backup、observability、真實 PSP refund provider，還有營運制度。
```

## 證據對照

| 主張 | 建議展示 | 對應證據 |
|---|---|---|
| 不是單純聊天機器人 | AI 推薦卡 -> 訂位 -> 救場 -> 退款營運 | [架構總覽](architecture-overview.md) |
| Java 是交易狀態權威 | 我的訂位、商家後台、incident proposal | [訂位營運 ER Model](er-model-booking-operations.md) |
| AI 有可靠性邊界 | late arrival prompt、structured recommendation ids、evals | [AI 對話狀態案例](case-studies/10-ai-dialogue-state.md) |
| 資料品質可審查 | data coverage、taxonomy、ABSA、Qdrant payload | [資料覆蓋率報告](data-coverage-report.md) |
| 部署與驗證不是事後補充 | Portfolio CI、Nginx contract、migration smoke | [公開展示部署案例](case-studies/11-demo-deployment.md) |
| 效能沒有誇大 | hot query paths、indexes、code anchors | [效能與查詢證據](performance-query-evidence.md) |

## 錄影前檢查

正式錄影或 live demo 前，至少跑：

```bash
scripts/release-readiness.sh --offline
scripts/verify-portfolio.sh
```

若本機三個服務與 Nginx public proxy 都已啟動，再跑：

```bash
scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict
```

乾淨資料庫啟動驗證：

```bash
scripts/smoke-clean-mysql-migrations.sh --timeout 180
```

## 不要過度宣稱

這個專案可以說是 portfolio-ready、contract-tested、demo-ready。不要說它已經是 production SaaS。

正式上線仍需要：

- managed secrets；
- cloud runtime 與 cloud data stores；
- backup / restore policy；
- observability dashboards 與 alerting；
- 真實 PSP refund provider；
- merchant notification preferences；
- operations runbook。

這個回答反而比較專業：作品已經證明核心工程能力，但 production rollout 是另一個明確 gate。
