# 進度日誌

## 會話：2026-06-20

### 階段 43：Performance/query evidence
- **狀態：** complete
- **完成時間：** 2026-06-21T01:10:00+08:00
- 執行的操作：
  - 使用者要求繼續完成錄影外的高價值項目後，選擇 performance/query evidence。
  - 盤點 booking、slot inventory、incident、deposit adjustment、refund reconciliation、merchant notification dispatch 的 migration indexes 與 Java query paths。
  - 新增 `docs/performance-query-evidence.md`，用 reviewer-facing 方式說明 hot operational query paths、支援索引、state transition performance choices、未證明的 production throughput 邊界與下一步 EXPLAIN/load-test artifact。
  - 新增 `scripts/verify-performance-query-evidence.py`，檢查文件、migration index snippets、Java operational code anchors 是否仍存在。
  - 將 verifier 接入 `scripts/release-readiness.sh --offline` 與 `scripts/verify-portfolio.sh`。
  - 將文件接入 README、release boundary、portfolio evidence map、scorecard、100 roadmap、system design pack、demo evidence package。
- 後續規劃評估：
  - 下一個工程證據應是 E2E seeded browser flows，或進一步做 seeded EXPLAIN runner。
  - 若要談真正 production performance，應補 production-like seed volume、EXPLAIN plan gate、slow query review 與 latency SLO，而不是在文件中寫未量測數字。

### 階段 42：System design interview pack
- **狀態：** complete
- **完成時間：** 2026-06-21T00:45:00+08:00
- 執行的操作：
  - 使用者表示錄影晚點再做，因此先處理錄影之外的高價值補強。
  - 新增 reviewer-facing `docs/system-design-interview-pack.md`，聚焦架構邊界、booking/incident flow、一致性模型、資料模型答辯、AI reliability、失敗模式、驗證故事與 production rollout answer。
  - 將 system design pack 接入 README fast links、release boundary、portfolio evidence map、portfolio 100 roadmap、demo evidence package。
  - 更新 `scripts/verify-release-boundary.py`，把 system design interview pack 納入 release boundary contract，避免文件漂移。
- 後續規劃評估：
  - 這份文件適合給面試官或面試時打開講，不是內部自評。
  - 下一步若還不錄影，最高價值會是 performance/query evidence 或 E2E seeded browser flows；兩者都應做成可驗證 artifact，不應再新增大功能。

### 階段 41：Internal top-company readiness planning
- **狀態：** complete
- **完成時間：** 2026-06-21T00:20:00+08:00
- 執行的操作：
  - 回應使用者希望作品達到「頂級 / 100 分」的要求，先用內部標準重新評估 Java backend、full-stack、AI application 三條投遞方向。
  - 初步新增過 reviewer-facing 的 top-company readiness doc 後，使用者指出這是寫給本人看的，不應讓面試官看到。
  - 接受修正：移除 README、release boundary、scorecard 的公開引用，並刪除 `docs/top-company-readiness-plan.md`，避免把內部投遞策略放進對外作品文件。
  - 將大廠 100 分差距改記在 `findings.md` 作為內部作戰策略。
- 內部嚴格評分：
  - Java backend：86 / 100。
  - AI application：84 / 100。
  - Full-stack：82 / 100。
- 內部下一步路線：
  - Java backend 最高槓桿：performance/query evidence、concurrency/failure-mode proof、transaction sequence diagrams。
  - Full-stack 最高槓桿：Playwright E2E seeded demo flows、accessibility/responsive checks、frontend API/data-flow writeup。
  - AI application 最高槓桿：AI eval summary、failure taxonomy、latency/cost/observability notes、retrieval quality report。
- 對外文件原則：
  - README / release boundary / scorecard 只放成熟、正向、可驗證的 reviewer-facing artifacts。
  - 內部打分、投遞策略、殘酷缺口評估只留在 planning files，不放作品集入口。

### 階段 40：ER model evidence
- **狀態：** complete
- **完成時間：** 2026-06-21T00:10:00+08:00
- 執行的操作：
  - 回應使用者詢問是否應放 ER model 設計圖。
  - 決策：放，但只放面試高訊號的 booking operations ER，不畫全資料庫大圖。
  - 盤點 `tb_booking`、`tb_booking_incident`、`tb_booking_deposit_adjustment`、`tb_booking_refund_reconciliation_event`、`tb_merchant_shop`、`tb_booking_slot_inventory`、`tb_merchant_notification_dispatch` schema。
  - 新增 `docs/er-model-booking-operations.md`，包含 Mermaid ER diagram 與面試 talking points。
  - 輸出 ER model PNG，並用視覺檢查修正表名截斷與 label 重疊。
  - 更新 demo evidence package、recording script、release verifier，並重產 GIF preview 讓 ER model 也出現在預覽中。
- 產出：
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/10-er-model-booking-operations.png`
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/00-bytebites-evidence-walkthrough.gif`，約 11.01 秒、1.4MB，已包含 ER model。
- 下一步評估：
  - 錄影時 ER model 放在 architecture 後面，用 10-15 秒講清楚即可。
  - 面試若追問，就展開 `booking_code` workflow key、incident single pending proposal tradeoff、deposit adjustment 與 refund audit 的分離。

### 階段 39：Recording script polish and GIF preview
- **狀態：** complete
- **完成時間：** 2026-06-20T23:59:00+08:00
- 執行的操作：
  - 重新閱讀 `docs/demo-recording-script.md` 與 `docs/demo-evidence-package.md`。
  - 判斷原稿方向正確，但較像大綱；補上可直接照念的繁中 3 分鐘逐字稿。
  - 使用既有 evidence screenshots 產出短 GIF preview，不再為 GIF 重新啟動服務或改 demo state。
  - 更新 evidence package，明確列出 GIF preview 檔名與用途。
- 產出：
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/00-bytebites-evidence-walkthrough.gif`，約 10.63 秒、1.2MB。
- 驗證：
  - `git diff --check` 通過。
  - `scripts/release-readiness.sh --offline` 通過。
- 建立/修改的檔案：
  - `docs/demo-recording-script.md`
  - `docs/demo-evidence-package.md`
  - `task_plan.md`
  - `progress.md`
- 下一步評估：
  - 進入實際錄影；建議先錄 3 分鐘版本，不要先追求 5 分鐘完美版。
  - GIF 可放在作品集頁面或 README 外部展示，但正式面試仍以使用者親自講解的影片為主。

### 階段 38：Remaining evidence screenshots
- **狀態：** complete
- **完成時間：** 2026-06-20T23:50:00+08:00
- 執行的操作：
  - 補齊 Phase 37 尚未完成的 evidence screenshots：LINE rescue/proposal card、refund operations digest、CI、clean migration smoke、architecture overview。
  - 透過本機 Web / Java / AI stack 建立 refund failed adjustment demo state，讓商家後台顯示 refund operations digest。
  - 製作 LINE card preview PNG，來源是 Java incident proposal payload；此圖應說成 LINE Flex card preview，不應說成手機實機截圖。
  - 以 `gh run list --workflow "Portfolio CI" --limit 3` 記錄最新 Portfolio CI 綠燈。
  - 執行 live `scripts/smoke-clean-mysql-migrations.sh --timeout 180`，確認空 MySQL schema 可跑 Flyway 並啟動 Java health UP。
  - 在 refund digest evidence capture 過程中發現 MySQL collation mismatch，新增 V52 migration 修正 `tb_booking_deposit_adjustment.booking_code` collation。
- 截圖輸出：
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/05-line-rescue-card.png`：LINE rescue/proposal Flex card preview。
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/06-refund-operations-digest.png`：Merchant refund operations digest 主證據。
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/07-ci-portfolio-green.png`：Portfolio CI 綠燈證據。
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/08-clean-migration-smoke.png`：clean MySQL migration smoke 通過證據。
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/09-architecture-overview.png`：架構總覽證據。
- 驗證：
  - `scripts/smoke-clean-mysql-migrations.sh --timeout 180` 通過：`PASS Java booted from clean MySQL schema and health is UP.`
  - `gh run list --workflow "Portfolio CI" --limit 3` 顯示最近三次 Portfolio CI 皆為 `completed success`。
  - `scripts/release-readiness.sh --offline` 通過，包含 release boundary、data-quality、Nginx、clean migration workflow、smoke dry-runs。
  - `scripts/verify-portfolio.sh` 通過：Java 96 tests / 0 failures / 3 skipped；AI 174 passed；ETL 43 passed；Web tests 19 passed；Next production build passed。
- 建立/修改的檔案：
  - `backend-java/src/main/resources/db/migration/V52__align_deposit_adjustment_booking_code_collation.sql`
  - `scripts/verify-release-boundary.py`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
  - `docs/demo-evidence-package.md`
  - `docs/demo-recording-script.md`
- 下一步評估：
  - 目前不建議再加新功能；應由使用者親自錄製 3-5 分鐘 voiceover walkthrough。
  - GIF 仍是可選補充，最多做 1 個短片段：AI prompt -> recommendation cards，或 My Bookings accept/decline proposal。
  - 若要繼續工程化，下一個大方向才是 stable demo cloud；production SaaS 仍需真實 PSP refund provider、managed secrets、observability、backup/restore、operations policy。

