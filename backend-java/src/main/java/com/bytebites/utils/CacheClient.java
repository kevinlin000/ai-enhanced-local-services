package com.bytebites.utils;

import cn.hutool.core.util.BooleanUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;

import static com.bytebites.utils.RedisConstants.*;

@Slf4j
@Component
public class CacheClient {

    private final StringRedisTemplate stringRedisTemplate;

    @Autowired
    public CacheClient(StringRedisTemplate stringRedisTemplate) {
        this.stringRedisTemplate = stringRedisTemplate;
    }

        public void set(String key, Object value, Long time, TimeUnit unit) {
            stringRedisTemplate.opsForValue().set(key, JSONUtil.toJsonStr(value), time, unit);
        }

        public void setWithLogicalEpire(String key, Object value, Long time, TimeUnit unit) {
            //設置邏輯過期
            RedisData redisData = new RedisData();
            redisData.setData(value);
            redisData.setExpireTime(LocalDateTime.now().plusSeconds(unit.toSeconds(time)));
            //寫入Redis
            stringRedisTemplate.opsForValue().set(key, JSONUtil.toJsonStr(redisData));
        }

    public <R, ID> R queryWithPassThrough(
            String keyPrefix, ID id,Class<R> type, Function<ID, R> dbfallback, Long time, TimeUnit unit) {
        String key = keyPrefix+ id;
        //1.從redis查詢商家緩存
        String json = stringRedisTemplate.opsForValue().get(key);

        //2.判斷是否存在
        if (StrUtil.isNotBlank(json)) {
            //3.存在，直接返回
            return  JSONUtil.toBean(json, type);
        }

        //判斷命中的是否是空值
        if(json != null){
            //返回一個錯誤資訊
            return null;
        }
        //4.不存在，根據id查詢數據庫
        R r = dbfallback.apply(id);
        //5.不存在，返回錯誤
        if (r == null) {
            //將空值寫入redis
            stringRedisTemplate.opsForValue().set(key, "", CACHE_NULL_TTL, TimeUnit.MINUTES);
            //返回錯誤資訊
            return null;
        }
        //6. 存在，寫入redis
        this.set(key, r, time, unit);

        //7.返回
        return r;
    }


    private static final ExecutorService CACHE_REBUILD_EXECUTOR = Executors.newFixedThreadPool(10);

    public <R, ID> R  queryWithLogicalExpire (
            String keyPrefix ,ID id, Class<R> type, Function<ID, R> dbFallback, Long time, TimeUnit unit) {
        String key = keyPrefix + id;
        //1.從redis查詢商家緩存
        String json = stringRedisTemplate.opsForValue().get(key);

        //2.判斷是否存在
        if (StrUtil.isBlank(json)) {
            //3.存在，直接返回
            return  null;
        }
        //4.命中，需要先把json反序列化為對象
        RedisData redisData = JSONUtil.toBean(json, RedisData.class);
        R r = JSONUtil.toBean((JSONObject) redisData.getData(), type);
        LocalDateTime expireTime = redisData.getExpireTime();
        //5. 判斷是否過期
        if (expireTime.isAfter(LocalDateTime.now())) {
            //5.1 未過期，直接返回店家資訊
            return r;
        }

        //5.2 已過期，需要緩存重建
        //6. 緩存重建
        //6.1 獲取互斥鎖
        String  lockKey = LOCK_SHOP_KEY + id;
        boolean isLock = tryLock(lockKey);
        //6.2 判斷是否獲取成功
        if (isLock) {
            //6.3 成功，則開啟獨立線程，實現緩存重建
            CACHE_REBUILD_EXECUTOR.submit(() -> {
                try {
                    //查詢數據庫
                    R r1 = dbFallback.apply(id);
                    //寫入redis
                    this.setWithLogicalEpire(key, r1, time, unit);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                } finally {
                    //釋放鎖
                    unLock(lockKey);
                }
            });
        }
        //6.4 失敗，則返回過期的店家資訊
        return r;
    }

    private boolean tryLock(String key) {
        Boolean flag = stringRedisTemplate.opsForValue().setIfAbsent(key, "1", LOCK_SHOP_TTL, TimeUnit.SECONDS);
        return BooleanUtil.isTrue(flag);
    }

    private void unLock(String key) {
        stringRedisTemplate.delete(key);
    }
}
