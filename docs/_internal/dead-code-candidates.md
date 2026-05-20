# Dead Code Candidates

以下是目前「明顯像死代碼，但本批先不刪」的候選清單。

## 1. `SimpleRedisLock`
- 位置：`backend-java/src/main/java/com/hmdp/utils/SimpleRedisLock.java`
- 證據：全專案唯一額外命中只剩註解引用，見 `backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java:259`
- 判斷：目前專案已改用 Redisson，這個自製 Redis lock 看起來已退役

## 2. `ILock`
- 位置：`backend-java/src/main/java/com/hmdp/utils/ILock.java`
- 證據：只被 `SimpleRedisLock` 實作，找不到其他使用點
- 判斷：若 `SimpleRedisLock` 確認刪除，`ILock` 也可一起移除

## 3. `RedisIdWorker.main()`
- 位置：`backend-java/src/main/java/com/hmdp/utils/RedisIdWorker.java:45`
- 證據：專案內只有兩個 `main()`；一個是應用入口，另一個是這個手動時間戳小工具
- 判斷：類別本身有用，但 `main()` 方法像一次性除錯殘留

## 4. `BlogCommentsController`
- 位置：`backend-java/src/main/java/com/hmdp/controller/BlogCommentsController.java`
- 證據：類別存在，但沒有任何 endpoint method，只有空 controller 殼
- 判斷：像是生成後未實作的 scaffolding

## 5. `IBlogCommentsService` / `BlogCommentsServiceImpl`
- 位置：
  - `backend-java/src/main/java/com/hmdp/service/IBlogCommentsService.java`
  - `backend-java/src/main/java/com/hmdp/service/impl/BlogCommentsServiceImpl.java`
- 證據：全專案搜尋只找到介面定義、實作本身、以及空 controller；沒有其他 service/controller 呼叫
- 判斷：高機率是未完成功能留下的 scaffolding

## 6. 大段註解舊實作
- 位置：
  - `backend-java/src/main/java/com/hmdp/service/impl/VoucherOrderServiceImpl.java`
  - `backend-java/src/main/java/com/hmdp/service/impl/ShopServiceImpl.java`
  - `backend-java/src/main/java/com/hmdp/utils/SimpleRedisLock.java`
- 證據：保留大量完整舊版本方法與流程，已不參與編譯
- 判斷：不算「類別死代碼」，但屬明顯清理候選，會增加閱讀噪音