### 階段 37：Screenshot evidence capture
- **狀態：** complete
- 執行的操作：
  - 回應使用者詢問是否可以協助截圖、以及是否應做功能演示 GIF。
  - 判斷：使用者自己錄影是正確分工；本輪先由 Codex 用真實瀏覽器協助截圖，GIF 只作為少數互動流程的可選補充。
  - 讀取 `docs/demo-recording-script.md`、`docs/demo-evidence-package.md`、`docs/demo-recording-cloud-plan.md` 與 Web package scripts。
  - 執行 `scripts/demo-readiness.sh --base-url http://localhost:8088`，確認目前 Web/Java/AI/Nginx 都未啟動，需要先啟動本機服務再截圖。
  - 啟動 Web dev server、Java backend、AI service；Java sandbox 啟動因 MySQL socket 權限失敗後，改用 escalated `mvn spring-boot:run` 成功。
  - 查明本機 `hmdp` schema 缺 demo merchant ownership、bookings、incidents、adjustments；用本機 capture seed 啟用 `10009` / `10022`，補 `tb_merchant_shop` demo ownership，並將 demo user 綁定本機 LINE identity。
  - 透過 Java API 建立 booking `BK-5C93D20A-946`、demo pay-test 付款、customer late incident，以及 merchant proposal。
  - 使用 Playwright 真實瀏覽器捕捉並人工檢查截圖品質。
