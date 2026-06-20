# 任務計畫：incident 後下一步評估與最小縱切

## 目標
評估 real-time incident handling 完成後的下一個最高價值產品能力，並完成一個可驗證、可面試展示的最小縱切。

## 目前階段
階段 44 完成

## 各階段

### 階段 1：需求與現況盤點
- [x] 理解使用者意圖
- [x] 讀取 README、roadmap、case study、portfolio evidence
- [x] 盤點 incident 相關程式碼與測試覆蓋
- [x] 將發現記錄到 findings.md
- **狀態：** complete

### 階段 2：評估方案
- [x] 提出 3 個下一步候選方案
- [x] 依面試展示價值、技術風險、縱切完整度排序
- [x] 選定本輪實作目標
- **狀態：** complete

### 階段 3：實作最小縱切
- [x] 依既有架構補足後端、AI、Web 或文件中缺口最大的部分
- [x] 保持 Java 為 source of truth
- [x] 避免改動與本輪無關的既有變更
- **狀態：** complete

### 階段 4：測試與驗證
- [x] 執行最小相關測試
- [x] 如可行執行 portfolio verification
- [x] 記錄測試結果到 progress.md
- **狀態：** complete

### 階段 5：交付
- [x] 總結方案評估
- [x] 說明完成項目、檔案、驗證結果
- [x] 提供下一步建議
- **狀態：** complete

### 階段 6：Alternative Slot Suggestions 最小縱切
- [x] 盤點 slot inventory / reschedule / merchant incident payload
- [x] 選定不碰訂金差額的建議模型
- [x] 由 Java 計算替代時段 suggestions
- [x] 商家後台顯示 suggestions
- [x] 補測試與文件
- **狀態：** complete

### 階段 7：顧客確認替代時段提案
- [x] 設計 pending proposal 欄位與狀態
- [x] 商家從 suggestion 建立 proposal
- [x] 顧客在 My Bookings 接受 proposal
- [x] 接受後走既有 BookingRescheduleService
- [x] 補 Java/Web 測試與文件
- **狀態：** complete

### 階段 8：替代時段提案拒絕與逾期
- [x] 新增 proposal expiry / declined 狀態欄位
- [x] 顧客可拒絕 pending proposal，incident 保持 OPEN 讓商家可再提案
- [x] 顧客接受逾期 proposal 時由 Java 標記 EXPIRED 並拒絕改單
- [x] Web 顯示有效期限並提供拒絕按鈕
- [x] 補 Java/Web 測試與文件
- **狀態：** complete

### 階段 9：LINE 替代時段提案卡
- [x] Java 在商家送出 proposal 後推送 LINE proposal notification
- [x] AI service 新增 internal LINE proposal endpoint 與 Flex card
- [x] LINE 輕量頁可接受/拒絕 proposal，並呼叫 Java source of truth
- [x] LINE status / my-bookings 頁顯示 pending proposal 操作入口
- [x] 補 Java / AI 測試與文件
- **狀態：** complete

