
-- 比較線程標識與鎖中的標識是否一致
if (redis.call("get", KEYS[1]) == ARGV[1]) then
    -- 刪除鎖 del key
    return redis.call("del", KEYS[1])
end
-- 返回0，表示刪除失敗
return 0