- 截圖輸出：
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/01-ai-recommendation-cards.png`：AI 推薦卡主證據。
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/02-booking-payment-incident.png`：My Bookings 已付款訂位、latest incident、pending proposal 主證據。
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/04-merchant-proposal.png`：Merchant console incident proposal 主證據。
  - `/Users/kevinlintingwei/projects/output/playwright/demo-evidence/00-homepage-product-thesis.png`、`01-ai-page-initial.png`、`01-ai-recommendation.png` 可作輔助素材。
  - `02-my-bookings-current.png`、`04-merchant-current.png` 是未 seeded 空狀態，不建議放正式作品集。
- 後續規劃評估：
  - 使用者自己錄影是正確主線；截圖可放作品集或簡報。
  - GIF 暫不優先。若要補，最多做 1-2 個短 GIF：`AI prompt -> recommendation cards` 或 `My Bookings 接受/拒絕 incident proposal`。
  - 下一步應補 `05-line-rescue-card.png`、`06-refund-operations-digest.png`、`07-ci-portfolio-green.png`、`08-clean-migration-smoke.png`、`09-architecture-overview.png`，再開始正式錄影。

### 階段 36：Recording script and shot plan
- **狀態：** complete
- 執行的操作：
  - 回應使用者要求開始做錄影素材與講稿。
  - 新增 `docs/demo-recording-script.md`，提供錄影目標、5 分鐘 walkthrough、3 分鐘短版、12 分鐘面試版、截圖拍攝順序、錄影 checklist、opening lines、closing lines。
  - 將 recording script 接進 README fast links、`docs/demo-evidence-package.md`、`docs/demo-recording-cloud-plan.md`、`docs/portfolio-100-roadmap.md`、`docs/portfolio-readiness-scorecard.md`、`docs/release-boundary.md`。
  - 擴充 `scripts/verify-release-boundary.py`，檢查 recording script 的講稿版本、截圖順序、錄影 checklist 和 live smoke command。
  - `python3 scripts/verify-release-boundary.py` 通過。
  - `git diff --check` 通過。
  - `scripts/release-readiness.sh --offline` 通過，包含 whitespace、Nginx contract、clean migration workflow、release boundary、data-quality evidence、smoke script syntax/dry-runs；Markdown reviewer-facing links 44 passed。
  - `scripts/verify-portfolio.sh` 通過：Java 96 tests / 0 failures / 3 skipped，AI 174 passed，ETL 43 passed，data-quality gate passed，Nginx deployment template contract passed，clean MySQL migration smoke/workflow contracts passed，release boundary contract passed，Web tests 19 passed，Web production build passed。
- 後續規劃評估：
  - 完成這輪後，下一步才是實際啟動 local demo stack，依講稿拍攝 screenshots 與錄製 walkthrough。

### 階段 35：Recording and cloud rollout decision
- **狀態：** complete
- 執行的操作：
  - 回應使用者是否應自己錄影、是否需要上雲、以及 managed secrets / PSP refund provider / backups / observability / operations 是否都要完成的問題。
  - 決策：先錄製作者親自 voiceover 的 3-5 分鐘 walkthrough，再做 screenshots evidence package；stable demo cloud 是加分項，不應阻塞 portfolio packaging。
  - 新增 `docs/demo-recording-cloud-plan.md`，把錄影、上雲、production hardening 拆成 recommended order、cloud levels、production hardening triage 與 interview answer。
  - 更新 `docs/portfolio-100-roadmap.md`，將 recording/cloud plan 放進 Path To Portfolio 100。
  - 更新 `docs/demo-evidence-package.md`，明確指出作者應親自錄製 voiceover，並連到 recording/cloud plan。
  - 更新 README、`docs/portfolio-readiness-scorecard.md`、`docs/release-boundary.md`、`scripts/verify-release-boundary.py`、`task_plan.md`、`findings.md`。
  - `python3 scripts/verify-release-boundary.py` 通過。
  - `git diff --check` 通過。
  - `scripts/release-readiness.sh --offline` 通過，包含 whitespace、Nginx contract、clean migration workflow、release boundary、data-quality evidence、smoke script syntax/dry-runs；Markdown reviewer-facing links 43 passed。
  - `scripts/verify-portfolio.sh` 通過：Java 96 tests / 0 failures / 3 skipped，AI 174 passed，ETL 43 passed，data-quality gate passed，Nginx deployment template contract passed，clean MySQL migration smoke/workflow contracts passed，release boundary contract passed，Web tests 19 passed，Web production build passed。
- 後續規劃評估：
  - 下一步應依 `docs/demo-recording-cloud-plan.md` 先完成錄影與截圖；若還要繼續做工程，才進入 stable demo cloud，不直接跳 production SaaS rollout。

### 階段 34：Portfolio 100 roadmap, evidence package, architecture overview
- **狀態：** complete
- 執行的操作：
  - 回應使用者「每一樣都達到 100 分」的目標，先把 100 分拆成可在 repo 內完成的 Portfolio 100，以及需要外部服務和部署制度的 Production SaaS 100。
  - 新增 `docs/portfolio-100-roadmap.md`，定義目前 88/100 到 portfolio 100 的缺口與 production 100 的真實後續路線。
  - 新增 `docs/demo-evidence-package.md`，列出 AI recommendation、booking/payment、incident、merchant proposal、LINE card、refund digest、CI、clean migration smoke、architecture overview 的截圖/影片證據標準。
  - 新增 `docs/architecture-overview.md`，用 Mermaid 架構圖與 ownership table 說明 AI orchestration、Java source of truth、Web/LINE channel、ETL/Qdrant、Nginx public boundary。
  - 將三份文件接進 README fast links、`docs/release-boundary.md`、`docs/portfolio-readiness-scorecard.md` 與 `scripts/verify-release-boundary.py`。
  - `python3 scripts/verify-release-boundary.py` 通過。
  - `git diff --check` 通過。
  - `scripts/release-readiness.sh --offline` 通過，包含 whitespace、Nginx contract、clean migration workflow、release boundary、data-quality evidence、smoke script syntax/dry-runs。
  - `scripts/verify-portfolio.sh` 通過：Java 96 tests / 0 failures / 3 skipped，AI 174 passed，ETL 43 passed，data-quality gate passed，markdown links 42 passed，Nginx deployment template contract passed，clean MySQL migration smoke/workflow contracts passed，release boundary contract passed，Web tests 19 passed，Web production build passed。
- 後續規劃評估：
  - 本輪完成的是「100 分路線與證據 contract」；真正把分數從 88 往 95-100 拉升，下一步要照 `docs/demo-evidence-package.md` 捕捉實際截圖、短影片與最新 CI 結果。

### 階段 33：Portfolio readiness scorecard and next plan
- **狀態：** complete
- 執行的操作：
  - 依目前完整產品面、架構面、驗證面評估作品成熟度，判斷目前已足夠作為 portfolio interview project。
  - 給出總分：Portfolio readiness 88 / 100；角色別評分：Java backend 92、AI application engineer 90、Full-stack engineer 88、Production platform/SRE 72。
  - 新增 `docs/portfolio-readiness-scorecard.md`，集中說明「已足夠面試展示，但尚非 production SaaS rollout」。
  - 在 scorecard 中列出扣分點：demo evidence 分散、production gaps 需精簡答法、缺一眼看懂的架構圖、live demo 依賴本機服務、截圖需聚焦高訊號頁面。
  - 將 scorecard 接到 README fast links、`docs/release-boundary.md` 與 `scripts/verify-release-boundary.py`。
  - 更新 `task_plan.md` Phase 33。
  - `python3 scripts/verify-release-boundary.py` 通過。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 96 tests / 0 failures / 3 skipped，AI 174 passed，ETL 43 passed，data-quality gate passed，Nginx deployment template contract passed，clean MySQL migration smoke/workflow contracts passed，release boundary contract passed，Web tests 19 passed，Web production build passed。
- 後續規劃評估：
  - 下一步最高價值是 evidence package：固定截圖、短影片或 slide deck，而不是再新增產品功能。
  - 若繼續做工程，應先做一張 architecture diagram 與 demo screenshot checklist，讓面試官在 60 秒內看懂深度。

### 階段 32：Portfolio CI taxonomy fixture stabilization
- **狀態：** complete
- 執行的操作：
  - 重新接回 planning files 與 GitHub Actions 狀態，確認手動 `Clean MySQL Migration Smoke` workflow 已成功，但 push-triggered `Portfolio CI` 仍失敗。
  - 定位最新失敗 run `27864782092` 的失敗點在 ETL Pipeline：`tests/test_taxonomy.py` 因 `load_shops()[...]` 對多個 shop id 丟 `KeyError`。
  - 盤點 `.gitignore` 與 `etl-pipeline/data/raw/`，確認本機有 62MB ignored raw corpus，CI checkout 不包含，因此本機 `scripts/verify-portfolio.sh` 和 GitHub Portfolio CI 看到的測試資料不同。
  - 新增 `etl-pipeline/tests/fixtures/taxonomy_shops.json`，提交 6 個 taxonomy critical fixture：10099、10104、10171、10181、10183、10190。
  - 更新 `etl-pipeline/tests/test_taxonomy.py`：`load_shops()` 先載入 committed fixture，再用 raw corpus 覆寫；完整 103 筆 approval map 若缺 raw corpus 會明確 skip；新增 committed fixture smoke test 永遠在 CI 跑。
  - `cd etl-pipeline && uv run pytest tests/test_taxonomy.py -q` 通過：33 passed。
  - 暫時隱藏 ignored raw corpus 模擬 CI checkout，`uv run pytest tests/test_taxonomy.py -q` 通過：32 passed, 1 skipped。
  - `cd etl-pipeline && UV_CACHE_DIR=../.uv-cache uv run pytest tests -q` 通過：43 passed。
  - 暫時隱藏 ignored raw corpus 模擬 CI checkout，`uv run pytest tests -q` 通過：42 passed, 1 skipped。
  - `scripts/release-readiness.sh --offline` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 96 tests / 0 failures / 3 skipped，AI 174 passed，ETL 43 passed，data-quality gate passed，Nginx deployment template contract passed，clean MySQL migration smoke/workflow contracts passed，release boundary contract passed，Web tests 19 passed，Web production build passed。
  - commit `252f44c fix: stabilize taxonomy tests in ci` 推上 `main` 後，新的 Portfolio CI run `27867881647` 顯示 ETL / AI / Data Gate / Web 全部通過，taxonomy fixture 修正有效。
  - 同一輪 CI 轉為 Backend Java failure，根因是 `BookingSyncContractTest` 的 proposal expiry fixture 使用無時區 `LocalDateTime.now()`，在 UTC hosted runner 上會被 production `Asia/Taipei` business clock 判定已逾期。
  - 更新 `BookingSyncContractTest`，讓 proposal future/expired fixtures 與 booking date 都使用 `ZoneId.of("Asia/Taipei")`。
  - `TAPPAY_PARTNER_KEY=test TAPPAY_MERCHANT_CREDITCARD=test mvn -Dtest=BookingSyncContractTest test` 通過：12 tests / 0 failures。
  - `TAPPAY_PARTNER_KEY=test TAPPAY_MERCHANT_CREDITCARD=test mvn test` 通過：96 tests / 0 failures / 3 skipped。
  - commit `f2a8956 fix: use business timezone in booking tests` 推上 `main` 後，Portfolio CI run `27867984528` 通過：Backend Java、AI Service Python、ETL Pipeline、Data Quality Gate、Web 全部成功。
- 後續規劃評估：
  - 短期優先保持 release boundary，不再立即堆新功能；下一步適合做 demo evidence packaging，例如固定 demo script、截圖、面試講稿與 production-gap checklist。
  - 中期若要繼續深化產品，優先做「production observability / release operations」而不是新餐廳推薦功能，因為目前作品已經有完整 incident、付款、退款、LINE、Nginx、CI 敘事，缺的是公開展示時的可操作證據包。

### 階段 31：Release boundary and final handoff
- **狀態：** complete
- 執行的操作：
  - 判斷目前專案下一步應收斂 release boundary，而不是再堆新 feature；核心風險是命令、gate、live smoke、commit grouping 和 production gaps 分散。
  - 新增 `docs/release-boundary.md`，集中說明 release thesis、verification ladder、release readiness script、commit grouping、demo script 與 production gaps。
  - 新增 `scripts/release-readiness.sh`，支援 `--dry-run`、`--offline`、`--full`、`--live-local` 與 `--base-url`。
  - `--offline` 會跑 whitespace、Nginx contract、clean migration workflow contract、release boundary contract、data-quality evidence、smoke script syntax 與 dry-runs。
  - `--full` 會跑 `scripts/verify-portfolio.sh`；`--live-local` 會跑 clean MySQL migration smoke 與 strict Nginx public-proxy live smoke。
  - 新增 `scripts/verify-release-boundary.py`，離線檢查 release boundary 文件與 readiness script 的核心命令、模式與 production-gap framing。
  - 將 `verify-release-boundary.py` 接進 `scripts/verify-portfolio.sh`。
  - 更新 README fast links / verification table、portfolio evidence map、case study 14 與 `scripts/verify-data-quality.py` evidence anchors。
  - `python3 scripts/verify-release-boundary.py` 通過。
  - `scripts/release-readiness.sh --dry-run` 通過。
  - `scripts/release-readiness.sh --offline` 通過。
  - `python3 scripts/verify-data-quality.py` 通過。
  - `git diff --check` 通過。

### 階段 30：GitHub Actions clean migration smoke workflow
- **狀態：** complete
- 執行的操作：
  - 盤點 `.github/workflows/portfolio-ci.yml` 與 `backend-java/src/main/resources/application.yaml`，確認 Java live startup 需要 MySQL、Redis、RabbitMQ，且 datasource 可用 `MYSQL_*` env 控制。
  - 新增 `.github/workflows/clean-mysql-migration-smoke.yml`，使用 `workflow_dispatch` 手動觸發，提供 `timeout_seconds` input。
  - workflow 使用 Redis / RabbitMQ GitHub Actions services，另用 `docker run --name bytebites-ci-mysql` 建立已知名稱的 MySQL 8.0 container，讓現有 smoke script 可用 `--mysql-container bytebites-ci-mysql` 操作臨時 DB。
  - workflow 設定 Java 17、Maven cache、TapPay test env，並呼叫 `scripts/smoke-clean-mysql-migrations.sh --timeout ... --java-port 18081`。
  - 新增 `scripts/verify-clean-migration-workflow.py`，離線檢查 workflow 必須是手動觸發、包含 Redis/RabbitMQ/MySQL、使用 Java 17、呼叫同一支 clean migration smoke script，並驗 `bash -n` / dry-run。
  - 將 `verify-clean-migration-workflow.py` 接進 `scripts/verify-portfolio.sh`。
  - 更新 `scripts/verify-data-quality.py`，要求 portfolio evidence map 收錄 `.github/workflows/clean-mysql-migration-smoke.yml`。
  - 更新 README、`docs/deployment-nginx.md`、roadmap、portfolio evidence map、case study 11、case study 14 與 planning 記錄。
  - `python3 scripts/verify-clean-migration-workflow.py` 通過。
  - `python3 scripts/verify-data-quality.py` 通過。
  - `bash -n scripts/verify-portfolio.sh` 通過。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 96 tests / 0 failures / 3 skipped，AI 174 passed，ETL 42 passed，data-quality gate passed，Nginx deployment template contract passed，clean MySQL migration smoke contract passed，clean MySQL migration workflow contract passed，Web tests 19 passed，Web production build passed。

### 階段 29：Clean MySQL migration smoke runner
- **狀態：** complete
- 執行的操作：
  - 延續 Phase 28 的 V16 clean DB failure，選定下一步為 clean MySQL migration smoke runner，而不是再加產品功能。
  - 新增 `scripts/smoke-clean-mysql-migrations.sh`，支援 `--mysql-container`、`--database`、`--java-port`、`--timeout`、`--keep-database`、`--dry-run` 與 `LOG_FILE` 覆寫。
  - 腳本 live mode 會在 local MySQL container 建立臨時 DB，用 `MYSQL_DATABASE` 與臨時 `SERVER_PORT` 啟動 Java，等待 `/actuator/health` 回 `UP`，最後停止 Java 並刪除臨時 DB。
  - 修正 dry-run 不應建立暫存 log 檔，讓 portfolio gate 保持零副作用。
  - 修正 macOS/BSD `mktemp` 相容性，避免 `.log` suffix 模板不被替換。
  - 將 `bash -n scripts/smoke-clean-mysql-migrations.sh` 與 `scripts/smoke-clean-mysql-migrations.sh --dry-run` 接進 `scripts/verify-portfolio.sh`。
  - 更新 README、`docs/deployment-nginx.md`、roadmap、portfolio evidence map、case study 11、case study 14 與 planning 記錄。
  - 第一次 live smoke 在 sandbox 內被 Docker daemon socket 權限擋下；改用 escalated execution 後通過。
  - `scripts/smoke-clean-mysql-migrations.sh --timeout 180` 通過：Java 從臨時乾淨 MySQL schema 跑完 Flyway 並 health UP。
  - 收尾確認 `18081` 無殘留 listener，`bytebites_migration_smoke_%` database 無殘留。
  - `mvn -Dtest=TaxonomyMigrationResourceTest test` 通過，2 tests / 0 failures。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 96 tests / 0 failures / 3 skipped，AI 174 passed，ETL 42 passed，data-quality gate passed，Nginx deployment template contract passed，clean MySQL migration smoke contract passed，Web tests 19 passed，Web production build passed。

### 階段 28：正式 demo rehearsal
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、progress.md 並執行 session-catchup。
  - 新增 task_plan Phase 28，目標是實際啟動 demo stack 並跑 `scripts/demo-readiness.sh --live-smoke --strict`。
  - 初次 live preflight 通過部署檔與 Docker Compose public-proxy config，但 Web `:3000`、Java `:8081`、AI `:8000`、Nginx `:8088` 均未啟動；目前 `deploy` compose 只看到 Prometheus/Grafana。
  - 啟動 `rabbitmq` / `qdrant`；Web `npm run dev -- --port 3000` 成功；AI 首次因 `~/.cache/uv` sandbox 權限失敗，改用 escalated `uv run uvicorn` 成功。
  - Java 首次因 sandbox 阻擋 MySQL socket 失敗，改用 escalated `mvn spring-boot:run` 後連到 MySQL，但發現本機 MySQL 缺 `hmdp` schema。
  - 在 local MySQL container 建立 `hmdp` schema，Java/Flyway 開始從乾淨 DB 套 migrations。
  - Flyway 在 `V16__taxonomy_backfill.sql` 因 `tb_shop_badge` FK failure 失敗；修正 V16 badge/tag backfill，改成 derived allowlist join `tb_shop`，只對存在店家回填。
  - 清掉本機 `flyway_schema_history` 中剛才 failed 的 V16 row，重新啟動 Java；Flyway 成功套到 V51，Java health 回 `{"status":"UP"}`。
  - 新增 `TaxonomyMigrationResourceTest.v16BackfillOnlyAssignsBadgesAndTagsToExistingShops`，防止 V16 回歸成直接硬插不存在 shop id。
  - 啟動 Nginx public-proxy overlay；第一次 sandbox 直接跑 strict readiness false negative，因腳本內 curl 被 sandbox 擋住；直接 curl 四個 endpoint 均成功。
  - 使用 escalated `scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict` 完成正式彩排：Web root、Java health、AI health、Nginx health routes、LINE webhook check、LINE Login redirect/cookie path、AI SSE start frame 全部 PASS。
  - `mvn -Dtest=TaxonomyMigrationResourceTest test` 通過，2 tests / 0 failures。
  - `git diff --check` 通過。
  - `python3 scripts/verify-nginx-template.py` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 96 tests / 0 failures / 3 skipped，AI 174 passed，ETL 42 passed，data-quality gate passed，Nginx deployment template contract passed，Web tests 19 passed，Web production build passed。

### 階段 27：Demo readiness preflight runner
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 評估四個候選下一步：live smoke、demo readiness preflight、HTTPS/雲端、回到產品功能。
  - 選定 preflight runner：延續 Nginx deployment 主線，把 demo 前人工 checklist 變成一條命令；不自動啟動或殺服務，只檢查並提示下一步。
  - 新增 `scripts/demo-readiness.sh`，支援 `--base-url`、`--live-smoke`、`--strict`、`--dry-run`；檢查必要部署檔、Docker Compose public-proxy config、Web/Java/AI/Nginx public proxy health，並在服務未啟動時印出下一步命令。
  - 更新 `docs/deployment-nginx.md`、README、web README、roadmap、portfolio evidence map 與 case study 11，將 readiness preflight 放進 demo rehearsal path。
  - 擴充 `scripts/verify-nginx-template.py`，檢查 readiness script contract、`bash -n` 與 dry-run。
  - 第一次 targeted verifier 發現 readiness script 忽略環境變數 `DRY_RUN=true`，導致 verifier 仍打 localhost；改成 `DRY_RUN` / `STRICT` / `LIVE_SMOKE` 可由環境變數覆寫後通過。
  - `bash -n scripts/demo-readiness.sh` 通過。
  - `scripts/demo-readiness.sh --dry-run` 通過。
  - `python3 scripts/verify-nginx-template.py` 通過。
  - `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.nginx.yml --profile public-proxy config` 通過。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 95 tests / 0 failures / 3 skipped，AI 174 passed，ETL 42 passed，data-quality gate passed，Nginx deployment template contract passed，Web tests 19 passed，Web production build passed。

### 階段 26：Nginx public-proxy smoke test runner
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 盤點 `scripts/demo-keepalive.sh`、AI `/api/ai/agent/stream`、AI `/api/line/webhook`、Java LINE Login redirect/cookie 行為，以及現有 deployment smoke docs。
  - 選定本輪最小部署驗證：新增短命令 smoke script，服務啟動後可一鍵驗證 Nginx public proxy routes；portfolio gate 只做語法與 dry-run，不要求 live services。
  - 新增 `scripts/smoke-nginx-public-proxy.sh`，支援 `--base-url`、`--skip-stream`、`--dry-run`，檢查 Web root、Java health、AI health、LINE webhook、LINE Login redirect/cookie path、AI SSE start frame。
  - 更新 `docs/deployment-nginx.md`，將 smoke runner 放在 Smoke Checks 首選路徑，manual curl 保留為 fallback。
  - 更新 README、web README、roadmap、portfolio evidence map 與 case study 11。
  - 擴充 `scripts/verify-nginx-template.py`，新增 smoke script contract 檢查、`bash -n` 與 dry-run。
  - 第一次 targeted check 發現 `scripts/smoke-nginx-public-proxy.sh` bash syntax error；修正預設 stream query 和 Location header parsing 後，`bash -n` 與 dry-run 通過。
  - `python3 scripts/verify-nginx-template.py` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 95 tests / 0 failures / 3 skipped，AI 174 passed，ETL 42 passed，data-quality gate passed，Nginx deployment template contract passed，Web tests 19 passed，Web production build passed。
  - `git diff --check` 通過。

### 階段 25：Nginx Docker Compose public-proxy overlay
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 盤點 root `docker-compose.yml`、`deploy/docker-compose.yml`、`deploy/nginx/bytebites.conf.template`、`docs/deployment-nginx.md` 與 `scripts/verify-nginx-template.py`。
  - 選定本輪最小部署縱切：新增 Nginx Docker Compose overlay，讓現有 host 上的 Web/Java/AI dev processes 可透過 containerized Nginx public-proxy 演練。
  - 新增 `deploy/docker-compose.nginx.yml`，以 `public-proxy` profile 啟動 `bytebites-nginx`，預設 `localhost:8088` 對外、`host.docker.internal` 代理 Web/Java/AI。
  - 更新 `docs/deployment-nginx.md`，加入 Compose overlay 啟動、config 驗證、停止 proxy、local smoke checks 與 HTTPS/LINE 注意事項。
  - 更新 README、web README、roadmap、portfolio evidence map 與 case study 11。
  - 擴充 `scripts/verify-nginx-template.py`，同時檢查 Nginx template、Compose overlay 與部署文件 contract。
  - `python3 scripts/verify-nginx-template.py` 通過。
  - `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.nginx.yml config` 通過，但因 profile 未啟用而不顯示 nginx；確認後改用帶 profile 的 config。
  - `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.nginx.yml --profile public-proxy config` 通過，輸出包含 nginx service、8088 port、host upstream 與 template mount。
  - `scripts/verify-portfolio.sh` 通過：Java 95 tests / 0 failures / 3 skipped，AI 174 passed，ETL 42 passed，data-quality gate passed，Nginx deployment template contract passed，Web tests 19 passed，Web production build passed。
  - `git diff --check` 通過。

### 階段 24：Nginx stable public deployment boundary
- **狀態：** complete
- 執行的操作：
  - 重新盤點 `web/next.config.ts`、LINE Login/AuthController 路徑、AI LINE webhook/action pages、demo deployment case study 與 verification script。
  - 判斷不應把 ngrok 直接替換掉；保留 ngrok 作為 local temporary demo，新增 Nginx 作為 stable public / production-like entrypoint。
  - 新增 `deploy/nginx/bytebites.conf.template`，固定 `/api/java`、`/api/python`、`/api/ai`、`/api/line`、`/line`、`/health/java`、`/health/ai` 路由。
  - 新增 `docs/deployment-nginx.md`，記錄 LINE callback/webhook、Web/Java/AI env、refund source allowlist behind proxy、smoke checks。
  - 新增 `scripts/verify-nginx-template.py`，離線檢查 template 與 docs 是否保留必要 route/header/env contract。
  - 將 Nginx template verifier 接進 `scripts/verify-portfolio.sh`。
  - 同步 README、web README、roadmap、portfolio evidence map、case study 11 與 case study index。
  - `python3 scripts/verify-nginx-template.py` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 95 tests / 0 failures / 3 skipped，AI 174 passed，ETL 42 passed，data-quality gate passed，Nginx deployment template contract passed，Web tests 19 passed，Web production build passed。
  - `git diff --check` 初次抓到 case study Tech 行 trailing whitespace；修正後重跑通過。

### 階段 23：退款 callback source validation / PSP allowlist
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 選定本輪最小 production hardening slice：refund callback source validation / PSP allowlist。
  - 更新 task_plan.md / findings.md / progress.md，將 Phase 23 設為進行中。
  - `PaymentController` 新增 `bytebites.refund.webhook.allowed-sources`、`trusted-proxies`、`source-header` 設定。
  - refund reconciliation callback 在 allowlist 未設定時保留 demo 行為；設定 allowlist 後會驗證 direct remote address 或 trusted proxy forwarded source。
  - source rule 支援 exact IP 與 IPv4 CIDR；forwarded header 只有在 remote address 命中 trusted proxy 時才採用。
  - `application.yaml` 新增 REFUND_WEBHOOK_SECRET / PREVIOUS_SECRET / ALLOWED_SOURCES / TRUSTED_PROXIES / SOURCE_HEADER 環境變數映射。
  - `PaymentSyncContractTest` 補上 direct allowed source、trusted proxy forwarded source、untrusted forwarded spoofing tests。
  - `mvn -Dtest=PaymentSyncContractTest test` 通過，10 tests / 0 failures。
  - `mvn -Dtest=PaymentSyncContractTest,BookingDepositAdjustmentServiceTest,MerchantControllerTest test` 通過，44 tests / 0 failures。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest,LineNotificationClientTest test` 通過，61 tests / 0 failures。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 95 tests / 0 failures / 3 skipped，AI 174 passed，ETL 42 passed，Web tests 19 passed，Web production build passed。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/controller/PaymentController.java
  - backend-java/src/main/resources/application.yaml
  - backend-java/src/test/java/com/bytebites/controller/PaymentSyncContractTest.java
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 22：退款 operations digest scheduled policy
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 選定本輪最小 scheduled policy slice：提供 scheduler 可呼叫的 due 判斷與 dispatch-if-due contract。
  - 更新 task_plan.md / findings.md / progress.md，將 Phase 22 設為進行中。
  - 新增 `tb_merchant_notification_dispatch`，記錄 merchant notification dispatch audit 與 successful sent timestamp。
  - `BookingDepositAdjustmentService` 新增 refund operations notification policy，回傳 shouldNotify、reason、cooldown、lastSentAt、nextEligibleAt，並提供 dispatch audit 寫入。
  - `MerchantController` 新增 `/refund-report/notification-policy` 與 `/refund-report/dispatch-due`，manual notify 不受 cooldown 影響，scheduled dispatch 會依 policy 跳過或推送 LINE digest。
  - Web API wrapper 與商家後台新增排程通知政策狀態與「執行排程判斷」操作。
  - `mvn -Dtest=MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，34 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest,LineNotificationClientTest test` 通過，58 tests / 0 failures。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 92 tests / 0 failures / 3 skipped，AI 174 passed，ETL 42 passed，Web tests 19 passed，Web production build passed。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/resources/db/migration/V51__merchant_notification_dispatch.sql
  - backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/test/java/com/bytebites/service/BookingDepositAdjustmentServiceTest.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - web/lib/api.ts
  - web/app/merchant/page.tsx
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 21：退款 operations digest notification
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 選定本輪最小 notification slice：refund operations digest 可被手動或未來 scheduler 觸發通知。
  - 更新 task_plan.md / findings.md / progress.md，將 Phase 21 設為進行中。
  - `LineNotificationClient` 新增 `/internal/line/refund-operations-digest` push payload。
  - `MerchantController` 新增 `/shops/{shopId}/deposit-adjustments/refund-report/notify`，使用商家帳號的 LINE identity link；沒有 LINE 綁定或沒有退款異常時回傳 skipped。
  - AI service 新增 internal refund operations digest endpoint 與 Flex card，顯示建議動作、統計與重點退款項目。
  - Web API wrapper 與商家後台新增「發送 LINE 摘要」操作。
  - `mvn -Dtest=MerchantControllerTest,LineNotificationClientTest,BookingDepositAdjustmentServiceTest test` 通過，33 tests / 0 failures。
  - `uv run --no-sync pytest tests/test_line_recommendation_fallback.py -q` 通過，121 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest,LineNotificationClientTest test` 通過，52 tests / 0 failures。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 86 tests / 0 failures / 3 skipped，AI 174 passed，ETL 42 passed，Web tests 19 passed，Web production build passed。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/main/java/com/bytebites/service/LineNotificationClient.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - backend-java/src/test/java/com/bytebites/service/LineNotificationClientTest.java
  - ai-service-python/app/main.py
  - ai-service-python/tests/test_line_recommendation_fallback.py
  - web/lib/api.ts
  - web/app/merchant/page.tsx
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 20：退款 escalation report / operations digest
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 選定本輪最小 operations slice：refund escalation report / operations digest。
  - 更新 task_plan.md / findings.md / progress.md，將 Phase 20 設為進行中，驗證後收斂為完成。
  - `BookingDepositAdjustmentService` 新增 merchant scoped refund operations report，重用 refund SLA attention items，拆分 pending escalation 與 escalated follow-up。
  - `MerchantController` 新增 `/shops/{shopId}/deposit-adjustments/refund-report`，沿用店家 ownership 檢查。
  - Web API wrapper 新增 `MerchantRefundOperationsReport` 與 `merchantRefundReport`。
  - 商家後台在退款 SLA band 下方顯示 operations digest、建議動作、未升級/已升級/失敗/逾時統計，以及最需要處理的退款項目。
  - `mvn -Dtest=BookingDepositAdjustmentServiceTest,MerchantControllerTest test` 通過，26 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，45 tests / 0 failures。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 83 tests / 0 failures / 3 skipped，AI 172 passed，ETL 42 passed，Web tests 19 passed，Web production build passed。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/test/java/com/bytebites/service/BookingDepositAdjustmentServiceTest.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - web/lib/api.ts
  - web/app/merchant/page.tsx
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 19：退款 webhook secret rotation
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 選定本輪最小 production hardening：refund webhook current/previous secret rotation。
  - 更新 task_plan.md / findings.md / progress.md，將 Phase 19 設為進行中，驗證後收斂為完成。
  - `PaymentController` 新增 `bytebites.refund.webhook.previous-secret` 設定。
  - refund callback signature validation 會接受 current 或 previous secret 任一 HMAC；設定任一 secret 時仍要求 fresh timestamp，無 secret 時保留 demo callback。
  - `PaymentSyncContractTest` 補上 previous secret 輪替期間可接受 callback 的 contract test。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=PaymentSyncContractTest,BookingDepositAdjustmentServiceTest test` 通過，21 tests / 0 failures。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，43 tests / 0 failures。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過：Java 81 tests / 0 failures / 3 skipped，AI 172 passed，ETL 42 passed，Web tests 19 passed，Web production build passed。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/controller/PaymentController.java
  - backend-java/src/test/java/com/bytebites/controller/PaymentSyncContractTest.java
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 18：退款 escalation / follow-up tracking
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 選定本輪最小 operational follow-up：failed/stuck refund escalation tracking。
  - 更新 task_plan.md / findings.md / progress.md，將 Phase 18 設為進行中。
  - 新增 `V50__booking_refund_escalation.sql`，在 `tb_booking_deposit_adjustment` 記錄 refund escalation 時間、備註與處理人。
  - `BookingDepositAdjustmentService` 新增 `escalateRefundForMerchantShop`，只允許 OPEN REFUND 且 settlement 為 FAILED / PROCESSING 時升級。
  - escalation 操作會寫入 `REFUND_ESCALATED` audit event，並在 adjustment payload / refund SLA summary 中回傳 escalation 狀態。
  - `MerchantController` 新增 `/shops/{shopId}/deposit-adjustments/{adjustmentId}/refund/escalate`，沿用 merchant shop ownership 檢查。
  - Web API wrapper 新增 escalation 欄位與 `escalateMerchantDepositAdjustmentRefund`。
  - 商家後台退款卡片可輸入升級備註並標記「升級處理」；已升級項目會顯示時間與備註，SLA band 顯示尚未升級件數。
  - 補 Java service/controller tests，涵蓋 escalation 欄位更新、audit event 與 owned-shop endpoint。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=BookingDepositAdjustmentServiceTest,MerchantControllerTest test` 通過，24 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，42 tests / 0 failures。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/resources/db/migration/V50__booking_refund_escalation.sql
  - backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/test/java/com/bytebites/service/BookingDepositAdjustmentServiceTest.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - web/lib/api.ts
  - web/app/merchant/page.tsx
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 17：退款 SLA / stuck refund visibility
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 選定本輪最小 operational hardening：refund SLA summary，聚合 FAILED 與卡在 PROCESSING 的退款。
  - 更新 task_plan.md / findings.md / progress.md，將 Phase 17 設為進行中。
  - `BookingDepositAdjustmentService` 新增 merchant scoped refund SLA summary，查出 OPEN REFUND 中 FAILED 或超過門檻仍 PROCESSING 的項目。
  - `MerchantController` 新增 `/shops/{shopId}/deposit-adjustments/refund-sla`，沿用商家 ownership 檢查。
  - Web API wrapper 新增 `MerchantRefundSlaSummary` 與 `merchantRefundSla`。
  - 商家後台「訂金差額處理」新增 refund SLA 狀態 band；退款請求、對帳回寫與套用改單後會刷新 SLA summary。
  - 補 Java service/controller tests，涵蓋 stuck/failed refund counts 與 owned-shop endpoint。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=BookingDepositAdjustmentServiceTest,MerchantControllerTest test` 通過，22 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，40 tests / 0 failures。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/test/java/com/bytebites/service/BookingDepositAdjustmentServiceTest.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - web/lib/api.ts
  - web/app/merchant/page.tsx
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 16：退款 webhook signature verification
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 選定本輪最小 hardening：refund reconciliation optional HMAC signature verification。
  - `PaymentController` 新增 `bytebites.refund.webhook.secret` 設定；secret 空白時保留 demo callback。
  - secret 設定後，refund callback 必須帶 `X-ByteBites-Webhook-Timestamp` 與 `X-ByteBites-Webhook-Signature`。
  - 簽章 payload 使用 timestamp、固定事件名稱、adjustmentId、bookingCode、amount、status、settlementTransId、eventKey，並用 HMAC-SHA256 驗證。
  - 加入 5 分鐘 timestamp freshness check 與 constant-time signature compare。
  - 補 Java tests，涵蓋 secret 空白可用、valid HMAC 可用、invalid signature 拒絕、expired timestamp 拒絕。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=PaymentSyncContractTest,BookingDepositAdjustmentServiceTest,MerchantControllerTest test` 通過，26 tests / 0 failures。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，38 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/controller/PaymentController.java
  - backend-java/src/test/java/com/bytebites/controller/PaymentSyncContractTest.java
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 15：退款 reconciliation idempotency + audit
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 選定本輪最小 hardening：refund reconciliation event key idempotency + audit trail。
  - 新增 `V49__booking_refund_reconciliation_audit.sql`，建立 refund request / reconciliation audit table。
  - `BookingDepositAdjustmentService` 在退款請求與 reconciliation 寫入 audit event；reconciliation 可用 eventKey 去重，重複事件回傳 `idempotentReplay`。
  - `PaymentController` refund reconciliation callback 支援 `eventKey`。
  - Web API wrapper 支援傳入 optional `eventKey`。
  - 補 Java tests，涵蓋 audit insert、duplicate event key replay、controller eventKey delegation。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=BookingDepositAdjustmentServiceTest,PaymentSyncContractTest,MerchantControllerTest test` 通過，23 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，35 tests / 0 failures。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/resources/db/migration/V49__booking_refund_reconciliation_audit.sql
  - backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java
  - backend-java/src/main/java/com/bytebites/controller/PaymentController.java
  - backend-java/src/test/java/com/bytebites/service/BookingDepositAdjustmentServiceTest.java
  - backend-java/src/test/java/com/bytebites/controller/PaymentSyncContractTest.java
  - web/lib/api.ts
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 14：退款 webhook / reconciliation
- **狀態：** complete
- 執行的操作：
  - 恢復 Phase 13 之後的規劃上下文，確認下一個最高價值切片是 REFUND webhook / reconciliation。
  - 盤點 `BookingDepositAdjustmentService`、`PaymentController`、`MerchantController`、`web/lib/api.ts`、`web/app/merchant/page.tsx` 與相關測試。
  - 確認既有 settlement 欄位可承接 `PROCESSING` / `FAILED`，本輪不新增 migration。
  - `BookingDepositAdjustmentService` 新增 refund request、refund reconciliation、REFUND direct settlement guard。
  - `PaymentController` 新增 demo/internal PSP refund reconciliation callback。
  - `MerchantController` 新增 refund request endpoint，仍沿用 shop ownership 檢查。
  - 商家後台將 REFUND 拆成建立退款請求、對帳成功、標記失敗、重送請求；TOP_UP 仍保留既有 PSP completion path。
  - 補 Java service/controller tests，涵蓋 direct settlement guard、PROCESSING、COMPLETED、FAILED。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=BookingDepositAdjustmentServiceTest,PaymentSyncContractTest,MerchantControllerTest test` 通過，22 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，34 tests / 0 failures。
  - `git diff --check` 通過。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java
  - backend-java/src/main/java/com/bytebites/controller/PaymentController.java
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/test/java/com/bytebites/service/BookingDepositAdjustmentServiceTest.java
  - backend-java/src/test/java/com/bytebites/controller/PaymentSyncContractTest.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - web/lib/api.ts
  - web/app/merchant/page.tsx
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

## 會話：2026-06-19

### 階段 13：顧客補款 checkout link
- **狀態：** complete
- 執行的操作：
  - 重新讀取 planning-with-files-zht、task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 盤點 My Bookings 既有 TapPay iframe payment modal、`PaymentController.payByPrime` 與 `BookingDepositAdjustmentService` settlement contract。
  - 決定本輪只做 customer TOP_UP checkout；REFUND webhook/reconciliation 保留下一輪。
  - `BookingDepositAdjustmentService` 新增 customer TOP_UP list、payable validation 與 customer settlement recording。
  - `PaymentController` 新增 customer top-up list endpoint 與 TapPay pay-by-prime top-up endpoint。
  - My Bookings 新增「待補款改單」區塊，並重用 TapPay iframe modal 完成補款。
  - `mvn -Dtest=BookingDepositAdjustmentServiceTest,PaymentSyncContractTest test` 通過，9 tests / 0 failures。
  - `npm run build:ci` 通過。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，28 tests / 0 failures。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java
  - backend-java/src/main/java/com/bytebites/controller/PaymentController.java
  - backend-java/src/test/java/com/bytebites/service/BookingDepositAdjustmentServiceTest.java
  - backend-java/src/test/java/com/bytebites/controller/PaymentSyncContractTest.java
  - web/lib/api.ts
  - web/app/my-bookings/page.tsx
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 12：訂金差額 PSP settlement tracking
- **狀態：** complete
- 執行的操作：
  - 讀取 planning-with-files-zht 技能說明，恢復 task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 初步盤點付款與訂金相關程式碼，確認既有 booking payment 已有 TapPay pay-by-prime 與 `payment_trans_id`。
  - 決定 Phase 12 先補 deposit adjustment settlement state machine，不直接擴到完整 PSP refund webhook / reconciliation。
  - 新增 V48 migration，準備在 `tb_booking_deposit_adjustment` 上追蹤 settlement status/provider/trans id/amount/timestamps。
  - `BookingDepositAdjustmentService` 新增 settlement completed guard 與 `recordSettlementForMerchantShop`，未完成 PSP settlement 時禁止套用改單。
  - `MerchantController` 新增 adjustment settlement endpoint，商家仍需通過 shop ownership 檢查。
  - 商家後台把訂金差額改成兩步：先記錄 PSP 交易編號，再套用改單。
  - `mvn -Dtest=BookingDepositAdjustmentServiceTest,MerchantControllerTest test` 通過，11 tests / 0 failures。
  - `npm run build:ci` 通過。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，24 tests / 0 failures。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/resources/db/migration/V48__booking_deposit_adjustment_settlement.sql
  - backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/test/java/com/bytebites/service/BookingDepositAdjustmentServiceTest.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - web/lib/api.ts
  - web/app/merchant/page.tsx
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 11：商家手動訂金差額處理
- **狀態：** complete
- 執行的操作：
  - 重新讀取 task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 盤點 `MerchantController`、`BookingRescheduleService`、`web/lib/api.ts` 與 `web/app/merchant/page.tsx`。
  - 決定最小縱切：被訂金 guard 擋下時建立 OPEN adjustment；商家確認外部處理後，Java 以 manual override 套用改單並保留審計資料。
  - 新增 `tb_booking_deposit_adjustment` migration，記錄 TOP_UP / REFUND、來源、原訂金、新訂金、差額、提案目標與處理審計欄位。
  - 新增 `BookingDepositAdjustmentService`，支援建立/更新 OPEN adjustment、商家查詢、商家 resolve 後套用改單。
  - `BookingController` 在 direct reschedule 與 incident proposal acceptance 被 paid-booking deposit delta guard 擋下時建立 adjustment。
  - `MerchantController` 新增商家 adjustment list / resolve endpoints，並維持 shop ownership 檢查。
  - `BookingRescheduleService` 新增 manual handling override，只允許商家確認外部處理後套用原本被 guard 擋下的改單。
  - 商家後台新增「訂金差額處理」區塊，可查看 OPEN adjustment 並標記已處理套用。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=BookingSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test` 通過，20 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/resources/db/migration/V47__booking_deposit_adjustments.sql
  - backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java
  - backend-java/src/main/java/com/bytebites/service/BookingRescheduleService.java
  - backend-java/src/main/java/com/bytebites/controller/BookingController.java
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/test/java/com/bytebites/service/BookingDepositAdjustmentServiceTest.java
  - backend-java/src/test/java/com/bytebites/controller/BookingSyncContractTest.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - web/lib/api.ts
  - web/app/merchant/page.tsx
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 10：訂金政策防護
- **狀態：** complete
- 執行的操作：
  - 重新讀取 task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 盤點 `BookingRescheduleService`、`BookingController`、`DepositPolicy`、`BookingHoldService` 與 `BookingSyncContractTest`。
  - 確認下一個最小優化是 paid booking 的訂金差額 guard：自動改單不處理補款或退款，避免 Java 狀態和實際金流脫節。
  - 在 `BookingRescheduleService` 新增 deposit adjustment evaluation；已付款訂位若改單會增加訂金或產生退款，會在 slot capacity mutation 前失敗並保留原訂位。
  - `BookingController` 成功改單與接受 incident proposal 時回傳 `depositPolicy` metadata。
  - 調整既有成功改期測試為同訂金金額案例，新增 paid booking 訂金加收、退款、incident proposal 繞路防護測試。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=BookingSyncContractTest test` 通過，12 tests / 0 failures。
  - `mvn -Dtest=MerchantControllerTest,BookingSyncContractTest,BookingIncidentServiceTest test` 通過，19 tests / 0 failures。
  - `scripts/verify-portfolio.sh` 通過。
  - 清理 Markdown trailing whitespace，`git diff --check` 通過。
  - trailing whitespace 清理後再次執行 `scripts/verify-portfolio.sh`，確認最後狀態通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/service/BookingRescheduleService.java
  - backend-java/src/main/java/com/bytebites/controller/BookingController.java
  - backend-java/src/test/java/com/bytebites/controller/BookingSyncContractTest.java
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/README.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 9：LINE 替代時段提案卡
- **狀態：** complete
- 執行的操作：
  - 讀取 task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 評估下一步候選：LINE proposal card、deposit-policy handling、更多後台顯示；選擇先做 LINE proposal card，因 proposal 狀態機已完成。
  - BookingLineNotificationService 新增 proposal push，依 incident payload 的 userId 找 linked LINE user。
  - LineNotificationClient 新增 `/internal/line/booking-incident-proposal` webhook client。
  - MerchantController 在 proposal 成功建立並重讀 payload 後推送 LINE proposal notification。
  - AI service 新增 internal LINE proposal endpoint、proposal Flex card、LINE status / my-bookings 頁 pending proposal 區塊，以及 LINE accept/decline 輕量頁。
  - LINE accept/decline 頁面只轉送 lineUserId / lineActionToken 到 Java；真正狀態轉移仍由 BookingController 驗證。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=MerchantControllerTest,BookingLineNotificationServiceTest,LineNotificationClientTest test` 通過，14 tests / 0 failures。
  - `uv run --no-sync pytest tests/test_line_recommendation_fallback.py -q` 通過，119 tests / 0 failures。
  - `scripts/verify-portfolio.sh` 通過；補上 LINE my-bookings 入口後再次通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/main/java/com/bytebites/service/BookingLineNotificationService.java
  - backend-java/src/main/java/com/bytebites/service/LineNotificationClient.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - backend-java/src/test/java/com/bytebites/service/BookingLineNotificationServiceTest.java
  - backend-java/src/test/java/com/bytebites/service/LineNotificationClientTest.java
  - ai-service-python/app/main.py
  - ai-service-python/tests/test_line_recommendation_fallback.py
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 8：替代時段提案拒絕與逾期
- **狀態：** complete
- 執行的操作：
  - 讀取 task_plan.md、findings.md、progress.md 並執行 session-catchup。
  - 評估下一步候選：decline/expiry、LINE proposal card、deposit-policy handling；選擇先補 proposal 狀態機。
  - 新增 V46 migration：proposal_expires_at、proposal_declined_at。
  - MerchantController 建立 proposal 時寫入 30 分鐘有效期限，payload 帶 expiresAt / declinedAt，過期 PENDING 對外投影為 EXPIRED。
  - BookingIncidentService 同步 latestIncident / listIncidents 的 proposedChange 狀態投影。
  - BookingController 新增 customer decline endpoint；accept endpoint 在 transaction 中檢查 expiry，逾期時標記 EXPIRED 並不改單。
  - My Bookings 顯示提案有效期限，並提供接受/拒絕按鈕；merchant console 顯示 pending 有效期限，拒絕或逾期後可重新提案。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=MerchantControllerTest,BookingSyncContractTest,BookingIncidentServiceTest test` 通過，16 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md
  - backend-java/src/main/resources/db/migration/V46__booking_incident_proposal_expiry.sql
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/main/java/com/bytebites/controller/BookingController.java
  - backend-java/src/main/java/com/bytebites/service/BookingIncidentService.java
  - backend-java/src/test/java/com/bytebites/controller/BookingSyncContractTest.java
  - web/lib/api.ts
  - web/app/merchant/page.tsx
  - web/app/my-bookings/page.tsx
  - README.md
  - docs/roadmap.md
  - docs/portfolio-evidence-map.md
  - docs/case-studies/14-portfolio-verification.md

### 階段 7：顧客確認替代時段提案
- **狀態：** complete
- 執行的操作：
  - 讀取 task_plan.md、findings.md、progress.md。
  - 盤點 BookingController reschedule endpoint、MerchantController incident queue、BookingIncidentService latestIncident payload、My Bookings incident display。
  - 決定採單一 pending proposal 欄位：商家提出、顧客接受後才呼叫既有 BookingRescheduleService。
  - 新增 V45 migration：incident proposal 欄位。
  - MerchantController 新增建立 pending proposal endpoint。
  - BookingController 新增 customer accept proposal endpoint，接受後走 BookingRescheduleService。
  - My Bookings 顯示 pending proposal 並提供接受按鈕；Merchant console 可從 suggestion 送出提案。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=MerchantControllerTest,BookingSyncContractTest,BookingIncidentServiceTest test` 通過，14 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - progress.md
  - findings.md
  - backend-java/src/main/resources/db/migration/V45__booking_incident_proposals.sql
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/main/java/com/bytebites/controller/BookingController.java
  - backend-java/src/main/java/com/bytebites/service/BookingIncidentService.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - backend-java/src/test/java/com/bytebites/controller/BookingSyncContractTest.java
  - web/lib/api.ts
  - web/app/merchant/page.tsx
  - web/app/my-bookings/page.tsx

