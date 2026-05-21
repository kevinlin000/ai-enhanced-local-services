package com.bytebites;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.EnableAspectJAutoProxy;
import org.springframework.scheduling.annotation.EnableScheduling;

@EnableAspectJAutoProxy(exposeProxy = true)
@EnableScheduling
@MapperScan("com.bytebites.mapper")
@SpringBootApplication
public class ByteBitesApplication {

    public static void main(String[] args) {
        SpringApplication.run(ByteBitesApplication.class, args);
    }

}
