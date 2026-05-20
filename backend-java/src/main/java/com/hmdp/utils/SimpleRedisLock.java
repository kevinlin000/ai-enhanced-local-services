package com.hmdp.utils;

import cn.hutool.core.lang.UUID;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;

import java.util.Collections;
import java.util.concurrent.TimeUnit;

/**
 * 手刻分散式鎖示範（教學用，非生產代碼）。
 * <p>
 * 本類別保留作為「為什麼最終選擇 Redisson 而非自製鎖」的對照範例：
 * - 缺乏可重入支援
 * - 釋放鎖時的擁有者驗證需自行處理
 * - 看門狗機制需自行實作
 * <p>
 * 實際生產使用請見 {@link org.redisson.api.RLock}。
 */
@Deprecated
public class SimpleRedisLock implements ILock {

    private String name; // 鎖的名字
    private StringRedisTemplate stringRedisTemplate; // Redis 客戶端



    public SimpleRedisLock(String name, StringRedisTemplate stringRedisTemplate) {
        this.name = name;
        this.stringRedisTemplate = stringRedisTemplate;
    }

    private static final String KEY_PREFIX = "lock:";
    private static final String ID_PREFIX = UUID.randomUUID().toString(true) + "-";
    private static final DefaultRedisScript<Long> UNLOCK_SCRIPT;
    static {
        UNLOCK_SCRIPT = new DefaultRedisScript<>();
        UNLOCK_SCRIPT.setLocation(new ClassPathResource("unlock.lua"));
        UNLOCK_SCRIPT.setResultType(Long.class);
    }

    @Override
    public boolean tryLock(long timeoutSec) {
        //獲取線程標識
        String theardId = ID_PREFIX + Thread.currentThread().getId();
        // 嘗試獲取鎖，使用 SETNX 命令
        Boolean success = stringRedisTemplate.opsForValue()
                .setIfAbsent(KEY_PREFIX + name, theardId, timeoutSec, TimeUnit.SECONDS);
        return Boolean.TRUE.equals(success);
    }

    @Override
    public void unlock() {
        //調用lua腳本
        stringRedisTemplate.execute(
                UNLOCK_SCRIPT,
                Collections.singletonList(KEY_PREFIX + name),
                ID_PREFIX + Thread.currentThread().getId()
        );
    }
}
