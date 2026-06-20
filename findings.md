# 發現與決策

## 需求
- 使用者已完成 real-time incident handling，要求評估下一步並繼續做好。
- 需要從產品、架構、面試展示價值三個面向判斷，而不是只列待辦。

## 研究發現
- README 和 portfolio evidence map 已把 incident 放進核心展示路徑：AI late-arrival utterance -> deterministic Java incident -> LINE rescue card -> My Bookings open incident。
- roadmap 的 Next Product Moats 明確列出 incident 下一步：restaurant-side incident console、alternative slot suggestions、deposit-policy handling。
- 現有 `BookingIncidentService` 已有 create/list/resolve 服務方法，表示後端 domain 已具備 incident 生命週期雛形。
- Web `my-bookings` 已能建立 incident，但目前從讀到的片段看，展示重心仍在消費者端；營運端閉環可能是最大缺口。
- 商家後台已有 `/merchant` 與 `MerchantController` 管理 slot inventory，適合承接 open incident queue，不需要新增獨立後台。
- 本輪完成 merchant-side open incident list + resolve，讓 incident 從通知變成店家可處理的 operational queue。
- Alternative slot suggestions 可以先做成「建議」而非「一鍵改單」：Java 依 slot inventory 計算同日同桌型可用時段，先不碰訂金差額與 reschedule side effects。
- Alternative slot suggestions 第一版已完成：商家 incident payload 會回傳最多三個 adjustedTime 之後、同日同桌型、剩餘座位足夠的候選時段。
- 下一步最小閉環是 merchant 建立 proposal、customer accept 後走 `BookingRescheduleService`；不要讓 merchant 直接改顧客訂位。
- 顧客確認替代時段提案已完成第一版：proposal 掛在 incident 上，商家送出 PENDING，顧客接受後 BookingController 呼叫 `BookingRescheduleService`，並將 incident proposal 標為 ACCEPTED/RESOLVED。
- 替代時段提案拒絕與逾期已完成：proposal 現在有 expiresAt / declinedAt，顧客可拒絕，逾期提案會由 Java 標記 EXPIRED 並禁止改單。
- LINE 替代時段提案卡已完成：商家建立 proposal 後 Java 推送 proposal notification，AI service 產生 Flex card，LINE 輕量頁接受/拒絕時仍呼叫 Java proposal endpoint。
- 訂金政策盤點發現：`BookingRescheduleService` 會在改人數時直接重算 `depositTotal`；若訂位已付款，這可能靜默產生加收或退款義務，但目前沒有補款/退款金流或人工審核狀態。
- 當前 merchant incident proposal 仍限制同日、同桌型、同人數，所以現有商家提案不會自然產生訂金差額；但 direct reschedule endpoint 和未來擴充 proposal 都可能碰到此風險，防護應放在 Java 共用改單 service。
- 訂金政策防護第一版已完成：paid booking 若 proposed deposit total 高於或低於 current paid total，Java 會在 slot capacity mutation 前拒絕；成功改單會回傳 `depositPolicy` metadata 讓前端/LINE 可顯示政策狀態。
- 商家手動訂金差額處理的最小閉環應該是「先記錄 OPEN adjustment，再由商家確認已外部處理，最後 Java 套用改單」。這能避免假裝有真實金流，同時讓被擋下的需求不消失。
- 商家手動訂金差額處理第一版已完成：direct reschedule 或 incident proposal acceptance 被 paid-booking 訂金差額 guard 擋下時，Java 會建立 OPEN adjustment；商家在後台確認補款/退款已外部處理後，Java 才套用改單並關閉相關 incident proposal。
- 既有付款流程已有 TapPay pay-by-prime 與 booking `payment_trans_id`，但 Phase 11 的 TOP_UP / REFUND adjustment 目前只有商家 handling note，還沒有 settlement status、交易編號或 PSP 回寫時間。
- `PaymentController` 的 TapPay pay-by-prime 是顧客訂位訂金付款入口；差額 TOP_UP 需要顧客端 prime 才能真正刷卡，REFUND 多半由商家/PSP 後台處理。因此 Phase 12 不應硬把 merchant console 假裝成刷卡入口，而是先建立 settlement tracking contract。
- `BookingDepositAdjustmentService.resolveAndApplyForMerchantShop` 是套用改單的唯一後端入口，適合在這裡加上 settlement completed guard，防止 UI 或 API 直接跳過付款/退款紀錄。
- PSP settlement tracking 第一版已完成：`tb_booking_deposit_adjustment` 會記錄 settlement status/provider/trans id/amount/requested/completed timestamps；商家後台必須先記錄 PSP 交易完成，Java 才允許套用改單。
- My Bookings 已有 TapPay iframe prime 付款流程，適合重用在 TOP_UP adjustment；付款成功後應只記錄 settlement，改單套用仍交給商家端 resolve，以保留營運審核與 incident proposal 收斂。
- 顧客補款 checkout 第一版已完成：Java 提供 customer TOP_UP list / pay-by-prime endpoint，My Bookings 顯示待補款改單並重用 TapPay iframe；付款成功只把 adjustment settlement 標成 COMPLETED，不直接 mutate booking。
- 退款側目前仍會被 merchant settlement endpoint 直接標成 COMPLETED；這和真實金流不符，因退款通常是 PSP/後台非同步處理，應改成 request -> processing -> reconciliation result。
- 既有 settlement 欄位已能承接 PROCESSING / FAILED，不需要新增 migration；本輪可以只收斂 service 層狀態機與 API contract。
- REFUND reconciliation 第一版已完成：merchant direct settlement 不再能完成退款；REFUND 必須先 request，reconciliation 成功才是 COMPLETED，失敗會停在 FAILED 並阻擋 apply。
- refund reconciliation 仍缺 callback idempotency：PSP 常會重送同一事件，若沒有 event key 去重，服務雖然會因 COMPLETED guard 不再重複 apply，但缺少可查的 duplicate/audit trail。
- refund idempotency + audit 第一版已完成：新增 V49 audit table，request / reconciliation 都寫事件；callback 可帶 eventKey，重複 eventKey 會回傳 `idempotentReplay`。
- 目前 refund callback 有 event key 去重，但尚未驗證 callback 來源；若 production 設定 webhook secret，應拒絕缺失、過期或 HMAC 不符的 callback。
- signed refund webhook 第一版已完成：`bytebites.refund.webhook.secret` 空白時保留 demo；設定後要求 `X-ByteBites-Webhook-Timestamp` 與 `X-ByteBites-Webhook-Signature`，並驗證 5 分鐘時間窗。
- refund 狀態機已經有 PROCESSING / COMPLETED / FAILED，且已補 audit 與 callback signature；下一個缺口不是再新增金流動作，而是讓商家營運端可以一眼看到 FAILED 或卡住太久的 PROCESSING 退款，避免 incident/deposit adjustment 雖可信但不可營運。
- refund SLA visibility 第一版已完成：Java 以 shop ownership scope 聚合 OPEN REFUND 中的 FAILED 與超時 PROCESSING，商家後台用狀態 band 顯示正常或注意件數，並在 refund request/reconciliation/apply 後刷新。
- refund SLA 只能告警，還不能表達「營運已接手」；下一個最小閉環應新增 escalation/follow-up 狀態，讓 FAILED 或 stale PROCESSING refund 被標記為已升級處理並留下 audit event。
- refund escalation 第一版已完成：V50 在 adjustment 上記錄升級時間、備註與處理人；service/controller 只允許 FAILED 或 PROCESSING refund 升級，並寫入 `REFUND_ESCALATED` audit event。
- refund webhook 目前已有 HMAC 與 freshness，但只有單一 secret；production secret rotation 需要 current/previous secret 並存，讓 PSP callback 在部署與 provider 設定切換期間不中斷。
- refund webhook secret rotation 第一版已完成：`PaymentController` 支援 `bytebites.refund.webhook.secret` + `bytebites.refund.webhook.previous-secret`；驗證會接受 current/previous 任一 HMAC，無 secret 時保留 demo。
- refund SLA 與 escalation tracking 已能分別回答「哪些退款異常」與「哪些已有人接手」，但商家仍需要一個 digest/report 把 FAILED、stale PROCESSING、未升級、已升級待追蹤整理成營運視角。
- refund operations report 可直接重用 `refundSlaSummaryForMerchantShop` 的 attention items；不需要新增 migration 或重複 SQL，能把 pending escalation / escalated follow-up 做成同一個 merchant scoped report。
- refund operations digest 第一版已完成：後端提供 merchant scoped report，前端商家後台顯示建議動作、未升級/已升級統計與重點退款項目。
- refund operations digest 已經有穩定 payload；下一步若要做 scheduled notification，應先提供「可觸發通知 contract」與 LINE Flex card，排程/值班偏好可晚一輪再接。
- refund operations digest notification 第一版已接通：MerchantController 可觸發通知、Java 透過商家 LINE identity link 找推播目標，AI service 提供 internal Flex card endpoint；沒有 LINE 綁定或沒有退款異常時回傳 skipped。
- Phase 21 後仍缺 scheduler 可安全使用的 due-policy：若直接把 cron 接到 notify endpoint，會在異常未解決時重複洗版；Phase 22 應先讓 Java 判斷 shouldNotify、cooldown、lastSentAt、nextEligibleAt 與 skipped reason。
- refund operations scheduled policy 第一版已完成：Java 以 `tb_merchant_notification_dispatch` 記錄 dispatch，policy endpoint 回傳 shouldNotify / reason / cooldown / lastSentAt / nextEligibleAt，dispatch-if-due endpoint 在 cooldown 內會 skipped，due 時才推 LINE digest。
- refund callback 目前已有 HMAC、fresh timestamp 與 current/previous secret rotation，但尚未驗證 request source；Phase 23 應新增 optional allowlist，支援 direct remote address 與受信任 proxy header，未設定 allowlist 時保留 demo callback。
- refund callback source validation 第一版已完成：`bytebites.refund.webhook.allowed-sources` 設定後會驗證 request source；direct remote address 可命中 exact IP / IPv4 CIDR，若使用 forwarded source，remote address 必須先命中 `trusted-proxies` 才信任 `source-header`。
- 使用者提到「ngorx 改成 ngnix」時，實際應判斷為 ngrok vs Nginx：兩者不是同類替換。ngrok 是 local tunnel，Nginx 是 stable public reverse proxy / TLS / routing boundary。
- 現有 Web 依賴 Next rewrites 與 `NEXT_PUBLIC_JAVA_API=/api/java`；LINE Login callback 在公開 Web proxy 下是 `/api/java/api/auth/line/callback`，Java 實際收到 `/api/auth/line/callback`。
- AI service 同時承接 `/api/line/webhook`、`/line/webhook`、`/line/book/*`、`/line/my-bookings` 等 LINE Messaging webhook 與 action pages；Nginx 需要 preserve `/api/line` 與 `/line` prefix。
- AI agent stream 走 `/api/ai/agent/stream`；若 Nginx buffering 未關，可能不會壞成 500，但會讓串流延遲成非即時回應。
- Phase 24 應保留 ngrok local demo path，新增 Nginx template / docs / verifier 來支撐 stable public demo，而不是改動已通過的 Java/AI/Web runtime 合約。
- Nginx stable public deployment boundary 第一版已完成：template 定義 Web/Java/AI upstream、proxy headers、health paths、LINE webhook/action paths，並對 AI routes 關閉 proxy buffering；部署指南列出 LINE Login callback、Messaging webhook、Web/Java/AI env 與 refund webhook trusted proxy/source allowlist 設定。
- root `docker-compose.yml` 使用 `./deploy/...` volume path，`deploy/docker-compose.yml` 使用 `./...` path；若新增 overlay 放在 `deploy/docker-compose.nginx.yml`，應讓 command 以 `-f deploy/docker-compose.yml -f deploy/docker-compose.nginx.yml` 執行，volume path 可用 `./nginx/bytebites.conf.template` 指向 deploy 目錄下的 template。
- Nginx compose overlay 應預設代理 host 上的 dev processes，因此 upstream 預設用 `host.docker.internal:3000/8081/8000`，並加 `extra_hosts: host.docker.internal:host-gateway` 兼容 Linux Docker。
- 本機 public-proxy port 不應預設搶 80，避免權限或 port 衝突；用 `BYTEBITES_PUBLIC_HTTP_PORT=8088` 比較安全，正式環境再設為 80 或由 TLS/load balancer 對外。
- Nginx Docker Compose public-proxy overlay 第一版已完成：`deploy/docker-compose.nginx.yml` 透過 `public-proxy` profile 啟動 `nginx:1.27-alpine`，mount `deploy/nginx/bytebites.conf.template` 到官方 Nginx templates 目錄，預設對外 `localhost:8088`。
- `docker compose ... config` 不帶 profile 時會隱藏 `nginx`，這是 Compose profiles 的預期行為；部署文件已改成 `--profile public-proxy config`，讓驗證輸出包含 Nginx service。
- 現有 `scripts/demo-keepalive.sh` 是常駐 watchdog，會啟動 Web/Java/AI/ngrok；Phase 26 需要的是短命令 smoke test runner，不應複製 keepalive 的啟動/重啟行為。
- AI `/api/ai/agent/stream` 會先回 SSE `agent_start` 與 `status`，再進入較重的 agent turn；smoke test 可以只檢查 `text/event-stream` 與 `agent_start`，不必等完整推薦結果。
- Java LINE Login `/api/auth/line/login` 在 OAuth 未設定時仍會 redirect 到 frontend error，但會先設定 state cookie；public-proxy smoke test 應檢查 redirect status、Location 存在、以及 `Set-Cookie Path=/api/java/api/auth/line`，避免 proxy cookie path 回歸錯誤。
- Nginx public-proxy smoke runner 第一版已完成：`scripts/smoke-nginx-public-proxy.sh` 檢查 Web root、Java health、AI health、LINE webhook、LINE Login redirect/cookie path、AI SSE start frame；支援 `--base-url`、`--skip-stream`、`--dry-run`。
- `scripts/verify-nginx-template.py` 現在會讀取 smoke script、檢查關鍵路由與 cookie path 片段、執行 `bash -n` 和 dry-run；live smoke 不放進 portfolio gate，避免 CI 需要啟動四個服務。
- Phase 27 評估：直接 live smoke 驗證強但受本機服務狀態影響；HTTPS/雲端需要網域與 secrets；回到產品功能會打斷部署可靠性主線。最高 CP 是新增 demo readiness preflight runner，先檢查 compose config、Web/Java/AI/Nginx 可達性，並可選擇性呼叫 live smoke。
- Demo readiness preflight 第一版已完成：`scripts/demo-readiness.sh` 檢查必要部署檔、Docker Compose public-proxy config、Web/Java/AI/Nginx health，預設只警告 live service 缺失；`--strict` 可讓正式彩排在任何服務未就緒時 fail，`--live-smoke` 可接續跑完整 public-proxy smoke。
- `verify-nginx-template.py` 一開始用 `DRY_RUN=true` 呼叫 readiness script，但 script 固定把 `DRY_RUN=false`，導致 verifier 仍打 localhost。已改為環境變數可覆寫，讓 portfolio gate 保持離線且不依賴四個服務啟動。
- Phase 28 live rehearsal 初次 preflight 證實 Web/Java/AI/Nginx 都未啟動；啟動 infra 後，Web 和 AI 可正常健康檢查，Java 先後卡在 sandbox MySQL socket、缺 `hmdp` schema、以及 V16 clean DB FK failure。
- 乾淨 DB 啟動暴露 `V16__taxonomy_backfill.sql` 的 allowlist id 假設：`tb_shop_badge` / `tb_shop_tag` 直接插入部分不存在的 shop id 會被 FK 擋下。修正後用 derived table join `tb_shop`，只對存在店家 backfill badge/tag。
- live readiness/smoke 腳本本身需要網路權限；在 sandbox 直接跑 `scripts/demo-readiness.sh --live-smoke --strict` 會讓腳本內部 curl 全部 000，但同一時間直接 `curl` endpoint 成功。正式 live rehearsal 需用 escalated execution。
- Phase 28 正式 rehearsal 已通過：`scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict` 全綠，包含 Web root、Java health、AI health、Nginx route health、LINE webhook、LINE Login redirect/cookie path、AI SSE start frame。
- Phase 29 clean migration smoke 第一版已完成：`scripts/smoke-clean-mysql-migrations.sh` 用臨時 DB 和臨時 Java port 驗證 fresh-schema Flyway startup，成功後會停 Java 並刪 DB。
- clean migration smoke 的 live mode 需要 Docker daemon、MySQL、Redis、RabbitMQ 與 Java 啟動權限；portfolio gate 只納入 `bash -n` 與 `--dry-run`，避免日常驗證受本機服務狀態影響。
- macOS/BSD `mktemp` 不適合使用 `XXXXXX.log` suffix 模板；改成無 suffix 的 `bytebites-clean-migration.XXXXXX` 才能正確產生短命 log path。
- Phase 30 clean migration smoke workflow 第一版已完成：`.github/workflows/clean-mysql-migration-smoke.yml` 可手動在 GitHub Actions 啟 Redis/RabbitMQ/MySQL，並呼叫同一支 `scripts/smoke-clean-mysql-migrations.sh` 驗 fresh-schema Java startup。
- workflow 採 named MySQL container `bytebites-ci-mysql`，而不是 GitHub service hostname，因為既有 smoke script 需要 `docker exec` 到 MySQL container 來建立和刪除臨時 DB；使用已知 container name 可保持腳本 source-of-truth 不分叉。
- 新增 `scripts/verify-clean-migration-workflow.py` 作為離線 contract verifier，避免手動 workflow 的 infra/service/image/timeout/script invocation 漂移後等到 demo 前才發現。
- Phase 31 release boundary 第一版已完成：`docs/release-boundary.md` 把 verification ladder、commit grouping、demo script 與 production gaps 收成單一發表交付邊界。
- `scripts/release-readiness.sh` 採 dry-run / offline / full / live-local 四模式，避免一條命令同時混合離線 contract、full portfolio build 和 live service smoke。
- push-triggered Portfolio CI 在 release boundary 後仍紅燈，失敗點不是 clean migration workflow，而是 ETL taxonomy tests 對 ignored `etl-pipeline/data/raw/` 有隱性依賴。
- 本機 `scripts/verify-portfolio.sh` 會因本機存在 62MB ignored raw corpus 而通過；GitHub checkout 沒有該 corpus，因此 `load_shops()[10099]` 等存取丟 `KeyError`。
- ETL taxonomy 測試應分成兩層：committed minimal fixture 永遠在 CI 跑核心分類回歸；完整 103 筆 approval map 只在 full raw corpus 存在時跑。
- Phase 32 完成 fixture stabilization 後，本機完整 raw 模式 ETL 為 43 passed；模擬 CI 無 raw 模式為 42 passed, 1 skipped。
- Portfolio CI 的 ETL 修正推上後，Backend Java 暴露另一個 hosted-runner-only failure：proposal expiry 測試用系統預設時區，production code 用 `Asia/Taipei` business zone，UTC runner 會把未來 20 分鐘誤判成已逾期。
- 目前作品以 portfolio interview 標準可評 88/100：足夠展示且高於一般 CRUD / chatbot demo，但尚未是 production SaaS rollout。
- 目前不應繼續堆新功能；更高價值是把 evidence package 收斂成 scorecard、截圖、短 demo script、production-gap answer 與 architecture diagram。
- 使用者目標是「每一樣都達到 100 分」；需要先定義評分邊界，否則容易把 portfolio readiness 和 production SaaS readiness 混在一起。
- Portfolio 100 可以在 repo 內完成：架構圖、證據包、截圖/影片、CI/verification、清楚的 production-gap answer。
- Production SaaS 100 不能只靠本機 repo 宣稱完成：還需要真實 PSP refund provider contract、managed secrets、cloud runtime、observability、backup/restore、merchant operations process。

