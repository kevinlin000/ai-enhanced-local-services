# 代碼體檢報告

## 摘要
總共 20 個問題：高 7、中 13、低 0。

本次以靜態審查為主，另外執行過 `mvn test`。測試未通過，但主要原因是測試啟動時需要連 `127.0.0.1:6379`，目前環境無法連線 Redisson，屬於驗證限制，不列入下方問題統計。

## 1. 正確性問題

### 1.1 秒殺接口忽略 Lua 執行結果，庫存不足或重複下單仍回成功
- **嚴重等級**：高
- **位置**：`backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:178`、`backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:185`
- **問題描述**：`seckillVoucher()` 執行 Lua 後完全沒有判斷 `result`，不論 Lua 回傳 `1`（庫存不足）、`2`（重複下單）或 `0`，都直接回傳 `Result.ok(orderId)`。
- **可能後果**：前端會收到成功訂單號，但實際沒有下單成功，造成訂單狀態錯亂、客訴、重試風暴。
- **建議修法**：明確判斷 Lua 回傳值；`0` 才回成功，其餘回對應失敗訊息。

### 1.2 登出只清 ThreadLocal，Redis token 未失效
- **嚴重等級**：高
- **位置**：`backend-java/src/main/java/com/hmdp/controller/UserController.java:61`、`backend-java/src/main/java/com/hmdp/controller/UserController.java:64`、`backend-java/src/main/java/com/hmdp/utils/RefreshTokenIntercepter.java:32`、`backend-java/src/main/java/com/hmdp/utils/RefreshTokenIntercepter.java:45`
- **問題描述**：`/user/logout` 只呼叫 `UserHolder.removeUser()`，沒有刪除 Redis 中的登入 token。只要 token 還沒過期，後續請求仍可通過攔截器重新登入。
- **可能後果**：登出形同無效，遺失或外洩的 token 在 TTL 內仍可持續使用。
- **建議修法**：登出時解析 request header token，刪除 `login:token:*` 對應 Redis key，再清理 ThreadLocal。

### 1.3 異步下單執行緒依賴共享 `proxy` 欄位，啟動後可能空指標
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:66`、`backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:151`、`backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:164`、`backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:170`、`backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:185`
- **問題描述**：背景執行緒在 `@PostConstruct` 就啟動，但 `proxy` 只有在 HTTP 請求進到 `seckillVoucher()` 時才賦值。若系統重啟後先處理 pending list，`proxy.createVoucherOrder()` 可能直接 NPE。
- **可能後果**：重啟後積壓訂單無法恢復處理，pending list 反覆報錯。
- **建議修法**：不要用共享欄位傳 proxy。改成透過 Spring 注入自身代理 bean，或把交易方法拆到獨立 service。

### 1.4 Redis Stream consumer group 未見初始化，首次部署可能直接失敗
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:78`、`backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:105`
- **問題描述**：程式直接用 `Consumer.from("g1", "c1")` 讀 `stream.orders`，但專案內沒有建立 `g1` group 的程式碼。
- **可能後果**：新環境第一次啟動即出現 `NOGROUP`，異步下單流程不可用。
- **建議修法**：在應用啟動時顯式建立 stream 與 consumer group，或在部署腳本初始化。

### 1.5 Follow 寫 MySQL 與 Redis 沒有交易/補償，容易不一致
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/service/impl/FollowServiceImpl.java:45`、`backend-java/src/main/java/com/hmdp/service/impl/FollowServiceImpl.java:50`、`backend-java/src/main/java/com/hmdp/service/impl/FollowServiceImpl.java:53`、`backend-java/src/main/java/com/hmdp/service/impl/FollowServiceImpl.java:57`、`backend-java/src/main/java/com/hmdp/service/impl/FollowServiceImpl.java:61`
- **問題描述**：先寫 DB，再寫 Redis set；中途 Redis 失敗時沒有回滾或補償。
- **可能後果**：`isFollow()` 查 DB 與共同關注查 Redis 可能互相矛盾，產生幽靈關注/漏關注。
- **建議修法**：至少加交易與錯誤處理；更穩妥做法是用事件補償或定期對帳重建 Redis 關注集合。

## 2. 效能問題

### 2.1 熱門筆記查詢存在 N+1 DB 查詢與 N+1 Redis 查詢
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:57`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:63`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:64`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:66`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:219`
- **問題描述**：`queryHotBlog()` 先查一頁 blog，之後每筆再查一次作者資料、再查一次按讚 zset score。
- **可能後果**：頁面資料量一大，DB/Redis 往返次數線性放大，延遲明顯上升。
- **建議修法**：作者資料批次查詢；按讚狀態可視需求批次讀取或延後查詢。

