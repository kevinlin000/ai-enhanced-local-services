package com.hmdp.controller;

import com.hmdp.config.RabbitConfig;
import com.hmdp.dto.Result;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/demo")
public class DemoMqController {

    private final RabbitTemplate rabbitTemplate;

    public DemoMqController(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
    }

    @PostMapping("/mq")
    public Result publish(@RequestParam String msg) {
        rabbitTemplate.convertAndSend(RabbitConfig.DEMO_EXCHANGE, RabbitConfig.DEMO_ROUTING_KEY, msg);
        return Result.ok();
    }
}
