package com.bytebites.config;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MetricsConfig {

    @Bean
    public Counter seckillAttempts(MeterRegistry registry) {
        return Counter.builder("bytebites.seckill.attempts").register(registry);
    }

    @Bean
    public Counter rateLimitRejects(MeterRegistry registry) {
        return Counter.builder("bytebites.ratelimit.rejects").register(registry);
    }

    @Bean
    public Counter outboxPublished(MeterRegistry registry) {
        return Counter.builder("bytebites.outbox.published").register(registry);
    }
}