### 階段 6：Alternative Slot Suggestions 最小縱切
- **狀態：** complete
- 執行的操作：
  - 讀取上一輪 task_plan.md、findings.md、progress.md。
  - 確認下一步首選是 alternative slot suggestions。
  - session-catchup 無額外輸出；git status 顯示仍有大量既有未提交變更。
  - 讀取 BookingSlotInventory、BookingRescheduleService、MerchantController、MerchantControllerTest。
  - 在 MerchantController 的 incident payload 中加入 `alternativeSlots`，由 Java 依同店、同日、同桌型、adjustedTime 之後、剩餘座位足夠來計算最多三個建議時段。
  - 商家後台 incident queue 顯示可協調替代時段。
  - `mvn -Dtest=MerchantControllerTest test` 通過，3 tests / 0 failures。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
  - `mvn -Dtest=MerchantControllerTest,BookingIncidentServiceTest test` 通過，6 tests / 0 failures。
  - `npm run build:ci` 通過。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - progress.md
  - backend-java/src/main/java/com/bytebites/controller/MerchantController.java
  - backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java
  - web/lib/api.ts
  - web/app/merchant/page.tsx

### 階段 1：需求與現況盤點
- **狀態：** complete
- **開始時間：** 2026-06-19T00:00:00+08:00
- 執行的操作：
  - 讀取 planning-with-files-zht 技能說明。
  - 檢查專案根目錄與 git 工作樹。
  - 建立本輪規劃檔案。
  - 讀取 README、roadmap、portfolio evidence、case study、BookingIncidentService、my-bookings、AI main、MerchantController、merchant page、api.ts、BookingIncidentServiceTest。
  - 選定商家端 incident console 作為本輪最小縱切。
  - 新增 merchant incident endpoints、Web 商家後台 incident queue、MerchantControllerTest。
  - 同步 README、roadmap、portfolio evidence map、case study 14。
