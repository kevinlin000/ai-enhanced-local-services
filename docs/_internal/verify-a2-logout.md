# 驗證報告：A2 登出 Token 失效（commit 0716f6c）

## 逐項驗證

1. **token 來源**：從 `request.getHeader("authorization")` 取得；`logout()` 以 `token != null && !token.isBlank()` 判斷，空值和 null 均不會觸發 Redis 刪除，有正確防護。

2. **key 組合**：`logout()` 用 `LOGIN_USER_KEY + token`，`RefreshTokenIntercepter` 也用 `RedisConstants.LOGIN_USER_KEY + token`，兩邊使用同一個常數，key 完全一致。

3. **刪除順序**：先刪 Redis（`stringRedisTemplate.delete()`），再清 ThreadLocal（`UserHolder.removeUser()`）；先清外部共享狀態再清本地狀態，順序合理。

4. **回傳值**：`stringRedisTemplate.delete()` 回傳值不使用；無論 key 是否存在，一律回 `Result.ok()`，已登出或 token 過期的情況不會報錯。

5. **攔截器影響**：登出後 Redis key 已刪；同一 token 再帶過來，`RefreshTokenIntercepter` 取得空 `userMap`，走 `return true` 放行但不呼叫 `UserHolder.saveUser()` 也不刷新 TTL，token 不會復活。

## 附加觀察（不影響結論）

`UserServiceImpl.login()` 第 104–106 行對同一 key 執行兩次 `putAll`（重複寫入），屬冗餘但不影響正確性，可在 Batch B 清理。

## 結論：通過
