package com.bytebites.config;

import com.bytebites.utils.RedisConstants;
import com.bytebites.entity.SeckillVoucher;
import com.bytebites.service.ISeckillVoucherService;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Pre-loads Redis stock keys for Flyway-seeded flash deals.
 * Flyway inserts bypass addSeckillVoucher, so Redis stock must be bridged on startup.
 */
@Component
public class DemoDataInitializer implements ApplicationRunner {

    private final StringRedisTemplate redisTemplate;
    private final ISeckillVoucherService seckillVoucherService;

    public DemoDataInitializer(StringRedisTemplate redisTemplate, ISeckillVoucherService seckillVoucherService) {
        this.redisTemplate = redisTemplate;
        this.seckillVoucherService = seckillVoucherService;
    }

    @Override
    public void run(ApplicationArguments args) {
        LocalDateTime now = LocalDateTime.now();
        List<SeckillVoucher> vouchers = seckillVoucherService.list();
        vouchers.stream()
                .filter(voucher -> voucher.getVoucherId() != null)
                .filter(voucher -> voucher.getStock() != null && voucher.getStock() > 0)
                .filter(voucher -> voucher.getEndTime() == null || voucher.getEndTime().isAfter(now))
                .forEach(voucher -> {
                    Long voucherId = voucher.getVoucherId();
                    Integer stock = voucher.getStock();
                    String key = RedisConstants.SECKILL_STOCK_KEY + voucherId;
                    redisTemplate.opsForValue().setIfAbsent(key, stock.toString());
                });
    }
}