- 測試：
  - `mvn -Dtest=MerchantControllerTest,BookingIncidentServiceTest test` 通過，6 tests / 0 failures。
  - `npm run build:ci` 通過，Next production build completed。
  - `scripts/verify-portfolio.sh` 通過。
- 建立/修改的檔案：
  - task_plan.md
  - findings.md
  - progress.md

## 測試結果
| 測試 | 輸入 | 預期結果 | 實際結果 | 狀態 |
|------|------|---------|---------|------|
| Java targeted tests | MerchantControllerTest, BookingIncidentServiceTest | incident API 與既有 service 通過 | 6 tests, 0 failures | passed |
| Web production build | npm run build:ci | TypeScript/Next build 通過 | build completed | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 46 tests 0 failures 3 skipped; AI 169 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Merchant suggestions targeted test | mvn -Dtest=MerchantControllerTest test | Merchant incident payload 產生可用替代時段 | 3 tests, 0 failures | passed |
| Java incident targeted tests | mvn -Dtest=MerchantControllerTest,BookingIncidentServiceTest test | merchant suggestions 與既有 incident service 通過 | 6 tests, 0 failures | passed |
| Web production build | npm run build:ci | TypeScript/Next build 通過 | build completed | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 46 tests 0 failures 3 skipped; AI 169 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Proposal targeted tests | mvn -Dtest=MerchantControllerTest,BookingSyncContractTest,BookingIncidentServiceTest test | merchant proposal + customer accept + incident service 通過 | 14 tests, 0 failures | passed |
| Web production build | npm run build:ci | proposedChange types and UI compile | build completed | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 48 tests 0 failures 3 skipped; AI 169 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Proposal lifecycle targeted tests | mvn -Dtest=MerchantControllerTest,BookingSyncContractTest,BookingIncidentServiceTest test | proposal accept/decline/expiry + incident service 通過 | 16 tests, 0 failures | passed |
| Web production build | npm run build:ci | proposal decline/expiry UI and API types compile | build completed | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 50 tests 0 failures 3 skipped; AI 169 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| LINE proposal Java targeted tests | mvn -Dtest=MerchantControllerTest,BookingLineNotificationServiceTest,LineNotificationClientTest test | merchant proposal pushes LINE proposal webhook payload | 14 tests, 0 failures | passed |
| LINE proposal AI targeted tests | uv run --no-sync pytest tests/test_line_recommendation_fallback.py -q | LINE proposal Flex card、internal endpoint、status page 通過 | 119 tests, 0 failures | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 52 tests 0 failures 3 skipped; AI 172 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Deposit policy booking contract | mvn -Dtest=BookingSyncContractTest test | paid booking 訂金加收/退款 guard 與 proposal acceptance guard 通過 | 12 tests, 0 failures | passed |
| Deposit policy incident targeted tests | mvn -Dtest=MerchantControllerTest,BookingSyncContractTest,BookingIncidentServiceTest test | merchant proposal + booking sync + incident service 通過 | 19 tests, 0 failures | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 55 tests 0 failures 3 skipped; AI 172 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Whitespace sanity check | git diff --check | 確認 diff 無 trailing whitespace | no output | passed |
| Manual deposit adjustment targeted tests | mvn -Dtest=BookingSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test | blocked paid deposit delta creates merchant adjustment; merchant resolve applies manual override | 20 tests, 0 failures | passed |
| Web production build | npm run build:ci | merchant adjustment queue UI and API types compile | build completed | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 59 tests 0 failures 3 skipped; AI 172 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| PSP settlement targeted tests | mvn -Dtest=BookingDepositAdjustmentServiceTest,MerchantControllerTest test | settlement record endpoint and completed guard 通過 | 11 tests, 0 failures | passed |
| Web production build | npm run build:ci | settlement UI and API types compile | build completed | passed |
| PSP settlement booking/payment contracts | mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test | booking/payment/reschedule contracts remain valid with settlement guard | 24 tests, 0 failures | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 62 tests 0 failures 3 skipped; AI 172 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Customer top-up targeted tests | mvn -Dtest=BookingDepositAdjustmentServiceTest,PaymentSyncContractTest test | customer TOP_UP list/payable/settlement and payment endpoint 通過 | 9 tests, 0 failures | passed |
| Web production build | npm run build:ci | My Bookings top-up checkout UI and API types compile | build completed | passed |
| Customer top-up booking/payment contracts | mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test | booking/payment/reschedule/merchant contracts remain valid with customer TOP_UP checkout | 28 tests, 0 failures | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 66 tests 0 failures 3 skipped; AI 172 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Refund SLA targeted tests | mvn -Dtest=BookingDepositAdjustmentServiceTest,MerchantControllerTest test | refund SLA summary 與 merchant endpoint 通過 | 22 tests, 0 failures | passed |
| Refund SLA Web production build | npm run build:ci | merchant refund SLA UI and API types compile | build completed | passed |
| Refund SLA booking/payment contracts | mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test | booking/payment/reschedule/merchant contracts remain valid with refund SLA visibility | 40 tests, 0 failures | passed |
| Whitespace sanity check | git diff --check | 確認 diff 無 trailing whitespace | no output | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 78 tests 0 failures 3 skipped; AI 172 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Refund escalation targeted tests | mvn -Dtest=BookingDepositAdjustmentServiceTest,MerchantControllerTest test | refund escalation service/controller contract 通過 | 24 tests, 0 failures | passed |
| Refund escalation Web production build | npm run build:ci | merchant escalation UI and API types compile | build completed | passed |
| Refund escalation booking/payment contracts | mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test | booking/payment/reschedule/merchant contracts remain valid with refund escalation tracking | 42 tests, 0 failures | passed |
| Whitespace sanity check | git diff --check | 確認 diff 無 trailing whitespace | no output | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 80 tests 0 failures 3 skipped; AI 172 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Refund webhook rotation targeted tests | mvn -Dtest=PaymentSyncContractTest,BookingDepositAdjustmentServiceTest test | previous secret callback and refund adjustment contracts remain valid | 21 tests, 0 failures | passed |
| Refund webhook rotation booking/payment contracts | mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test | booking/payment/reschedule/merchant contracts remain valid with current/previous webhook secrets | 43 tests, 0 failures | passed |
| Whitespace sanity check | git diff --check | 確認 diff 無 trailing whitespace | no output | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 81 tests 0 failures 3 skipped; AI 172 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Refund operations report targeted tests | mvn -Dtest=BookingDepositAdjustmentServiceTest,MerchantControllerTest test | refund operations report service/controller contract 通過 | 26 tests, 0 failures | passed |
| Refund operations report Web production build | npm run build:ci | merchant refund operations digest UI and API types compile | build completed | passed |
| Refund operations report booking/payment contracts | mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest test | booking/payment/reschedule/merchant contracts remain valid with refund operations digest | 45 tests, 0 failures | passed |
| Whitespace sanity check | git diff --check | 確認 diff 無 trailing whitespace | no output | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 83 tests 0 failures 3 skipped; AI 172 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Refund operations digest notification targeted Java tests | mvn -Dtest=MerchantControllerTest,LineNotificationClientTest,BookingDepositAdjustmentServiceTest test | triggerable merchant LINE digest contract 通過 | 33 tests, 0 failures | passed |
| Refund operations digest notification targeted AI tests | uv run --no-sync pytest tests/test_line_recommendation_fallback.py -q | refund operations digest Flex card and internal endpoint 通過 | 121 tests, 0 failures | passed |
| Refund operations digest notification Web production build | npm run build:ci | merchant LINE digest button and API types compile | build completed | passed |
| Refund operations digest notification booking/payment contracts | mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest,LineNotificationClientTest test | booking/payment/merchant/refund/LINE contracts remain valid | 52 tests, 0 failures | passed |
| Whitespace sanity check | git diff --check | 確認 diff 無 trailing whitespace | no output | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 86 tests 0 failures 3 skipped; AI 174 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Refund operations scheduled policy targeted Java tests | mvn -Dtest=MerchantControllerTest,BookingDepositAdjustmentServiceTest test | due-policy, cooldown skip, dispatch audit contract 通過 | 34 tests, 0 failures | passed |
| Refund operations scheduled policy Web production build | npm run build:ci | merchant scheduled policy UI and API types compile | build completed | passed |
| Refund operations scheduled policy booking/payment contracts | mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest,LineNotificationClientTest test | booking/payment/merchant/refund/LINE contracts remain valid with scheduler-ready policy | 58 tests, 0 failures | passed |
| Whitespace sanity check | git diff --check | 確認 diff 無 trailing whitespace | no output | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 92 tests 0 failures 3 skipped; AI 174 passed; ETL 42 passed; Web 19 passed; build passed | passed |
| Refund callback source validation targeted test | mvn -Dtest=PaymentSyncContractTest test | HMAC/rotation/source allowlist contract 通過 | 10 tests, 0 failures | passed |
| Refund callback source validation Java tests | mvn -Dtest=PaymentSyncContractTest,BookingDepositAdjustmentServiceTest,MerchantControllerTest test | payment/refund/merchant contracts remain valid | 44 tests, 0 failures | passed |
| Refund callback source validation booking/payment contracts | mvn -Dtest=BookingSyncContractTest,PaymentSyncContractTest,MerchantControllerTest,BookingDepositAdjustmentServiceTest,LineNotificationClientTest test | booking/payment/merchant/refund/LINE contracts remain valid with source allowlist | 61 tests, 0 failures | passed |
| Whitespace sanity check | git diff --check | 確認 diff 無 trailing whitespace | no output | passed |
| Portfolio verification | scripts/verify-portfolio.sh | 全 repo portfolio gate 通過 | Java 95 tests 0 failures 3 skipped; AI 174 passed; ETL 42 passed; Web 19 passed; build passed | passed |

