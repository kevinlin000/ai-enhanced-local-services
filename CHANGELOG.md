# CHANGELOG

## Stage 0 — 接手與工程基礎建設

### 原始功能導入與基礎模組
- `99c310d` add bytebites Spring Boot backend with nginx static frontend
- `2f42a56` 簡訊登入功能模組
- `83b4836` 商家快取功能模組
- `a4696c5` 優惠券秒殺功能模組
- `894c004` 優惠券搶購秒殺功能模組
- `96c70d0` 社群好友點讚功能模組
- `91b645e` 好友關注功能模組
- `4c1296e` 店家地理位置查詢功能模組
- `d30ffd0` 用戶簽到功能模組
- 為什麼：
  這一段代表接手前的原始功能基底，先保留完整脈絡，後續所有重構、升級與在地化都建立在這個基礎上。
  把起點說清楚，之後看安全修補、架構演進與台灣場景改造時，才知道哪些是既有設計，哪些是後續主動調整。

### Repo 整理與交接整理
- `3e5838a` restructure repo for spring boot 3 + python ai service
- `da03dfb` add initial code review report for java backend
- `a5b847a` keep planning docs and ai contracts out of git
- 為什麼：
  接手第一步不是急著加功能，而是先把 repo 結構、文件位置與 migration 入口整理到可維護狀態。
  先做代碼體檢與資料整理，後面每一批修補才有依據，不會在混亂基礎上繼續堆功能。

### 安全修補（Code Review 後）
- `f7b5360` handle lua return value in seckill api
- `0716f6c` invalidate redis token on logout
- `0de9676` prevent path traversal in delete endpoint
- `a6a6c40` do not log sms verification code
- `1eac0e0` externalize database credentials to env vars
- `108ac1b` verify logout and path traversal fixes
- 為什麼：
  接手後先補高風險安全洞，優先處理會造成資料錯誤、登入狀態失效、敏感資訊外洩與檔案刪除漏洞的點。
  這些問題不先修，後面再做 Spring Boot 3 升級或功能擴充，只會把風險原樣帶進新版本。

### 死代碼清理
- `9396b0e` remove unused md5 password encoder
- `6c59919` list dead code candidates for review
- `b8f54d1` remove dead code - empty blog comments module
- `9cce264` remove redis id worker main method
- `28e8df4` remove commented out legacy implementations
- `165726b` mark simple redis lock as deprecated educational example
- 為什麼：
  先清掉沒人用、容易誤導、甚至帶弱密碼學暗示的死代碼，能降低後續改版時的理解噪音。
  這一段的重點不是追求「乾淨漂亮」，而是把真正還在生效的程式路徑從歷史殘骸中分離出來。

### Spring Boot 3.2 + Java 17 升級
- `d12f9ea` upgrade java to 17
- `e525985` upgrade to spring boot 3.2 with jakarta migration
- `e758ff7` merge feature branch for spring boot 3 upgrade
- 為什麼：
  Spring Boot 2.7 已進入生命週期尾段，Java 17 是 Spring Boot 3 的最低門檻，也是現行 LTS 基準。
  先完成平台級升級，後續安全、認證、Flyway、AMQP 與基礎設施能力才有穩定的現代執行環境。

## Stage 1 — 台灣在地化

### B1: Schema 台灣化
- `b1fb00e` add flyway for sql migration management
- `58cb041` V2 rename tables to taiwan locale
- `3973ef7` V3 add taiwan localization fields
- `7ca24ed` V4 replace shop categories with taiwan food scene
- `4aea0fa` V5 seed 25 taipei shops in xinyi and zhongshan districts
- `5906917` merge feature branch for schema taiwan localization
- 為什麼：
  產品要服務台灣使用者，資料模型就不能停留在不相符的商業語境，否則 API、搜尋與推薦都會被舊命名綁住。
  Flyway 先接起來，後續每次 schema 演進都能留完整 migration 歷史，不再靠手動改表維持狀態。

### B2: LINE Login
- `884a4d7` add spring security, oauth2 client, and webflux
- `b88a2fb` add line login config properties
- `da1d170` add spring security config replacing manual interceptors
- `8879aa6` add jwt token provider and authentication filter
- `66ed46d` add line oauth service for code exchange and profile parsing
- `03a1aef` add line login controller and user service integration
- `bf198ae` deprecate sms login endpoints in favor of line login
- `ee3220b` permit public api aliases in security config
- `f5a0dfb` return 401 for unauthenticated api requests
- `ab63a73` rename roadmap draft to roadmap
- `13dbb20` stop stream worker cleanly during shutdown
- `e01e9d4` merge feature branch for line login oauth2
- 為什麼：
  台灣場景下，LINE Login 的實用性遠高於簡訊登入，登入流程也更符合真實產品習慣。
  這批同時把手刻攔截器換成 Spring Security，讓認證與授權邏輯回到框架主路徑，後續才容易擴充與維護。