### 階段 10：訂金政策防護
- [x] 盤點改期、proposal acceptance 與訂金重算路徑
- [x] 對已付款訂位阻擋會產生加收或退款的自動改單
- [x] 成功改單時回傳 depositPolicy metadata
- [x] 補 Java contract tests 與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 11：商家手動訂金差額處理
- [x] 新增 manual deposit adjustment persistence
- [x] 被訂金 guard 擋下時建立 OPEN adjustment
- [x] 商家後台可列出與完成 adjustment
- [x] 完成後由 Java 套用改單，incident proposal 來源同步收斂狀態
- [x] 補 Java/Web 測試與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 12：訂金差額 PSP settlement tracking
- [x] 盤點既有 TapPay/payment controller 與 booking payment state
- [x] 為 deposit adjustment 新增 settlement 狀態與交易紀錄欄位
- [x] 後端提供 settlement initiate / mark-complete contract，避免商家直接跳過付款狀態
- [x] 商家後台顯示 settlement 狀態並依狀態啟用套用改單
- [x] 補 Java/Web 測試與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 13：顧客補款 checkout link
- [x] 盤點 My Bookings TapPay iframe 付款流程與 adjustment payload
- [x] 後端提供 customer TOP_UP adjustment list 與 pay-by-prime endpoint
- [x] 顧客付款成功後由 Java 記錄 settlement，但不直接套用改單
- [x] My Bookings 顯示待補款項目並可用 TapPay iframe 完成補款
- [x] 補 Java/Web 測試與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 14：退款 webhook / reconciliation
- [x] 盤點 REFUND adjustment settlement 現況與前端操作
- [x] 後端新增 refund request -> processing -> completed/failed 狀態機
- [x] Payment API 提供 PSP refund reconciliation callback
- [x] 商家後台將 REFUND 從手填完成改成請求與對帳結果
- [x] 補 Java/Web 測試與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 15：退款 reconciliation idempotency + audit
- [x] 盤點 refund callback 重送風險與既有欄位
- [x] 新增 refund reconciliation audit table
- [x] PSP reconciliation callback 支援 event key idempotency
- [x] refund request / reconciliation 都留下 audit event
- [x] 補 Java tests 與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 16：退款 webhook signature verification
- [x] 盤點 refund reconciliation callback 與設定方式
- [x] 新增 optional HMAC signature verification
- [x] 設定 secret 時拒絕缺失、過期或錯誤簽章
- [x] 保持 demo 無 secret 時可用
- [x] 補 Java tests 與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 17：退款 SLA / stuck refund visibility
- [x] 盤點 refund adjustment list、merchant API 與 web 顯示接點
- [x] 後端提供商家 refund SLA summary，聚合 FAILED 與超時 PROCESSING refund
- [x] 商家後台顯示退款 SLA 注意狀態
- [x] 補 Java/Web 測試與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 18：退款 escalation / follow-up tracking
- [x] 盤點 refund SLA summary、audit table 與 merchant UI 接點
- [x] 後端記錄 refund escalation 狀態與 audit event
- [x] 商家後台可對 FAILED 或 stale PROCESSING refund 標記已升級處理
- [x] 補 Java/Web 測試與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 19：退款 webhook secret rotation
- [x] 盤點 refund webhook signature 驗證與設定方式
- [x] 支援 current + previous webhook secret，讓 production 可平滑輪替
- [x] 保持 demo 無 secret 時可用，設定 secret 時仍拒絕缺失/過期/錯誤簽章
- [x] 補 Java tests 與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 20：退款 escalation report / operations digest
- [x] 盤點 refund SLA summary、escalation 欄位與 merchant UI 接點
- [x] 後端提供商家 scoped refund operations report，彙整 FAILED、stale PROCESSING、已升級與未升級退款
- [x] 商家後台顯示可讀 digest，協助快速判斷待處理重點
- [x] 補 Java/Web 測試與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 21：退款 operations digest notification
- [x] 盤點商家 LINE 綁定與既有 internal LINE notification 模式
- [x] 後端提供可觸發的 refund operations digest notification contract
- [x] AI service / LINE internal endpoint 產生 digest Flex card
- [x] 沒有商家 LINE 綁定時回傳 skipped，不假裝已通知
- [x] 補 Java / AI tests 與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 22：退款 operations digest scheduled policy
- [x] 盤點 Phase 21 triggerable notification 與 operations digest payload
- [x] 後端提供 scheduler 可呼叫的 due-policy / dispatch-if-due contract
- [x] 記錄 successful dispatch，支援 cooldown 與 skipped reason
- [x] 商家後台顯示排程通知判斷與可手動執行 due dispatch
- [x] 補 Java/Web 測試與文件
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 23：退款 callback source validation / PSP allowlist
- [x] 盤點 refund callback signature / rotation contract
- [x] 新增 optional source allowlist 與 trusted proxy header 設定
- [x] 未設定 allowlist 時保留 demo callback；設定後拒絕未知來源
- [x] 補 Java contract tests
- [x] 同步文件與 portfolio evidence
- [x] 執行 targeted tests 與 portfolio verification
- **狀態：** complete

### 階段 24：Nginx stable public deployment boundary
- [x] 盤點現有 ngrok / Next rewrites / LINE Login callback / LINE webhook 路由
- [x] 決策保留 ngrok 作為 local temporary demo，新增 Nginx 作為 stable public entrypoint
- [x] 新增 Nginx reverse proxy template，保留 `/api/java`、`/api/ai`、`/api/line`、`/line` 路由語義
- [x] 補部署指南，列出 LINE、Web、Java、AI 與 refund source allowlist env
- [x] 加入離線 template verifier 並接進 portfolio verification
- [x] 執行 targeted verifier / portfolio verification / diff check
- **狀態：** complete

### 階段 25：Nginx Docker Compose public-proxy overlay
- [x] 盤點 root / deploy compose 與 Nginx template 相對路徑
- [x] 新增可用 Docker Compose 啟動的 Nginx public-proxy overlay
- [x] 更新部署指南、README、roadmap、evidence map 與 case study
- [x] 擴充 Nginx verifier，檢查 compose overlay contract
- [x] 執行 compose config、targeted verifier、portfolio verification、diff check
- **狀態：** complete

