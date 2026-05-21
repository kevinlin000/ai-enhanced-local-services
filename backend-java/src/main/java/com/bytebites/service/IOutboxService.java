package com.bytebites.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.bytebites.entity.OutboxMessage;

public interface IOutboxService extends IService<OutboxMessage> {

    void save(String aggregateType, Long aggregateId, String eventType, String exchange, String routingKey, Object payload);
}
