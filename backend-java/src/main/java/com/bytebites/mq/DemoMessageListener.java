package com.bytebites.mq;

import com.bytebites.config.RabbitConfig;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class DemoMessageListener {

    @RabbitListener(queues = RabbitConfig.DEMO_QUEUE)
    public void receive(String message) {
        log.info("RabbitMQ received: {}", message);
        if (message.contains("BOOM")) {
            throw new RuntimeException("simulated failure");
        }
    }

    @RabbitListener(queues = RabbitConfig.DEMO_DLQ)
    public void receiveDLQ(String message) {
        log.warn("DLQ received: {}", message);
    }
}
