package com.bytebites.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.bytebites.entity.OutboxMessage;
import com.bytebites.mapper.OutboxMessageMapper;
import com.bytebites.service.IOutboxService;
import org.springframework.stereotype.Service;

@Service
public class OutboxServiceImpl extends ServiceImpl<OutboxMessageMapper, OutboxMessage> implements IOutboxService {

    private final ObjectMapper objectMapper;

    public OutboxServiceImpl(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void save(String aggregateType, Long aggregateId, String eventType, String exchange, String routingKey, Object payload) {
        OutboxMessage outboxMessage = new OutboxMessage()
                .setAggregateType(aggregateType)
                .setAggregateId(aggregateId)
                .setEventType(eventType)
                .setExchange(exchange)
                .setRoutingKey(routingKey)
                .setPayload(toJson(payload))
                .setStatus(0)
                .setRetryCount(0);
        save(outboxMessage);
    }

    private String toJson(Object payload) {
        try {
            return objectMapper.writeValueAsString(payload);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("failed to serialize outbox payload", e);
        }
    }
}