## 錯誤日誌
| 時間戳記 | 錯誤 | 嘗試次數 | 解決方案 |
|----------|------|---------|---------|
| 2026-06-20T23:10:00+08:00 | Java 在 sandbox 內啟動時連 MySQL socket 失敗 | 1 | 改用 escalated `mvn spring-boot:run` 啟動，後端 health UP |
| 2026-06-20T23:23:00+08:00 | Playwright MCP screenshot 因即時倒數/元素穩定等待 timeout | 3 | 改用 terminal Playwright，在 sandbox 外啟動 Chromium 並直接輸出 PNG |
| 2026-06-20T23:18:00+08:00 | My Bookings 顯示未登入 | 3 | 確認 runtime JWT secret 與 LINE identity，補 demo user line identity 並用正確 secret 產生 token |
| 2026-06-19T21:31:00+08:00 | task_plan.md 首次 patch 因預期表格文字不完全相符失敗 | 1 | 重新讀取相關行號後改用更小範圍 patch 成功更新 |
| 2026-06-19T00:00:00+08:00 | BookingDepositAdjustmentService 大範圍 patch 因上下文不完全相符失敗 | 1 | 重新讀取檔案後改用小範圍 patch 分段更新 |

## 五問重啟檢查
| 問題 | 答案 |
|------|------|
| 我在哪裡？ | 階段 23：退款 callback source validation / PSP allowlist 完成 |
| 我要去哪裡？ | 下一輪可做 merchant notification preferences，或 provider-specific refund retry / operations |
| 目標是什麼？ | 評估 incident 後下一步，並完成可驗證的最小縱切 |
| 我學到了什麼？ | 見 findings.md |
| 我做了什麼？ | 見上方記錄；本輪把 refund reconciliation callback 推進到 optional source allowlist 與 trusted proxy header validation |

---
*每個階段完成後或遇到錯誤時更新此檔案*