### 2.2 關注流分頁同樣存在 N+1 DB 查詢與 N+1 Redis 查詢
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:201`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:204`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:206`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:208`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:219`
- **問題描述**：`queryBlogOfFollow()` 查出 blog 後，又逐筆查作者與按讚狀態。
- **可能後果**：粉絲流翻頁時吞吐下降，Redis/DB 壓力偏高。
- **建議修法**：與熱門筆記相同，改批次查作者與互動狀態。

### 2.3 發文後全量查粉絲、逐筆 `ZADD`，且未使用 pipeline
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:157`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:159`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:164`
- **問題描述**：`saveBlog()` 對所有粉絲做全量 `.list()`，再逐筆呼叫 Redis `ZADD`，沒有批次化。
- **可能後果**：大 V 發文時，單次請求延遲與 Redis RTT 成正比成長，容易拖慢整個 API。
- **建議修法**：至少改非同步 fan-out，並考慮 Redis pipeline / MQ / 推拉混合方案。

### 2.4 粉絲查詢未限制筆數，資料量大時容易拖垮發文接口
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:157`
- **問題描述**：`followService.query().eq("follow_user_id", user.getId()).list()` 沒有分頁或上限。
- **可能後果**：單一作者粉絲過多時，查詢結果一次全部載入記憶體。
- **建議修法**：改成分批拉取粉絲，或改由事件系統異步處理。

## 3. 安全問題

### 3.1 刪圖接口存在路徑穿越，可刪除上傳目錄外檔案
- **嚴重等級**：高
- **位置**：`backend-java/src/main/java/com/hmdp/controller/UploadController.java:38`、`backend-java/src/main/java/com/hmdp/controller/UploadController.java:39`、`backend-java/src/main/java/com/hmdp/controller/UploadController.java:43`
- **問題描述**：`filename` 直接拼進 `new File(SystemConstants.IMAGE_UPLOAD_DIR, filename)`，只檢查 `isDirectory()`，沒有檢查 canonical path 是否仍在上傳根目錄下。
- **可能後果**：攻擊者可傳 `../` 類路徑，刪掉服務器上其他檔案。
- **建議修法**：限制檔名格式、解析 canonical path、驗證必須位於白名單根目錄內，再刪除。

### 3.2 驗證碼直接寫入 debug log，屬敏感資訊外洩
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/service/impl/UserServiceImpl.java:62`
- **問題描述**：登入簡訊驗證碼直接記錄到日誌。
- **可能後果**：任何可讀 log 的人都能接管帳號登入流程。
- **建議修法**：不要記錄驗證碼；若需追蹤，只記錄手機末碼與 request id。

### 3.3 資料庫密碼直接硬編碼在 repo 內
- **嚴重等級**：高
- **位置**：`backend-java/src/main/resources/application.yaml:6`、`backend-java/src/main/resources/application.yaml:10`
- **問題描述**：`spring.datasource.password: password` 直接寫死在版本控制檔案中。
- **可能後果**：一旦 repo 外流，等於直接洩漏資料庫憑證；也不利於不同環境隔離。
- **建議修法**：改用環境變數、外部化設定或 secret manager；repo 內只留 `.example`。