### 階段 26：Nginx public-proxy smoke test runner
- [x] 盤點現有 demo keepalive、AI stream endpoint、LINE webhook 與 Login redirect 行為
- [x] 新增短命令 smoke script，檢查 Nginx public proxy routes
- [x] 更新部署文件、README、roadmap、portfolio evidence 與 case study
- [x] 擴充 verifier，檢查 smoke script 語法與 dry-run
- [x] 執行 targeted verifier、portfolio verification、diff check
- **狀態：** complete

### 階段 27：Demo readiness preflight runner
- [x] 評估下一步候選方案：live smoke、preflight runner、HTTPS/雲端、回到產品功能
- [x] 新增 demo readiness preflight script，檢查 compose config、服務健康與可選 live smoke
- [x] 更新部署文件、README、roadmap、portfolio evidence 與 case study
- [x] 擴充 verifier，檢查 preflight script 語法與 dry-run
- [x] 執行 dry-run、targeted verifier、portfolio verification、diff check
- **狀態：** complete

### 階段 28：正式 demo rehearsal
- [x] 檢查目前 Web / Java / AI / Nginx public proxy live 狀態
- [x] 啟動缺失的 infra / Java / AI / Web / Nginx public proxy
- [x] 執行 `scripts/demo-readiness.sh --live-smoke --strict`
- [x] 若 live rehearsal 失敗，修正可控問題或記錄外部阻塞
- [x] 更新 findings/progress，說明 demo rehearsal 結果與下一步
- **狀態：** complete

### 階段 29：Clean MySQL migration smoke runner
- [x] 新增 clean MySQL migration smoke script，用臨時 DB 驗證 Java/Flyway 可從空 schema 啟動
- [x] 腳本支援 dry-run、keep-db、timeout、container/db/port 覆寫，預設清理臨時 DB 與 Java process
- [x] 將 dry-run / syntax contract 接進 portfolio verification
- [x] 更新 README、deployment docs、roadmap、evidence/case study 與 planning 記錄
- [x] 執行 dry-run、live migration smoke、targeted tests、portfolio verification、diff check
- **狀態：** complete

### 階段 30：GitHub Actions clean migration smoke workflow
- [x] 盤點現有 GitHub Actions 與 Java runtime 依賴
- [x] 新增手動觸發 workflow，用 CI MySQL/Redis/RabbitMQ 執行 clean migration smoke
- [x] 增加離線 workflow contract verifier，檢查手動觸發、infra、腳本參數與 timeout
- [x] 將 verifier 接進 portfolio verification
- [x] 更新 README、deployment docs、roadmap、evidence/case study 與 planning 記錄
- [x] 執行 workflow verifier、portfolio verification、diff check
- **狀態：** complete

### 階段 31：Release boundary and final handoff
- [x] 新增 release boundary 文件，收斂 demo 前 gate、live smoke、CI 手動 workflow、commit grouping 與 production gaps
- [x] 新增 release readiness 腳本，提供 dry-run、offline、full、live-local 四種檢查模式
- [x] 新增 release boundary verifier，確保文件與腳本關鍵 contract 不漂移
- [x] 將 verifier 接進 portfolio verification
- [x] 更新 README、portfolio evidence map、case study 與 planning 記錄
- [x] 執行 release verifier、release dry-run/offline、portfolio verification、diff check
- **狀態：** complete

### 階段 32：Portfolio CI taxonomy fixture stabilization
- [x] 盤點最新 GitHub Portfolio CI failure 與本機 verification 差異
- [x] 確認 ETL taxonomy tests 依賴被 `.gitignore` 排除的 `etl-pipeline/data/raw/`
- [x] 新增 committed minimal taxonomy fixture，讓 CI 有穩定分類回歸資料
- [x] 將完整 103 筆 approval test 限定在 full raw corpus 存在時執行
- [x] 模擬沒有 raw corpus 的 CI checkout 並跑完整 ETL tests
- [x] 執行 release offline gate 與完整 portfolio verification
- [x] commit / push 並確認 GitHub Portfolio CI 回綠
- **狀態：** complete

### 階段 33：Portfolio readiness scorecard and next plan
- [x] 評估目前作品是否已足夠面試展示
- [x] 給出 portfolio readiness score 與角色別評分
- [x] 新增 scorecard 文件，明確區分 portfolio-ready 與 production-ready
- [x] 將 scorecard 接進 README / release boundary / verifier
- [x] 執行 release verifier、portfolio verification、CI
- **狀態：** complete

