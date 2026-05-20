package com.hmdp.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.hmdp.entity.OutboxMessage;

public interface IOutboxService extends IService<OutboxMessage> {

    void save(String aggregateType, Long aggregateId, String eventType, String exchange, String routingKey, Object payload);
}
