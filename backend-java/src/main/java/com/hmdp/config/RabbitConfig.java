package com.hmdp.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitConfig {

    public static final String DEMO_QUEUE = "demo.hello";
    public static final String DEMO_EXCHANGE = "demo.exchange";
    public static final String DEMO_ROUTING_KEY = "hello";
    public static final String DEMO_DLX = "demo.dlx";
    public static final String DEMO_DLQ = "demo.dlq";
    public static final String DEMO_DLQ_ROUTING_KEY = "dlq";

    @Bean
    public Queue demoQueue() {
        return QueueBuilder.durable(DEMO_QUEUE)
                .withArgument("x-dead-letter-exchange", DEMO_DLX)
                .withArgument("x-dead-letter-routing-key", DEMO_DLQ_ROUTING_KEY)
                .build();
    }

    @Bean
    public DirectExchange demoExchange() {
        return new DirectExchange(DEMO_EXCHANGE, true, false);
    }

    @Bean
    public DirectExchange dlxExchange() {
        return new DirectExchange(DEMO_DLX, true, false);
    }

    @Bean
    public Queue dlqQueue() {
        return QueueBuilder.durable(DEMO_DLQ).build();
    }

    @Bean
    public Binding demoBinding(Queue demoQueue, DirectExchange demoExchange) {
        return BindingBuilder.bind(demoQueue).to(demoExchange).with(DEMO_ROUTING_KEY);
    }

    @Bean
    public Binding dlqBinding(Queue dlqQueue, DirectExchange dlxExchange) {
        return BindingBuilder.bind(dlqQueue).to(dlxExchange).with(DEMO_DLQ_ROUTING_KEY);
    }
}
