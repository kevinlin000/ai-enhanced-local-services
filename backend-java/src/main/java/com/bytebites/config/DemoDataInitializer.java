package com.bytebites.config;

import com.bytebites.utils.RedisConstants;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * Pre-loads seckill stock keys into Redis for V12 demo vouchers.
 * These vouchers were seeded via Flyway (bypassing addSeckillVoucher),
 * so Redis never got populated — this bridges that gap on startup.
 */
@Component
public class DemoDataInitializer implements ApplicationRunner {

    private final StringRedisTemplate redisTemplate;

    public DemoDataInitializer(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    private static final Map<Long, Integer> DEMO_SECKILL_STOCK = Map.of(
            30101L, 50,
            30102L, 30,
            30103L, 20,
            30104L, 80,
            30105L, 40
    );

    @Override
    public void run(ApplicationArguments args) {
        DEMO_SECKILL_STOCK.forEach((voucherId, stock) -> {
            String key = RedisConstants.SECKILL_STOCK_KEY + voucherId;
            redisTemplate.opsForValue().setIfAbsent(key, stock.toString());
        });
    }
}
