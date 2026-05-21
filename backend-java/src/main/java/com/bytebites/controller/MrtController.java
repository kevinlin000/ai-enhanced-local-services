package com.bytebites.controller;

import com.bytebites.domain.jpa.ShopJpa;
import com.bytebites.dto.Result;
import com.bytebites.repository.ShopJpaRepository;
import org.springframework.data.geo.Distance;
import org.springframework.data.geo.GeoResult;
import org.springframework.data.geo.GeoResults;
import org.springframework.data.redis.connection.RedisGeoCommands;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.domain.geo.GeoReference;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
public class MrtController {

    private static final String MRT_GEO_KEY = "mrt:stations:geo";
    private static final double EARTH_RADIUS_METERS = 6371000.0;

    private final JdbcTemplate jdbcTemplate;
    private final StringRedisTemplate stringRedisTemplate;
    private final ShopJpaRepository shopJpaRepository;

    public MrtController(JdbcTemplate jdbcTemplate, StringRedisTemplate stringRedisTemplate, ShopJpaRepository shopJpaRepository) {
        this.jdbcTemplate = jdbcTemplate;
        this.stringRedisTemplate = stringRedisTemplate;
        this.shopJpaRepository = shopJpaRepository;
    }

    @GetMapping("/api/mrt/stations")
    public Result listStations() {
        return Result.ok(queryAllStations());
    }

    @GetMapping("/api/mrt/stations/nearby")
    public Result nearbyStations(
            @RequestParam double lng,
            @RequestParam double lat,
            @RequestParam(defaultValue = "500") double radius
    ) {
        GeoResults<RedisGeoCommands.GeoLocation<String>> results = stringRedisTemplate.opsForGeo().search(
                MRT_GEO_KEY,
                GeoReference.fromCoordinate(lng, lat),
                new Distance(radius, RedisGeoCommands.DistanceUnit.METERS),
                RedisGeoCommands.GeoSearchCommandArgs.newGeoSearchArgs().includeDistance()
        );
        if (results == null || results.getContent().isEmpty()) {
            return Result.ok(Collections.emptyList());
        }

        Map<String, StationView> stationMap = queryAllStations().stream()
                .collect(Collectors.toMap(StationView::getName, station -> station));

        List<NearbyStationView> nearbyStations = results.getContent().stream()
                .map(result -> toNearbyStation(result, stationMap))
                .filter(item -> item != null)
                .collect(Collectors.toList());
        return Result.ok(nearbyStations);
    }

    @GetMapping("/api/shop/nearby-mrt/{stationName}")
    public Result nearbyShops(
            @PathVariable String stationName,
            @RequestParam(defaultValue = "500") double radius
    ) {
        StationView station = findStationByName(stationName);
        if (station == null) {
            return Result.fail("捷運站不存在");
        }

        List<ShopJpa> shops = shopJpaRepository.findByMrtStation(stationName);
        List<ShopJpa> nearbyShops = shops.stream()
                .peek(shop -> shop.setDistance(haversineMeters(station.getY(), station.getX(), shop.getY(), shop.getX())))
                .filter(shop -> shop.getDistance() != null && shop.getDistance() <= radius)
                .sorted(Comparator.comparing(ShopJpa::getDistance))
                .collect(Collectors.toList());
        return Result.ok(nearbyShops);
    }

    @GetMapping("/api/mrt/{station}/popular-shops")
    public Result popularShopsByMrt(@PathVariable String station) {
        List<ShopJpa> shops = shopJpaRepository.findByMrtStation(station);
        List<ShopJpa> sorted = shops.stream()
                .sorted((a, b) -> Integer.compare(
                        b.getScore() != null ? b.getScore() : 0,
                        a.getScore() != null ? a.getScore() : 0))
                .limit(5)
                .toList();
        return Result.ok(sorted);
    }

    private NearbyStationView toNearbyStation(
            GeoResult<RedisGeoCommands.GeoLocation<String>> result,
            Map<String, StationView> stationMap
    ) {
        String name = result.getContent().getName();
        StationView station = stationMap.get(name);
        if (station == null) {
            return null;
        }
        double distanceMeters = result.getDistance() == null ? 0.0 : result.getDistance().getValue();
        return new NearbyStationView(
                station.getId(),
                station.getName(),
                station.getLine(),
                station.getX(),
                station.getY(),
                station.getDistrict(),
                distanceMeters
        );
    }

    private List<StationView> queryAllStations() {
        return jdbcTemplate.query(
                "SELECT id, name, line, x, y, district FROM tb_mrt_station ORDER BY id",
                (rs, rowNum) -> new StationView(
                        rs.getLong("id"),
                        rs.getString("name"),
                        rs.getString("line"),
                        rs.getDouble("x"),
                        rs.getDouble("y"),
                        rs.getString("district")
                )
        );
    }

    private StationView findStationByName(String stationName) {
        List<StationView> stations = jdbcTemplate.query(
                "SELECT id, name, line, x, y, district FROM tb_mrt_station WHERE name = ? LIMIT 1",
                (rs, rowNum) -> new StationView(
                        rs.getLong("id"),
                        rs.getString("name"),
                        rs.getString("line"),
                        rs.getDouble("x"),
                        rs.getDouble("y"),
                        rs.getString("district")
                ),
                stationName
        );
        return stations.isEmpty() ? null : stations.get(0);
    }

    private double haversineMeters(double lat1, double lng1, double lat2, double lng2) {
        double latRad1 = Math.toRadians(lat1);
        double latRad2 = Math.toRadians(lat2);
        double latDiff = Math.toRadians(lat2 - lat1);
        double lngDiff = Math.toRadians(lng2 - lng1);
        double a = Math.sin(latDiff / 2) * Math.sin(latDiff / 2)
                + Math.cos(latRad1) * Math.cos(latRad2)
                * Math.sin(lngDiff / 2) * Math.sin(lngDiff / 2);
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return EARTH_RADIUS_METERS * c;
    }

    public static class StationView {
        private final Long id;
        private final String name;
        private final String line;
        private final Double x;
        private final Double y;
        private final String district;

        public StationView(Long id, String name, String line, Double x, Double y, String district) {
            this.id = id;
            this.name = name;
            this.line = line;
            this.x = x;
            this.y = y;
            this.district = district;
        }

        public Long getId() {
            return id;
        }

        public String getName() {
            return name;
        }

        public String getLine() {
            return line;
        }

        public Double getX() {
            return x;
        }

        public Double getY() {
            return y;
        }

        public String getDistrict() {
            return district;
        }
    }

    public static class NearbyStationView extends StationView {
        private final Double distanceMeters;

        public NearbyStationView(Long id, String name, String line, Double x, Double y, String district, Double distanceMeters) {
            super(id, name, line, x, y, district);
            this.distanceMeters = distanceMeters;
        }

        public Double getDistanceMeters() {
            return distanceMeters;
        }
    }
}