### 階段 34：Portfolio 100 roadmap, evidence package, architecture overview
- [x] 將 100 分拆成 Portfolio 100 與 Production SaaS 100
- [x] 新增 reviewer-facing demo evidence checklist
- [x] 新增一頁式 architecture overview 與狀態權責圖
- [x] 將三份文件接進 README / release boundary / verifier
- [x] 執行 release verifier、release offline gate、portfolio verification、CI
- **狀態：** complete

### 階段 35：Recording and cloud rollout decision
- [x] 評估是否應由作者親自錄製 portfolio walkthrough
- [x] 評估上雲應放在錄影前或錄影後
- [x] 將 managed secrets、PSP refund、備份、觀測、營運制度拆成 portfolio vs production expectations
- [x] 新增 recording/cloud plan 並接進 README / roadmap / release verifier
- [x] 執行 release verifier、release offline gate、portfolio verification、CI
- **狀態：** complete

### 階段 36：Recording script and shot plan
- [x] 產出 3-5 分鐘錄影講稿與逐段分鏡
- [x] 補 3 分鐘短版、5 分鐘主版、12 分鐘面試版
- [x] 對齊 evidence screenshots 的拍攝順序與檔名
- [x] 將 recording script 接進 README / evidence package / scorecard / roadmap / release verifier
- [x] 執行 release verifier、release offline gate、portfolio verification、CI
- **狀態：** complete

### 階段 37：Screenshot evidence capture
- [x] 評估截圖與 GIF 的取捨
- [x] 啟動可截圖的本機 Web / Java / AI stack
- [x] 依 recording script / evidence package 捕捉高訊號畫面
- [x] 檢查截圖是否可讀、無 secrets、無明顯空白或錯誤狀態
- [x] 記錄截圖位置、缺口與下一步是否需要 GIF
- **狀態：** complete

### 階段 38：Remaining evidence screenshots
- [x] 補 LINE rescue/proposal card evidence
- [x] 補 refund operations digest evidence
- [x] 補 architecture overview evidence
- [x] 補 CI / verification evidence
- [x] 更新截圖索引與後續錄影建議
- **狀態：** complete

### 階段 39：Recording script polish and GIF preview
- [x] 重新審稿 3 分鐘 / 5 分鐘錄影講稿
- [x] 補繁中 3 分鐘逐字稿，讓使用者可直接照念
- [x] 產出 evidence walkthrough GIF preview
- [x] 更新 evidence package 與 recording checklist
- [x] 執行 release offline gate
- **狀態：** complete

### 階段 40：ER model evidence
- [x] 評估是否需要 ER model 面試圖
- [x] 盤點 booking / incident / deposit adjustment / refund audit 核心 schema
- [x] 新增 booking operations ER model 文件
- [x] 輸出 ER model PNG evidence
- [x] 更新 demo evidence package、錄影順序、release verifier 與 GIF preview
- **狀態：** complete

### 階段 41：Internal top-company readiness planning
- [x] 以大廠標準重新評估 Java / 全端 / AI 應用三條投遞方向
- [x] 定義內部 95-100 分補強路線
- [x] 移除不適合 reviewer-facing 的公開 top-company plan 文件
- [x] 將殘酷評分與投遞策略改記在 planning files
- [x] 確立對外文件只放成熟、正向、可驗證 artifacts
- **狀態：** complete

### 階段 42：System design interview pack
- [x] 避開錄影，選擇下一個高價值 reviewer-facing artifact
- [x] 新增 system design interview pack
- [x] 覆蓋架構邊界、一致性、失敗模式、AI reliability、production rollout
- [x] 接入 README / release boundary / evidence map / 100 roadmap / evidence package
- [x] 接入 release boundary verifier
- **狀態：** complete

### 階段 43：Performance/query evidence
- [x] 盤點 hot operational query paths 與既有 migration indexes
- [x] 新增 performance/query evidence 文件
- [x] 新增 verifier 檢查文件、索引與程式碼錨點
- [x] 將 verifier 接入 release readiness 與 portfolio verification
- [x] 同步 README / release boundary / evidence map / scorecard / roadmap
- **狀態：** complete

### 階段 44：README public-facing cleanup
- [x] 重新審視 README 是否像正式作品入口
- [x] 移除 README 中不適合公開入口的自評、100 分、錄影、面試準備連結
- [x] 將 README 改為中文主文件
- [x] 新增獨立英文版 README
- [x] 將英文 README 納入 markdown link verifier
- **狀態：** complete