### 3.4 自製密碼工具仍使用 MD5，若後續啟用不符合現代密碼學要求
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/utils/PasswordEncoder.java:11`、`backend-java/src/main/java/com/hmdp/utils/PasswordEncoder.java:19`
- **問題描述**：`PasswordEncoder` 採用加鹽 MD5。即使目前未看到登入流程實際使用此類別，該工具仍具誤用風險。
- **可能後果**：未來若接上密碼登入，容易被暴力破解或彩虹表攻擊。
- **建議修法**：改成 Spring Security `BCryptPasswordEncoder`、`Argon2PasswordEncoder` 等現代方案。

補充：本次未發現明顯 SQL 注入點、CORS 過寬配置或 JWT 驗簽流程問題。目前專案主要是 Redis token + 攔截器模型，非 JWT。

## 4. 架構問題

### 4.1 Controller 直接寫查詢與分頁邏輯，責任邊界混亂
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/controller/ShopController.java:91`、`backend-java/src/main/java/com/hmdp/controller/BlogController.java:45`、`backend-java/src/main/java/com/hmdp/controller/BlogController.java:49`、`backend-java/src/main/java/com/hmdp/controller/BlogController.java:71`、`backend-java/src/main/java/com/hmdp/controller/BlogController.java:76`
- **問題描述**：Controller 直接使用 `blogService.query()`、`shopService.query()` 組 SQL 條件與分頁，而非委派 service 封裝。
- **可能後果**：控制層變胖，規則散落，未來換 ORM 或補業務校驗時很難統一收口。
- **建議修法**：把查詢條件、分頁、DTO 組裝都收斂到 service/application service。

