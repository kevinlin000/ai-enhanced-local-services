package com.bytebites.service.impl;

import org.junit.jupiter.api.Test;
import org.springframework.data.redis.RedisSystemException;
import org.springframework.data.redis.core.RedisCallback;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class VoucherOrderServiceImplTest {

    @Test
    void ensuresOrderStreamGroupBeforeConsumerStarts() {
        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        VoucherOrderServiceImpl service = service(redis);

        service.ensureOrderStreamGroup();

        verify(redis).execute(any(RedisCallback.class));
    }

    @Test
    void existingOrderStreamGroupIsIdempotent() {
        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        when(redis.execute(any(RedisCallback.class))).thenThrow(
                new RedisSystemException("BUSYGROUP Consumer Group name already exists", new RuntimeException())
        );

        assertThatCode(() -> service(redis).ensureOrderStreamGroup()).doesNotThrowAnyException();
    }

    @Test
    void unexpectedRedisFailureStillFailsInitialization() {
        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        when(redis.execute(any(RedisCallback.class))).thenThrow(
                new RedisSystemException("connection refused", new RuntimeException())
        );

        assertThatCode(() -> service(redis).ensureOrderStreamGroup())
                .isInstanceOf(RedisSystemException.class);
    }

    private VoucherOrderServiceImpl service(StringRedisTemplate redis) {
        VoucherOrderServiceImpl service = new VoucherOrderServiceImpl();
        ReflectionTestUtils.setField(service, "stringRedisTemplate", redis);
        return service;
    }
}
