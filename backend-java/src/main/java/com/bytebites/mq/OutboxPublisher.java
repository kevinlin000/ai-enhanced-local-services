package com.bytebites.mq;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bytebites.entity.OutboxMessage;
import com.bytebites.service.IOutboxService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Component
public class OutboxPublisher {

    private final IOutboxService outboxService;
    private final RabbitTemplate rabbitTemplate;

    public OutboxPublisher(IOutboxService outboxService, RabbitTemplate rabbitTemplate) {
        this.outboxService = outboxService;
        this.rabbitTemplate = rabbitTemplate;
    }

    @Scheduled(fixedDelay = 2000)
    public void publish() {
        List<OutboxMessage> messages = outboxService.query()
                .eq("status", 0)
                .orderByAsc("created_at")
                .last("LIMIT 50")
                .list();

        for (OutboxMessage message : messages) {
            try {
                rabbitTemplate.convertAndSend(message.getExchange(), message.getRoutingKey(), message.getPayload());
                outboxService.lambdaUpdate()
                        .eq(OutboxMessage::getId, message.getId())
                        .set(OutboxMessage::getStatus, 1)
                        .set(OutboxMessage::getSentAt, LocalDateTime.now())
                        .update();
            } catch (Exception e) {
                int nextRetryCount = message.getRetryCount() + 1;
                int nextStatus = nextRetryCount >= 3 ? 2 : 0;
                outboxService.lambdaUpdate()
                        .eq(OutboxMessage::getId, message.getId())
                        .set(OutboxMessage::getRetryCount, nextRetryCount)
                        .set(OutboxMessage::getStatus, nextStatus)
                        .update();
                log.error("failed to publish outbox message id={}", message.getId(), e);
            }
        }
    }
}
