package com.bytebites.utils;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;

@Component
public class RedisIdWorker {

    /**
     * 開始時間戳
     */
    private static final long BEGIN_TIMESTAMP = 1767225600L;
    /**
     * 序列號的位數
     */
    private static final int COUNT_BITS = 32;

    private StringRedisTemplate stringRedisTemplate;

    public RedisIdWorker(StringRedisTemplate stringRedisTemplate) {
        this.stringRedisTemplate = stringRedisTemplate;
    }

    public long nextId(String keyPrefix){
        // 1. 生成時間戳
            LocalDateTime now = LocalDateTime.now();
            long nowSecond = now.toEpochSecond(ZoneOffset.UTC);
            long timestamp = nowSecond - BEGIN_TIMESTAMP;
        //2.生成序列號
        //2.1獲取當前日期，精確到天
        String date = now.format(DateTimeFormatter.ofPattern("yyyy:MM:dd"));
        //2.2 自增長
        long count = stringRedisTemplate.opsForValue().increment("icr:" + keyPrefix + ":" + date);


        //3.拼接並且返回
        return timestamp << COUNT_BITS | count;

    }

}
