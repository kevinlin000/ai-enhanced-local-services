package com.hmdp.config;

import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RBloomFilter;
import org.redisson.api.RedissonClient;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;

@Slf4j
@Configuration
public class BloomFilterConfig {

    public static final String SHOP_BLOOM_KEY = "shop:bloom";

    @Bean
    public RBloomFilter<Long> shopBloomFilter(RedissonClient redissonClient) {
        RBloomFilter<Long> bloomFilter = redissonClient.getBloomFilter(SHOP_BLOOM_KEY);
        bloomFilter.tryInit(10000, 0.01);
        return bloomFilter;
    }

    @Bean
    public ApplicationRunner shopBloomLoader(JdbcTemplate jdbcTemplate, RBloomFilter<Long> shopBloomFilter) {
        return new ApplicationRunner() {
            @Override
            public void run(ApplicationArguments args) {
                List<Long> shopIds = jdbcTemplate.query(
                        "SELECT id FROM tb_shop",
                        (rs, rowNum) -> rs.getLong("id")
                );
                for (Long shopId : shopIds) {
                    shopBloomFilter.add(shopId);
                }
                log.info("loaded {} shop ids into bloom filter", shopIds.size());
            }
        };
    }
}
