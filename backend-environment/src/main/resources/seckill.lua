-- 1.參數列表
--1.1 優惠券id
local voucherId = ARGV[1]
--1.2 用戶id
local userId = ARGV[2]
--1.3 訂單id
local orderId = ARGV[3]

-- 2.數據key
-- 2.1 庫存key
local stockKey = 'seckill:stock:' .. voucherId
-- 2.2 訂單key
local orderKey = 'seckill:order:' .. voucherId

-- 3.腳本邏輯
-- 3.1 判斷庫存是否充足
if (tonumber(redis.call('get', stockKey)) <= 0) then
    -- 3.1.1 庫存不足，返回1
    return 1
end

-- 3.2 判斷用戶是否已經搶購過了
if (redis.call('sismember', orderKey, userId) == 1) then
    -- 3.2.1 已經搶購過了，返回2
    return 2
end

-- 3.3 扣減庫存
redis.call('incrby', stockKey, -1)
-- 3.4 下單（保存用戶）
redis.call('sadd', orderKey, userId)
-- 3.5 下單成功，返回0
-- 3.6 發送消息到消息隊列
redis.call('xadd', 'stream.orders', '*', 'userId', userId, 'voucherId', voucherId, 'id', orderId)
return 0