## 技術決策
| 決策 | 理由 |
|------|------|
| 優先評估 restaurant-side incident console | 它直接延伸已完成的 incident state，能把「通知」升級成「營運處理流程」 |
| 本輪暫不做 alternative slot suggestions / deposit-policy handling | 這兩項會牽涉訂位改單、訂金差額、可用席次演算法，適合下一個較大縱切；merchant console 可先用現有 state 完成閉環 |
| 後續優先做 alternative slot suggestions | merchant console 已補齊營運入口；下一步可讓 incident resolve 前提出可行替代時段，價值高於先做單純歷史列表 |
| Suggestions 先放在 merchant incident payload | 它讓商家處理 incident 時直接看到可協調選項，且保持 Java 為 source of truth；前端不自行推測可用座位 |
| 下一步不是再加列表，而是一鍵顧客確認 | 現在已能看見可行替代時段；下一個產品價值是把建議轉成可被顧客確認的狀態轉移 |
| proposal 狀態先掛在 incident 上 | 一個 incident 只保留一個 pending proposal，能完成 demo 與 contract；多輪協商再另建 table |
| 下一步應做 decline/expiry 與 LINE proposal card | 接受流程已完成；缺的是顧客拒絕/過期和 LINE 直接確認入口，不是再補更多後台顯示 |
| decline/expiry 先於 LINE proposal card 完成 | LINE 卡片需要指向可靠狀態機；現在 PENDING 可轉 ACCEPTED / DECLINED / EXPIRED，下一步才適合做 LINE 直接操作入口 |
| LINE proposal card 採 Java 驗證的 action token flow | AI service 只承接 LINE UI 和 token，真正 accept/decline 仍由 BookingController transaction 檢查權限、逾期和狀態 |
| 下一步應評估 deposit-policy handling | incident 提案與 LINE 操作已閉環；若替代時段牽涉不同訂金或取消政策，下一個真實產品問題會是差額/退款規則 |
| deposit-policy handling 第一版採 guard rail | 已付款訂位若新訂金總額高於或低於原已付款總額，Java 拒絕自動改單並提示店家人工處理；待付款訂位仍可在付款前重算訂金 |
| 下一步應做 merchant manual adjustment 而非再擴 LINE 卡 | 現在改單會正確擋下金流差額；下一個缺口是商家看到被擋原因、記錄人工補款/退款處理結果，而不是讓 AI 或 LINE 自行繞過政策 |
| manual adjustment 不直接接 TapPay | 本輪保留 demo 邊界：記錄 TOP_UP/REFUND、處理備註、處理人與套用狀態；真實退款/補款 settlement 是下一層，不混入這個縱切 |
| 下一步首選 real PSP settlement tracking | manual adjustment 已把營運閉環補齊；若繼續深化付款可信度，應接 TapPay top-up/refund transaction 狀態與 reconciliation，而不是再讓商家手動填狀態 |
| Phase 12 先做 settlement state machine，不直接做真實退款 API | TapPay booking 付款已存在；本輪要先補差額 adjustment 的 PSP lifecycle contract，避免大幅擴張到退款對帳與金流商非同步 webhook |
| settlement completed guard 放在 service 層 | `resolve` 是改單套用前最後一道 transaction 邊界；在 service 層檢查可同時保護 Web UI、merchant API 和未來 LINE/AI 入口 |
| 下一步首選 customer top-up checkout / refund reconciliation | settlement tracking 已完成 source-of-truth 狀態；下一個付款深化點是讓 TOP_UP 產生顧客付款連結，REFUND 則接 PSP webhook / reconciliation |
| Phase 13 先做 TOP_UP，不做 REFUND webhook | TOP_UP 可由顧客端 TapPay prime 立即驗證；REFUND 需要非同步 PSP 狀態與對帳，不應和顧客 checkout 放在同一個最小縱切 |
| 下一步首選 REFUND webhook / reconciliation | TOP_UP 已具備顧客付款入口；剩下最真實的金流缺口是退款側 PSP 回寫、失敗重試與對帳報表 |
| Phase 14 先做 demo/internal reconciliation，不宣稱真實 PSP 退款 API | 現有 TapPay refund credential/webhook secret 未建模；先建立可信狀態機與 callback contract，文件註明正式上線需驗 PSP signature |
| REFUND 必須從 merchant direct settlement 拆出來 | 補款可以由顧客 checkout 或 merchant PSP reference 完成；退款要避免商家單點誤標 completed 後直接套用改單 |
| Phase 14 完成後下一步是 audit/retry，不是再加 UI 文案 | 現在狀態機已可信；若要繼續深化，應加 webhook signature、refund retry audit table、merchant SLA/reporting |
| Phase 15 先做 event-key idempotency 和 audit table | 這是 production hardening 的最小縱切；比直接做真實退款 API 更可控，也能支撐未來 webhook signature 和 retry report |
| 下一步才做 signed webhook verification | 現在已有去重與 audit；正式 PSP 接入前的下一個缺口是簽章驗證、secret rotation、callback source validation |
| Phase 16 採 optional HMAC secret | demo 環境不設 secret 時保留商家後台測試路徑；production 設 secret 後 callback 必須帶 timestamp 與簽章 |
| 下一步才做 secret rotation / source validation | 本輪已驗 HMAC 與 freshness；更完整 production rollout 還需要多 secret rotation、PSP IP/source allowlist、監控報表 |
| Phase 17 先做 refund SLA visibility | 這是最小 operational hardening：不改金流狀態機、不新增 migration，只把 Java source-of-truth 內的 FAILED / stale PROCESSING refund 聚合成商家可處理的訊號 |
| refund SLA summary 不新增 migration | 既有 `tb_booking_deposit_adjustment` settlement fields 已足夠判斷 FAILED 與超時 PROCESSING；本輪只新增查詢、API、UI 和測試 |
| Phase 18 採 adjustment 欄位 + audit event | escalation 是 adjustment 的目前營運狀態，適合放在 `tb_booking_deposit_adjustment`；每次標記仍寫入 refund audit table，保留事後追蹤 |
| Phase 18 不做自動重試 | 自動 retry 需要 PSP provider contract 與錯誤碼分類；本輪先做人工升級狀態和 audit，避免假裝已有 production refund operations |
| Phase 19 先做 secret rotation，不做 source allowlist | IP/source allowlist 依部署 proxy 與 PSP 網段而定；current/previous secret rotation 可在現有 controller contract 內完整測試 |
| Phase 19 不做 source allowlist | source validation 依 proxy/IP/PSP 網段部署；rotation 已先補上較穩定的密鑰生命周期缺口 |
| Phase 20 先做 operations report，不做自動 retry | retry 需要 PSP provider 錯誤碼與重試契約；report 可用既有 Java source-of-truth 欄位完成，能提升營運可見度且風險較低 |
| Phase 20 不做 scheduled auto notification | 目前沒有商家通知偏好與值班設定；先把 digest 放進商家後台，下一步再決定是否推 LINE/email/report job |
| Phase 21 先做 triggerable notification，不做 cron | 沒有通知頻率、值班時段與商家偏好模型前，不應新增固定排程；先讓 Java report 能被手動或未來 scheduler 觸發並保留 skipped 狀態 |
| Phase 22 先做 due-policy 與 cooldown audit，不做背景 daemon | scheduler 是否由 Spring、外部 job 或手動後台觸發可晚點決定；核心風險是避免重複通知與保留 dispatch 記錄，這應先落在 Java source of truth |
| Phase 22 不宣稱 production cron 已完成 | 本輪完成 scheduler-ready contract 與後台手動 due dispatch；真正 production rollout 還需要部署排程方式、商家通知偏好與 provider source validation |
| Phase 23 source validation 採 optional allowlist | PSP 網段與 proxy 部署依環境而定；Java 先提供明確 contract：設定 allowlist 才啟用，且 trusted proxy header 只在 remote address 命中 trusted proxy 時採用 |
| Phase 23 不把 forwarded header 當成無條件可信 | `X-Forwarded-For` 這類 header 可被客戶端偽造；只有 remote address 是 trusted proxy 時才讀 configured source-header |
| Phase 24 採 Nginx template，不改 runtime code | 這一輪的目標是部署邊界與可重現設定；現有功能已驗證通過，改 runtime 反而會擴大風險 |
| Nginx template 直接承接 public API paths | 讓 browser 仍使用 `/api/java`、`/api/ai`、`/api/line`，避免前端、LINE Developers、Java OAuth cookie path 需要改成另一套規則 |
| 保留 `/api/python/*` legacy smoke path | Case study 11 和 demo smoke tests 已使用 `/api/python/health`；Nginx 應先保留相容性，未來再清理命名 |
| Nginx verifier 接進 portfolio gate | 部署 template 之後若不驗，很容易在文件更新時讓 callback、webhook 或 proxy header 漂移；離線 verifier 能以低成本守住 route contract |
| Phase 25 不把 Web/Java/AI 都容器化 | 目前 repo 的 runtime 開發流程仍是 host 上跑三個服務；本輪只補 public proxy overlay，避免引入 build image、env secret 和 DB migration 啟動順序的新複雜度 |
| Compose overlay 使用 profile | 避免平常啟動 infra 時意外打開 public proxy；需要驗證或演練時明確加 `--profile public-proxy` 或指定 `nginx` service |
| smoke runner 不啟動服務 | 它只驗證既有 public proxy；啟停服務仍交給既有 dev commands / compose overlay，避免測試器變成另一個 watchdog |
| Phase 26 smoke script 不納入 live portfolio gate | smoke test 需要 Web/Java/AI/Nginx 都已啟動；CI/portfolio gate 只檢查腳本語法與 dry-run，真正 live smoke 由 demo rehearsal 手動執行 |
| Phase 27 preflight 不自動啟動或殺服務 | Demo 前檢查器應該指出缺什麼和下一步命令，不應擅自改變本機長跑服務狀態 |
| Phase 27 preflight 支援 non-strict 與 strict 兩種模式 | 日常檢查需要給出缺口與啟動命令但不中斷；正式 demo 彩排則應用 `--strict --live-smoke` 把缺失轉成失敗 |
| V16 backfill 採存在性安全寫法 | taxonomy allowlist 不應假設所有舊 seed shop id 永遠存在；migration 應在 FK 前先 join `tb_shop` |
| live rehearsal 腳本用 escalated execution | 腳本內部有多個 curl 與 Docker/Compose 檢查；sandbox 會造成 false negative，正式彩排應讓腳本以可存取本機服務的權限執行 |
| Phase 29 clean migration smoke 不納入 live portfolio gate | live check 會啟 Java、連 Docker MySQL 並依賴 Redis/RabbitMQ；日常 gate 只保護腳本 contract，正式 demo rehearsal 才跑 live smoke |
| clean migration smoke 使用臨時 DB 而不是重建 `hmdp` | 避免污染開發資料庫，也能反覆驗證 Flyway 是否能從空 schema 啟動 |
| Phase 30 採手動 GitHub Actions workflow | clean-schema startup 是高價值但較重的 live infra check；手動觸發比每次 push 強制跑更符合成本與穩定性 |
| workflow 使用 named MySQL container | GitHub service container 的 runtime 名稱不適合拿來給腳本 `docker exec`；顯式 `docker run --name bytebites-ci-mysql` 讓 smoke script 可直接重用 |
| Phase 31 不直接切 commit | 工作樹跨多個完整縱切且尚未由使用者確認 commit 策略；先建立 release boundary 和 commit grouping，避免把大量變更壓成不可審查的單一提交 |
| release readiness 分四種模式 | dry-run/offline/full/live-local 對應不同成本與依賴；這比一條命令自動啟 live smoke 更可控，也更符合 demo 前 checklist |
| Phase 32 先修 CI red gate，不加新功能 | Portfolio CI 紅燈會直接削弱作品可信度；在 CI 回綠前，新增功能的展示價值低於修正可重現性 |
| taxonomy fixture 不提交完整 raw corpus | `etl-pipeline/data/raw/` 是 crawler output 且已被忽略；提交少量 critical fixture 可保留回歸保障，同時避免把 62MB raw data 變成 repo contract |
| Java proposal expiry tests 使用 business zone | Runtime 以台北時間判斷提案是否逾期；測試也必須用同一個 business zone，避免 CI runner 時區影響結果 |
| Portfolio readiness 評分採 88/100 | 作品已具備產品差異、Java source-of-truth、AI workflow、資料品質、Web/LINE 協調與 CI；扣分主要來自 presentation packaging 與 production rollout gaps |
| 下一步做 evidence package 而非 feature | 新功能會增加說明成本；目前最大槓桿是讓現有深度更容易被面試官看見 |
| Phase 34 先建立 100 分路線圖與架構證據 | 這能把「做到很棒」變成可驗證交付物：Portfolio 100 的缺口是證據和敘事，不是再加產品分支 |

