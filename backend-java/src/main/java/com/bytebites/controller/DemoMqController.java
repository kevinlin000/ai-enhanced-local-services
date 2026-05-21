package com.bytebites.controller;

import com.bytebites.config.RabbitConfig;
import com.bytebites.dto.Result;
import com.bytebites.service.IOutboxService;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/demo")
public class DemoMqController {

    private final RabbitTemplate rabbitTemplate;
    private final IOutboxService outboxService;

    public DemoMqController(RabbitTemplate rabbitTemplate, IOutboxService outboxService) {
        this.rabbitTemplate = rabbitTemplate;
        this.outboxService = outboxService;
    }

    @PostMapping("/mq")
    public Result publish(@RequestParam String msg) {
        rabbitTemplate.convertAndSend(RabbitConfig.DEMO_EXCHANGE, RabbitConfig.DEMO_ROUTING_KEY, msg);
        return Result.ok();
    }

    @PostMapping("/mq-outbox")
    @Transactional
    public Result publishViaOutbox(@RequestParam String msg) {
        outboxService.save(
                "DEMO",
                System.currentTimeMillis(),
                "demo.message",
                RabbitConfig.DEMO_EXCHANGE,
                RabbitConfig.DEMO_ROUTING_KEY,
                Map.of("msg", msg)
        );
        return Result.ok();
    }
}