### 4.2 Service 層直接拼接原生 SQL 片段
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:109`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:116`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:139`、`backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:202`、`backend-java/src/main/java/com/hmdp/service/impl/ShopServiceImpl.java:277`
- **問題描述**：多處使用 `setSql(...)` 與 `last("ORDER BY FIELD(...)")` 直接嵌 raw SQL。
- **可能後果**：ORM 封裝被打穿，可維護性下降；後續切 JPA 時這些邏輯都得重寫。
- **建議修法**：把排序/批量更新收斂到 mapper 或 repository，並用更明確的資料存取接口封裝。

### 4.3 基礎設施配置硬編碼，環境可攜性差
- **嚴重等級**：中
- **位置**：`backend-java/src/main/java/com/hmdp/utils/SystemConstants.java:4`、`backend-java/src/main/java/com/hmdp/config/RedissonConfig.java:16`、`backend-java/src/main/resources/application.yaml:8`
- **問題描述**：上傳路徑使用開發者本機絕對路徑，Redisson 連線位址直接寫死，DB URL 也固定綁本機。
- **可能後果**：換機器、換環境、容器化部署都容易直接失敗。
- **建議修法**：全面改成 `@ConfigurationProperties` 或環境變數注入，避免程式碼內硬編碼。

補充：本次未發現明顯循環依賴，也沒有超過 500 行的類別。

## 5. Spring Boot 3.x 升級需修改項

### 5.1 專案仍停在 Spring Boot 2.7.4
- **嚴重等級**：中
- **位置**：`backend-java/pom.xml:15`
- **問題描述**：parent 版本仍是 `2.7.4`，尚未進入 Spring Framework 6 / Spring Boot 3 生態。
- **可能後果**：無法直接享用 Boot 3 的 Jakarta / JDK 17 / 新版依賴體系。
- **建議修法**：先升到最新 2.7.x 驗證，再切到 3.x。

### 5.2 Java 版本仍是 11，無法滿足 Spring Boot 3 最低要求
- **嚴重等級**：高
- **位置**：`backend-java/pom.xml:20`、`backend-java/pom.xml:21`、`backend-java/pom.xml:22`、`backend-java/pom.xml:118`、`backend-java/pom.xml:119`
- **問題描述**：`java.version`、compiler source/target 全部仍為 11。Spring Boot 3 需要 Java 17+。
- **可能後果**：升版後直接無法編譯或啟動。
- **建議修法**：先把建置與執行環境升到 Java 17，再處理框架遷移。

### 5.3 `javax.*` 共有 25 處 import，Boot 3 必須改成 `jakarta.*`
- **嚴重等級**：高
- **位置**：
  - `backend-java/src/main/java/com/hmdp/config/MvcConfig.java:10`
  - `backend-java/src/main/java/com/hmdp/controller/UserController.java:16`
  - `backend-java/src/main/java/com/hmdp/controller/UserController.java:17`
  - `backend-java/src/main/java/com/hmdp/controller/FollowController.java:8`
  - `backend-java/src/main/java/com/hmdp/controller/ShopController.java:12`
  - `backend-java/src/main/java/com/hmdp/controller/VoucherController.java:9`
  - `backend-java/src/main/java/com/hmdp/controller/ShopTypeController.java:11`
  - `backend-java/src/main/java/com/hmdp/controller/BlogController.java:15`
  - `backend-java/src/main/java/com/hmdp/controller/VoucherOrderController.java:11`
  - `backend-java/src/main/java/com/hmdp/service/IUserService.java:8`
  - `backend-java/src/main/java/com/hmdp/service/impl/BlogServiceImpl.java:24`
  - `backend-java/src/main/java/com/hmdp/service/impl/FollowServiceImpl.java:16`
  - `backend-java/src/main/java/com/hmdp/service/impl/ShopServiceImpl.java:26`
  - `backend-java/src/main/java/com/hmdp/service/impl/ShopTypeServiceImpl.java:13`
  - `backend-java/src/main/java/com/hmdp/service/impl/UserServiceImpl.java:21`
  - `backend-java/src/main/java/com/hmdp/service/impl/UserServiceImpl.java:22`
  - `backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:23`
  - `backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:24`
  - `backend-java/src/main/java/com/hmdp/service/impl/VoucherServiceImpl.java:14`
  - `backend-java/src/main/java/com/hmdp/utils/LoginIntercepter.java:11`
  - `backend-java/src/main/java/com/hmdp/utils/LoginIntercepter.java:12`
  - `backend-java/src/main/java/com/hmdp/utils/LoginIntercepter.java:13`
  - `backend-java/src/main/java/com/hmdp/utils/RefreshTokenIntercepter.java:10`
  - `backend-java/src/main/java/com/hmdp/utils/RefreshTokenIntercepter.java:11`
  - `backend-java/src/test/java/com/hmdp/HmDianPingApplicationTests.java:12`
- **問題描述**：Servlet、`@Resource`、`@PostConstruct` 仍全面使用 `javax.*`。
- **可能後果**：升到 Boot 3 / Spring 6 後會直接編譯失敗。
- **建議修法**：全面替換為 `jakarta.servlet.*`、`jakarta.annotation.*`，並重新驗證測試與相依套件。

### 5.4 MyBatis-Plus starter 仍是 Boot 2 版座標
- **嚴重等級**：高
- **位置**：`backend-java/pom.xml:71`
- **問題描述**：目前使用 `mybatis-plus-boot-starter`。Boot 3 應切換到 `mybatis-plus-spring-boot3-starter`。
- **可能後果**：升版後容易碰到 Jakarta / Spring 6 相依不相容。
- **建議修法**：升版時改用 Boot 3 對應 starter，並同步檢查 MyBatis-Plus 版本。

補充：本專案目前未直接使用 `WebSecurityConfigurerAdapter`，也未看到 Jackson、Lombok 的明顯升級 blocker。Boot 3 破壞性風險主要集中在 Java 17、`javax` → `jakarta`、MyBatis-Plus starter。

## 附錄：建議優先順序
1. [必修，影響升級] 先處理 Java 17、25 處 `javax.*`、MyBatis-Plus Boot 3 starter。
2. [必修，影響線上正確性] 修正秒殺接口忽略 Lua 結果、登出 token 未失效、上傳刪圖路徑穿越。
3. [強烈建議修，影響穩定性] 補 Redis Stream consumer group 初始化，移除異步下單對共享 `proxy` 的依賴。
4. [強烈建議修，影響效能] 修正 blog 熱門/關注流 N+1，將粉絲推送改批次或非同步。
5. [可選修] 收斂 Controller 業務邏輯、移除 service 層 raw SQL、把硬編碼環境配置外部化。