### B3: 台北捷運 GEO
- `baa1713` V6 seed taipei mrt stations
- `62800e4` load mrt stations into redis geo on startup
- `56d5587` mrt and nearby shop endpoints
- `3fff6fe` merge feature branch for mrt geo
- 為什麼：
  台北生活圈的店家搜尋，捷運站比行政區更貼近真實使用方式，GEO 能把「附近」變成可演示的核心能力。
  這一批也讓 Redis 不只做快取，而是真正參與地理索引，對後續附近推薦與路徑搜尋有延展性。

### B4: 在地分類深化
- `29bac62` category listing and shop filtering endpoints
- `8f960b2` map taiwan-specific fields in shop entity
- `a109f3c` fallback to db for uncached shop detail
- `24b1cad` merge feature branch for category deepening
- 為什麼：
  有了台灣資料後，還要讓前台真的能用分類進入內容，而不是只有 schema 漂亮、API 卻沒把語意接出來。
  補上 entity 映射與 uncached fallback，等於把前一批資料層改動真正打通到查詢體驗。

### Stage 1 README
- `02a6a1c` stage 1 readme
- `f7d6880` rewrite readme to remove source references
- `5b29c9b` merge feature branch for stage 1 readme
- 為什麼：
  公開 repo 需要能獨立說明產品定位、工程方向與已完成能力，不能只靠內部任務脈絡才能理解。
  README 也刻意移除來源痕跡，把敘事重心放回「這個專案現在是什麼、接下來要往哪裡走」。

## Stage 1.5 — 進階工程能力

### C1: 多層快取
- `4e600dd` add caffeine and redisson starter
- `6cd2be0` caffeine local cache config
- `19020f1` redisson bloom filter for shop ids
- `5ec618c` multi-layer cache in shop queryById
- `afc5a27` add debug log for cache path observability
- `096083c` merge feature branch for multi-layer cache
- 為什麼：
  這批把單層 Redis 快取升級成 L1 本地快取、Bloom filter、空值快取的組合，目標是同時處理熱點、穿透與誤查。
  更重要的是把 cache path 打出可觀測訊號，之後調校命中率、排查流量路徑時不必全靠猜。

### C2: 令牌桶限流
- `e96d3d3` token bucket lua script
- `7204e0c` rate limit annotation and aspect
- `9c014bf` apply rate limit to seckill endpoint
- `107f785` merge feature branch for rate limit
- 為什麼：
  秒殺場景最怕瞬時流量直接打爆應用層，令牌桶限流是比「事後補救」更便宜的第一層保護。
  用註解式 + Lua 腳本封裝後，限流不再是某個 endpoint 的特例，而是可重用的基礎能力。

### C3: 分散式冪等
- `ec58314` idempotent annotation and aspect
- `87de2a8` handle idempotent exception as 409
- `e41dc71` apply idempotent to seckill endpoint
- `8db9268` merge feature branch for idempotent
- 為什麼：
  在高併發或使用者重複點擊場景，沒有冪等保護就會把同一請求視為多次有效操作，風險直接落到業務資料。
  先把註解式框架立起來，後續不只秒殺，任何需要短時間去重的寫操作都能直接套用。

### C4: Redisson 讀寫鎖
- `92e65ab` distributed read-write lock annotation and aspect
- `31d00da` apply rw lock to shop service
- `85e73d0` merge feature branch for read write lock
- 為什麼：
  單純快取不能解決所有併發可見性問題，尤其資料更新與讀取交錯時，需要更明確的鎖語意保護一致性。
  讀寫鎖的價值在於不把所有流量都串成單線，讀可並行、寫互斥，能在一致性與吞吐量之間取得平衡。

### C5: RabbitMQ + Outbox + DLQ
- `db0532a` add rabbitmq via docker compose
- `75758c6` add spring amqp and config
- `7c7836e` demo queue, listener, and publish endpoint
- `d67a52b` merge feature branch for rabbitmq setup
- `aebe30c` V7 create outbox_message table
- `81e1a3f` outbox service for transactional message recording
- `2570874` scheduled publisher for outbox messages
- `f221e03` demo endpoint via outbox pattern
- `1b053e4` merge feature branch for mq outbox
- `add2bb4` add dlx and dlq for demo queue
- `f64c818` listener retry config and dlq consumer
- `52947aa` merge feature branch for mq dlq
- 為什麼：
  這一批把訊息系統從「能收能發」推進到「失敗時不丟、不堵、不靜默」，補齊實務上最常見的一致性與可靠性缺口。
  Outbox 保證 DB 與事件發送的最小一致性，DLQ 則把無法成功消費的訊息從主流程隔離，方便監控與人工處理。