## 關鍵問題
1. incident 完成後，下一個能力應強化「營運閉環」、「AI 個人化」還是「可觀測/後台」？
2. 哪個最小縱切能增加面試敘事價值，而不把系統帶進過大重構？

## 已做決策
| 決策 | 理由 |
|------|------|
| 先盤點再選項 | 目前工作樹已有大量既有變更，不能憑記憶直接動手 |
| 保持 Java 為狀態權威 | 延續 incident 縱切的架構主張，避免 AI 任意決策核心狀態 |
| 本輪實作商家端 incident console | 它補上店家處理 OPEN incident 的營運閉環，價值高於單純補文案或做大型政策引擎 |
| 下一輪實作 alternative slot suggestions | 它讓 merchant console 從被動處理升級成可協調方案，但本輪不直接改單、不處理訂金差額 |
| Alternative slot suggestions 已完成第一版 | Java 依 slot inventory 計算可協調時段，商家頁只展示 backend suggestions |
| 顧客確認提案採單一 pending proposal | 避免新建多輪協商系統；這版先證明狀態轉移與改單 contract，未來再拆 proposal table |
| 顧客確認提案第一版已完成 | 商家提出 PENDING proposal，顧客接受後沿用既有改單 contract 並標記 incident RESOLVED |
| 先補 decline/expiry 再接 LINE proposal card | 目前提案只有接受路徑；完整狀態機是 LINE 深連結與面試追問前的必要基礎 |
| 替代時段提案狀態機第一版完成 | Java 現在支援 PENDING -> ACCEPTED / DECLINED / EXPIRED；Web 只顯示和操作 Java payload |
| LINE proposal card 採「LINE 頁面呼叫 Java」 | 避免讓 AI service 擁有狀態；LINE 入口只帶 token 與使用者意圖，accept/decline 仍由 Java transaction 驗證 |
| LINE proposal card 第一版完成 | 商家提案後會推 LINE Flex card；顧客可在 LINE 接受/拒絕，AI service 只轉送 token 和操作到 Java |
| 訂金政策先做防護不做退款金流 | 目前真正風險是 paid booking 改人數時靜默改變已付款訂金義務；先由 Java 阻擋差額並要求人工處理，避免假裝已有退款/補款系統 |
| 訂金政策防護第一版完成 | `BookingRescheduleService` 現在是改單與 incident proposal acceptance 的共同 guard；成功回傳 `depositPolicy`，失敗時不異動 slot capacity 或 booking |
| 商家手動訂金差額處理採「外部處理 + Java 套用」 | Demo 不做真實 TapPay 退款/補款；商家標記已人工處理後，Java 才用 override 套用改單並保留審計紀錄 |
| 商家手動訂金差額處理第一版完成 | 被訂金 guard 擋下的 direct reschedule / incident proposal acceptance 會建立 OPEN adjustment；商家確認外部處理後由 Java 套用改單並同步 resolve 相關 incident proposal |
| Phase 12 選 PSP settlement tracking | 既有 TapPay booking payment 已有 source-of-truth 狀態；下一步應把 TOP_UP/REFUND adjustment 也變成可追蹤 settlement，而不是只靠 handling note |
| PSP settlement tracking 第一版完成 | `tb_booking_deposit_adjustment` 現在記錄 settlement 狀態、provider、交易編號、金額與完成時間；Java 會在 settlement completed 前拒絕套用改單 |
| Phase 13 先做 customer TOP_UP checkout | TOP_UP 可以沿用顧客端 TapPay prime；REFUND 需要 PSP webhook/reconciliation，風險不同，保留下一輪 |
| customer TOP_UP checkout 第一版完成 | My Bookings 現在顯示待補款改單，顧客可用 TapPay iframe 完成 TOP_UP；Java 只記錄 settlement，最後改單仍由商家端 apply |
| Phase 14 選 REFUND webhook / reconciliation | TOP_UP 已能由顧客付款；退款側缺的是 PSP 非同步結果與失敗狀態，不能再用商家手填完成取代 |
| REFUND 不再走 merchant direct settlement | 退款要先建立請求、等待 PSP 對帳，再由 callback/reconciliation 標記 COMPLETED 或 FAILED；Java apply 仍只接受 COMPLETED |
| REFUND reconciliation 第一版完成 | 商家後台可建立退款請求，demo/internal payment callback 可標記 COMPLETED/FAILED；失敗退款不允許套用改單 |
| Phase 15 選 refund idempotency + audit | PSP callback 可能重送；沒有 event key 去重和 audit table 時，狀態可信但事後追蹤不足 |
| refund idempotency + audit 第一版完成 | V49 audit table 記錄 request/reconciliation events；Payment callback 可帶 eventKey，重複 key 回傳 idempotentReplay |
| Phase 16 選 signed webhook verification | idempotency/audit 已完成；正式 PSP callback 的下一個缺口是來源驗證與防竄改 |
| signed refund webhook 第一版完成 | `bytebites.refund.webhook.secret` 設定後，callback 必須帶 fresh timestamp 與 HMAC-SHA256 signature；未設定時保留 demo 流程 |
| Phase 17 選 refund SLA visibility | refund 狀態機、idempotency、audit、signature 都已完成；下一個高價值缺口是讓營運端快速看到 FAILED 或卡在 PROCESSING 的退款 |
| refund SLA visibility 第一版完成 | Java 提供商家 scoped summary，Web 後台顯示 FAILED 與超時 PROCESSING refund 數量，讓 refund reconciliation 具備營運監控入口 |
| Phase 18 選 refund escalation tracking | SLA 已能發現退款異常；下一步應讓商家標記已升級處理並留下 Java-side audit，而不是只顯示警示 |
| refund escalation tracking 第一版完成 | `tb_booking_deposit_adjustment` 記錄 escalation 狀態；商家操作會寫 `REFUND_ESCALATED` audit event，Web 顯示已升級與備註 |
| Phase 19 選 webhook secret rotation | HMAC 已能驗證來源；production 換 secret 時需要 current/previous secret 並存，避免 PSP callback 在部署窗口中斷 |
| refund webhook secret rotation 第一版完成 | `PaymentController` 支援 current/previous secret；previous secret 簽章可在輪替期間通過，demo 無 secret 仍可用 |
| Phase 20 選 refund escalation report | SLA 能發現異常、escalation 能標記接手；下一步應把 refund operations 壓成可讀 digest，讓商家能快速看見未升級與已升級待追蹤項目 |
| refund operations digest 第一版完成 | Java 以商家 scope 回傳 pending escalation / escalated follow-up report；Web 後台顯示建議動作與重點退款項目 |
| Phase 21 選 refund operations digest notification | Phase 20 已有可讀 digest；下一步要讓 digest 可被排程或後台觸發通知，但本輪不新增 cron/job infrastructure |
| refund operations digest notification 第一版完成 | 商家可手動觸發 LINE digest；Java 經商家 LINE identity link 找推播目標，未綁定或無異常時回傳 skipped |
| Phase 22 選 scheduled notification policy | triggerable digest 已完成；下一步應先定義 scheduler 可用的 due 判斷、cooldown 與 dispatch audit，而不是直接新增不可配置的固定 cron |
| refund operations scheduled policy 第一版完成 | Java 現在提供 due-policy / dispatch-if-due contract，使用 dispatch audit 與 cooldown 防止重複推播；Web 可顯示排程判斷並手動執行 due dispatch |
| Phase 23 選 refund callback source validation | HMAC、secret rotation、scheduled policy 已完成；下一個 production hardening 缺口是 callback 來源約束，避免只靠簽章而完全不看來源 |
| refund callback source validation 第一版完成 | `PaymentController` 支援 optional allowed-sources、trusted-proxies、source-header；未設定時保留 demo，設定後可驗 direct source 或 trusted proxy forwarded source |
| Phase 24 不把 ngrok 直接替換成 Nginx | ngrok 與 Nginx 解的是不同問題；ngrok 適合本機快速 tunnel，Nginx 適合穩定公開網域、TLS、proxy headers、健康檢查與 production-like source validation |
| Nginx route contract 必須沿用現有 public path | Web 已使用 `/api/java` 啟動 LINE Login、AI 使用 `/api/line` webhook 與 `/line` action pages；Nginx 應固定這些路徑，避免重新引入 OAuth cookie path 或 webhook URL 錯位 |
| Nginx stable public deployment boundary 第一版完成 | 新增 `deploy/nginx/bytebites.conf.template`、`docs/deployment-nginx.md` 與 `scripts/verify-nginx-template.py`，並接進 `scripts/verify-portfolio.sh` |
| Phase 25 選 Docker Compose overlay | Nginx template 已可描述路由，但還不能一行啟動；compose overlay 能讓本機三服務啟動後用 `localhost:8088` 演練 public proxy，不需要先上雲 |
| Nginx Docker Compose public-proxy overlay 第一版完成 | 新增 `deploy/docker-compose.nginx.yml`，用 `public-proxy` profile 啟動 containerized Nginx，預設代理 host 上的 Web/Java/AI，並由 verifier 與 compose config 保護 |
| Phase 26 選 smoke test runner | Compose overlay 已能啟動 proxy；下一步應把 manual curl checks 收斂成一個短命令，驗證 root、Java health、AI health、LINE webhook、LINE Login redirect 與 AI SSE 起始 frame |
| Nginx public-proxy smoke runner 第一版完成 | 新增 `scripts/smoke-nginx-public-proxy.sh`，live services 已啟動時可一鍵檢查 public proxy；portfolio gate 透過 verifier 檢查語法與 dry-run |
| Phase 27 選 demo readiness preflight runner | live smoke runner 已存在，但 demo 前仍需要知道 Web/Java/AI/Nginx 是否已啟動、compose overlay 是否有效、下一步該跑什麼；preflight 能把人工 checklist 變成可執行檢查 |
| demo readiness preflight 第一版完成 | `scripts/demo-readiness.sh` 現在能先驗部署檔、Compose overlay、Web/Java/AI/Nginx reachability，並可用 `--live-smoke --strict` 進入正式彩排；portfolio gate 只驗語法與 dry-run |
| Phase 28 live rehearsal 完成 | 實際啟動 Web/Java/AI/Nginx 後，`scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict` 全部通過，包含 root、Java health、AI health、LINE webhook、LINE Login redirect/cookie path、AI SSE start frame |
| V16 taxonomy backfill 必須容忍 seed shop 差異 | 乾淨 DB 只跑 migration 時，allowlist id 可能不存在；badge/tag backfill 需先 join `tb_shop`，避免 FK failure 擋住 Java 啟動 |
| Phase 29 選 clean MySQL migration smoke runner | V16 問題證明一般 unit test 與已遷移本機 DB 不足以保護 fresh-schema startup；正式 demo 前應用短命 DB 實際啟 Java 驗 Flyway |
| Clean MySQL migration smoke 第一版完成 | `scripts/smoke-clean-mysql-migrations.sh` 會建立臨時 DB、用臨時 port 啟 Java、等 health UP，再停止 Java 並刪 DB；portfolio gate 只跑 `bash -n` 與 `--dry-run` |
| Phase 30 選手動 GitHub Actions workflow | clean migration smoke 是 live infra check，不適合每次 push 強制跑；手動 workflow 能在正式 demo 前用 hosted runner 重現 fresh-schema startup |
| Clean MySQL migration smoke workflow 第一版完成 | `.github/workflows/clean-mysql-migration-smoke.yml` 啟 Redis/RabbitMQ services 與 named MySQL container，再呼叫同一支 smoke script；`verify-clean-migration-workflow.py` 保護 workflow contract |
| Phase 31 選 release boundary/handoff | 目前功能與驗證已足夠展示，下一個風險是 reviewer 或發表前找不到正確 gate；應把命令、commit grouping、live smoke 與 production gaps 收斂成一個 release boundary |
| Release boundary 第一版完成 | `docs/release-boundary.md` 與 `scripts/release-readiness.sh` 定義 dry-run/offline/full/live-local 四層檢查，並由 `verify-release-boundary.py` 接進 portfolio gate |
| Phase 32 選 CI fixture stabilization | Release boundary 已完成但 push gate 仍紅；下一步最高價值不是加新功能，而是消除 CI 與本機資料狀態不一致，讓 portfolio 證據可被第三方重現 |
| ETL taxonomy tests 分成 committed fixture 與 full corpus | CI checkout 不包含 ignored raw data；核心 fixture 必須提交，完整 103 筆 approval 只在完整 raw corpus 存在時執行 |
| Java proposal expiry tests 使用 business zone | Runtime 以台北時間判斷提案是否逾期；測試也必須用同一個 business zone，避免 UTC hosted runner 誤判 |
| Phase 33 先做 scorecard，不再加新功能 | 作品已足夠面試展示；下一個價值是把評分、證據、扣分點與後續計畫集中，讓面試官快速理解成熟度 |
| 100 分分成 Portfolio 100 與 Production SaaS 100 | 前者可在 repo 內靠證據包、架構圖、驗證與講稿達成；後者需要真實雲端、PSP、secrets、備份、觀測與營運制度 |
| Phase 35 先錄影再上雲 | 親自 voiceover 的短 walkthrough 最能展示工程判斷；上雲有價值但不應在證據包完成前阻塞 portfolio 100 |
| Phase 36 講稿採三層版本 | 3 分鐘短版適合履歷/作品集；5 分鐘主版適合正式錄影；12 分鐘版適合面試追問時展開 |
| Phase 37 先截圖再決定 GIF | 靜態截圖是作品集 evidence 的主體；GIF 只適合少數互動流程，避免產生大型低訊號檔案 |
| Phase 38 補齊剩餘 evidence | LINE card、refund digest、architecture、CI、clean migration smoke 都已輸出成可放作品集的 PNG；下一步應進入使用者親自 voiceover 錄影 |
| V52 collation migration 必須保留 | 製作 refund digest 證據時發現 `tb_booking_deposit_adjustment.booking_code` 與 `tb_booking.booking_code` collation 不一致會讓 adjustment join runtime 失敗；V52 將 schema 修回可乾淨啟動 |
| Phase 39 補繁中逐字稿與 GIF | 使用者錄影時最需要的是可直接照念的短稿；GIF 只作作品集預覽，正式展示仍以親自 voiceover 影片為主 |
| Phase 40 補核心 ER model 而非全庫大圖 | 面試官常問 ER 設計；最有價值的是 booking operations 模型，能解釋 Java source-of-truth、booking_code workflow key、incident proposal、deposit adjustment 與 refund audit |
| Phase 41 大廠評分只作內部策略 | Google/Binance/Shopee 等投遞評分和缺口很有用，但不應出現在 README / release boundary / scorecard；對外文件只呈現作品成熟證據 |
| Phase 42 補 system design interview pack | 使用者晚點才錄影；錄影之外最高價值是把架構追問答辯變成 reviewer-facing artifact，且不包含內部自評或投遞策略 |
| Phase 43 補 performance/query evidence | 大廠面試會問查詢與效能，但目前沒有 production-like benchmark；先把 hot path、索引與 code anchors 做成可驗證 evidence，不假裝已有 QPS/p95 數據 |
| Phase 44 README 採中文主文件 + 英文獨立版 | 台灣求職情境下 README 應先用中文專業呈現；英文版獨立存在即可，避免中英混排與內部準備文件讓入口失焦 |