## 遇到的問題
| 問題 | 解決方案 |
|------|---------|
| readiness verifier dry-run 仍觸發 localhost HTTP checks | 將 `DRY_RUN`、`STRICT`、`LIVE_SMOKE` 改成保留環境變數預設值，再由 CLI option 覆寫 |
| Java live start: `Unknown database 'hmdp'` | 本機 MySQL container 只有 `local_fresh`，建立 `hmdp` schema 後讓 Flyway 自動套 migration |
| Java live start: V16 FK failure on `tb_shop_badge` | 將 V16 badge/tag allowlist insert 改成 join `tb_shop`，並新增 migration resource test |
| strict readiness sandbox false negative | 直接 curl 成功但腳本內 curl 失敗；改用 escalated script execution 後通過 |
| Portfolio CI ETL taxonomy tests 缺 ignored raw corpus | 新增 committed taxonomy fixture，並讓完整 approval map 在缺 full raw corpus 時明確 skip |
| Portfolio CI Backend Java proposal tests 在 UTC runner 誤判逾期 | 將 proposal expiry fixture 改成 `Asia/Taipei` business zone，與 production 判斷一致 |

## 資源
- README.md
- docs/roadmap.md
- docs/portfolio-evidence-map.md
- docs/case-studies/14-portfolio-verification.md

## 視覺/瀏覽器發現
- 未使用瀏覽器或視覺檢查。

---
*每執行2次查看/瀏覽器/搜尋操作後更新此檔案*
*防止視覺資訊遺失*
