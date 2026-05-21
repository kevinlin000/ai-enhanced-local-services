package com.bytebites.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.data.geo.Point;
import org.springframework.data.redis.connection.RedisGeoCommands;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

@Slf4j
@Component
public class MrtGeoLoader implements ApplicationRunner {

    private static final String MRT_GEO_KEY = "mrt:stations:geo";

    private final JdbcTemplate jdbcTemplate;
    private final StringRedisTemplate stringRedisTemplate;

    public MrtGeoLoader(JdbcTemplate jdbcTemplate, StringRedisTemplate stringRedisTemplate) {
        this.jdbcTemplate = jdbcTemplate;
        this.stringRedisTemplate = stringRedisTemplate;
    }

    @Override
    public void run(ApplicationArguments args) {
        List<Map<String, Object>> stations = jdbcTemplate.queryForList(
                "SELECT name, x, y FROM tb_mrt_station ORDER BY id"
        );
        for (Map<String, Object> station : stations) {
            stringRedisTemplate.opsForGeo().add(
                    MRT_GEO_KEY,
                    new RedisGeoCommands.GeoLocation<>(
                            station.get("name").toString(),
                            new Point(
                                    ((Number) station.get("x")).doubleValue(),
                                    ((Number) station.get("y")).doubleValue()
                            )
                    )
            );
        }
        log.info("loaded {} mrt stations into redis geo key {}", stations.size(), MRT_GEO_KEY);
    }
}