## 遇到的錯誤
| 錯誤 | 嘗試次數 | 解決方案 |
|------|---------|---------|
| `smoke-nginx-public-proxy.sh` bash syntax error near function close | 1 | 將預設 stream query 改成不含單引號的 ASCII 字串，並把 Location header 解析從 awk 改成 grep/sed；`bash -n` 和 dry-run 隨後通過 |
| `demo-readiness.sh` 在 verifier dry-run 中仍打 localhost | 1 | 將 `DRY_RUN` / `STRICT` / `LIVE_SMOKE` 改成可由環境變數覆寫，讓 `verify-nginx-template.py` 的離線 dry-run 不碰本機服務 |
| Java 首次 live start 被 sandbox 擋 MySQL socket | 1 | 改用 escalated `mvn spring-boot:run` 啟動，確認後續連線問題是實際 DB state 而非 sandbox |
| 本機 MySQL 缺 `hmdp` schema | 1 | 在 local MySQL container 建立 `hmdp` schema，讓 Flyway 自動建表 |
| 乾淨 DB 跑 V16 taxonomy backfill 時 FK failure | 1 | 將 V16 badge/tag allowlist insert 改為 derived table join `tb_shop`，並新增 `TaxonomyMigrationResourceTest` guard |
| `demo-readiness.sh --live-smoke --strict` sandbox 執行 false negative | 1 | 直接 curl 成功後確認是腳本內 curl 被 sandbox 限制；改用 escalated live rehearsal 執行並通過 |
| `smoke-clean-mysql-migrations.sh` sandbox 無法連 Docker socket | 1 | 一般 sandbox 對 Docker daemon socket 回 operation not permitted；live migration smoke 改用 escalated execution，dry-run 保持離線 |
| macOS `mktemp` 不替換含 `.log` suffix 的模板 | 1 | 將模板從 `bytebites-clean-migration.XXXXXX.log` 改為 `bytebites-clean-migration.XXXXXX`，確保 BSD/macOS 可攜 |
| Portfolio CI ETL taxonomy tests 對缺失 raw corpus 丟 KeyError | 1 | 新增 committed taxonomy fixture，CI 固定跑核心分類 smoke；完整 approval map 缺 raw corpus 時明確 skip |
| Portfolio CI Backend Java proposal tests 在 UTC runner 誤判逾期 | 1 | 將 proposal expiry fixture 改成 `Asia/Taipei` business zone，與 production 判斷一致 |

## 備註
- 不回退使用者或前序工作留下的修改。
- 本輪只做小而完整的縱切，避免擴大 blast radius。
