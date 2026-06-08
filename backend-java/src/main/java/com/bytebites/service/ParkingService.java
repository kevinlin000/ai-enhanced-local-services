package com.bytebites.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class ParkingService {

    private static final String DESC_URL = "https://tcgbusfs.blob.core.windows.net/blobtcmsv/TCMSV_alldesc.json";
    private static final String AVAILABLE_URL = "https://tcgbusfs.blob.core.windows.net/blobtcmsv/TCMSV_allavailable.json";
    private static final Duration LOT_CACHE_TTL = Duration.ofHours(12);
    private static final Duration AVAILABILITY_CACHE_TTL = Duration.ofSeconds(30);
    private static final double EARTH_RADIUS_METERS = 6371000.0;

    private final ObjectMapper objectMapper;
    private final RestTemplate restTemplate;
    private final Clock clock;

    private List<ParkingLot> cachedLots = List.of();
    private Instant lotsLoadedAt = Instant.EPOCH;
    private Map<String, Availability> cachedAvailability = Map.of();
    private Instant availabilityLoadedAt = Instant.EPOCH;

    @Autowired
    public ParkingService(ObjectMapper objectMapper) {
        this(objectMapper, new RestTemplate(), Clock.systemUTC());
    }

    ParkingService(ObjectMapper objectMapper, RestTemplate restTemplate, Clock clock) {
        this.objectMapper = objectMapper;
        this.restTemplate = restTemplate;
        this.clock = clock;
    }

    public List<NearbyParkingLotView> nearby(double lng, double lat, int radiusMeters, int limit) {
        if (!isTaipeiLngLat(lng, lat)) {
            return List.of();
        }
        int safeRadius = Math.max(100, Math.min(radiusMeters, 2000));
        int safeLimit = Math.max(1, Math.min(limit, 10));
        Map<String, Availability> availability = loadAvailability();

        return loadLots().stream()
                .map(lot -> toNearbyView(lot, availability.get(lot.id()), lng, lat))
                .filter(view -> view.distanceMeters() <= safeRadius)
                .sorted(Comparator
                        .comparingInt(NearbyParkingLotView::distanceMeters)
                        .thenComparing((a, b) -> Integer.compare(
                                b.availableCar() == null ? -1 : b.availableCar(),
                                a.availableCar() == null ? -1 : a.availableCar()
                        )))
                .limit(safeLimit)
                .toList();
    }

    private synchronized List<ParkingLot> loadLots() {
        Instant now = clock.instant();
        if (!cachedLots.isEmpty() && now.minus(LOT_CACHE_TTL).isBefore(lotsLoadedAt)) {
            return cachedLots;
        }
        try {
            cachedLots = parseLots(fetchDescJson());
            lotsLoadedAt = now;
        } catch (Exception ignored) {
            if (cachedLots == null) {
                cachedLots = List.of();
            }
        }
        return cachedLots;
    }

    private synchronized Map<String, Availability> loadAvailability() {
        Instant now = clock.instant();
        if (!cachedAvailability.isEmpty() && now.minus(AVAILABILITY_CACHE_TTL).isBefore(availabilityLoadedAt)) {
            return cachedAvailability;
        }
        try {
            cachedAvailability = parseAvailability(fetchAvailableJson());
            availabilityLoadedAt = now;
        } catch (Exception ignored) {
            if (cachedAvailability == null) {
                cachedAvailability = Map.of();
            }
        }
        return cachedAvailability;
    }

    protected String fetchDescJson() {
        byte[] body = restTemplate.getForObject(DESC_URL, byte[].class);
        return body == null ? "{}" : new String(body, StandardCharsets.UTF_8);
    }

    protected String fetchAvailableJson() {
        byte[] body = restTemplate.getForObject(AVAILABLE_URL, byte[].class);
        return body == null ? "{}" : new String(body, StandardCharsets.UTF_8);
    }

    List<ParkingLot> parseLots(String json) throws IOException {
        JsonNode parks = parkArray(json);
        List<ParkingLot> lots = new ArrayList<>();
        if (!parks.isArray()) {
            return lots;
        }
        for (JsonNode item : parks) {
            String id = text(item, "id");
            String name = text(item, "name");
            double[] lngLat = extractLngLat(item);
            if (id.isBlank() || name.isBlank() || lngLat == null || !isTaipeiLngLat(lngLat[0], lngLat[1])) {
                continue;
            }
            lots.add(new ParkingLot(
                    id,
                    name,
                    text(item, "area"),
                    text(item, "address"),
                    lngLat[0],
                    lngLat[1],
                    intValue(item, "totalcar"),
                    text(item, "payex"),
                    text(item, "serviceTime", "servicetime")
            ));
        }
        return lots;
    }

    Map<String, Availability> parseAvailability(String json) throws IOException {
        JsonNode parks = parkArray(json);
        Map<String, Availability> availability = new HashMap<>();
        if (!parks.isArray()) {
            return availability;
        }
        for (JsonNode item : parks) {
            String id = text(item, "id");
            if (id.isBlank()) {
                continue;
            }
            availability.put(id, new Availability(
                    intValue(item, "availablecar"),
                    text(item, "updatetime")
            ));
        }
        return availability;
    }

    private JsonNode parkArray(String json) throws IOException {
        JsonNode root = objectMapper.readTree(json == null ? "{}" : json);
        JsonNode data = root.path("data");
        JsonNode parks = data.path("park");
        return parks.isMissingNode() ? root.path("park") : parks;
    }

    private NearbyParkingLotView toNearbyView(ParkingLot lot, Availability availability, double lng, double lat) {
        int distance = (int) Math.round(haversineMeters(lat, lng, lot.lat(), lot.lng()));
        return new NearbyParkingLotView(
                lot.id(),
                lot.name(),
                lot.area(),
                lot.address(),
                lot.lng(),
                lot.lat(),
                distance,
                lot.totalCar(),
                availability == null ? null : availability.availableCar(),
                lot.payText(),
                lot.serviceTime(),
                availability == null ? "" : availability.updatedAt(),
                googleMapsDrivingUrl(lot.lat(), lot.lng())
        );
    }

    private double[] extractLngLat(JsonNode item) {
        double[] fromEntrance = extractEntranceLngLat(item.path("EntranceCoord"));
        if (fromEntrance != null) {
            return fromEntrance;
        }
        fromEntrance = extractEntranceLngLat(item.path("entrancecoord"));
        if (fromEntrance != null) {
            return fromEntrance;
        }
        double[] direct = normalizeLngLat(
                doubleValue(item, "lng", "longitude", "x", "Xcod"),
                doubleValue(item, "lat", "latitude", "y", "Ycod")
        );
        if (direct != null) {
            return direct;
        }
        return twd97ToLngLat(doubleValue(item, "tw97x"), doubleValue(item, "tw97y"));
    }

    private double[] extractEntranceLngLat(JsonNode entrance) {
        if (entrance == null || entrance.isMissingNode() || entrance.isNull()) {
            return null;
        }
        if (entrance.isArray()) {
            return firstEntranceLngLat(entrance);
        }
        if (entrance.isObject()) {
            JsonNode nested = entrance.path("EntrancecoordInfo");
            if (nested.isMissingNode()) {
                nested = entrance.path("EntranceCoordInfo");
            }
            if (nested.isMissingNode()) {
                nested = entrance.path("entrancecoordInfo");
            }
            if (nested.isArray()) {
                double[] lngLat = firstEntranceLngLat(nested);
                if (lngLat != null) {
                    return lngLat;
                }
            }
            double[] direct = normalizeLngLat(
                    doubleValue(entrance, "lng", "longitude", "x", "Xcod"),
                    doubleValue(entrance, "lat", "latitude", "y", "Ycod")
            );
            if (direct != null) {
                return direct;
            }
        }
        return null;
    }

    private double[] firstEntranceLngLat(JsonNode entrances) {
        for (JsonNode item : entrances) {
            double[] lngLat = normalizeLngLat(
                    doubleValue(item, "lng", "longitude", "x", "Xcod"),
                    doubleValue(item, "lat", "latitude", "y", "Ycod")
            );
            if (lngLat != null) {
                return lngLat;
            }
        }
        return null;
    }

    private double[] normalizeLngLat(Double first, Double second) {
        if (first == null || second == null) {
            return null;
        }
        if (Math.abs(first) > 90 && Math.abs(second) <= 90) {
            return new double[]{first, second};
        }
        if (Math.abs(second) > 90 && Math.abs(first) <= 90) {
            return new double[]{second, first};
        }
        return null;
    }

    private double[] twd97ToLngLat(Double x, Double y) {
        if (x == null || y == null || x < 100000 || x > 400000 || y < 2400000 || y > 2900000) {
            return null;
        }
        double a = 6378137.0;
        double b = 6356752.314245;
        double lon0 = Math.toRadians(121.0);
        double k0 = 0.9999;
        double dx = x - 250000.0;
        double e = Math.sqrt(1.0 - (b * b) / (a * a));
        double e1sq = e * e / (1.0 - e * e);
        double m = y / k0;
        double mu = m / (a * (1.0 - Math.pow(e, 2) / 4.0 - 3.0 * Math.pow(e, 4) / 64.0 - 5.0 * Math.pow(e, 6) / 256.0));
        double e1 = (1.0 - Math.sqrt(1.0 - e * e)) / (1.0 + Math.sqrt(1.0 - e * e));
        double fp = mu
                + (3.0 * e1 / 2.0 - 27.0 * Math.pow(e1, 3) / 32.0) * Math.sin(2.0 * mu)
                + (21.0 * Math.pow(e1, 2) / 16.0 - 55.0 * Math.pow(e1, 4) / 32.0) * Math.sin(4.0 * mu)
                + (151.0 * Math.pow(e1, 3) / 96.0) * Math.sin(6.0 * mu)
                + (1097.0 * Math.pow(e1, 4) / 512.0) * Math.sin(8.0 * mu);
        double sinFp = Math.sin(fp);
        double cosFp = Math.cos(fp);
        double tanFp = Math.tan(fp);
        double c1 = e1sq * cosFp * cosFp;
        double t1 = tanFp * tanFp;
        double r1 = a * (1.0 - e * e) / Math.pow(1.0 - e * e * sinFp * sinFp, 1.5);
        double n1 = a / Math.sqrt(1.0 - e * e * sinFp * sinFp);
        double d = dx / (n1 * k0);

        double lat = fp - (n1 * tanFp / r1) * (
                d * d / 2.0
                        - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1 * c1 - 9.0 * e1sq) * Math.pow(d, 4) / 24.0
                        + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1 * t1 - 252.0 * e1sq - 3.0 * c1 * c1) * Math.pow(d, 6) / 720.0
        );
        double lng = lon0 + (
                d
                        - (1.0 + 2.0 * t1 + c1) * Math.pow(d, 3) / 6.0
                        + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1 * c1 + 8.0 * e1sq + 24.0 * t1 * t1) * Math.pow(d, 5) / 120.0
        ) / cosFp;
        return new double[]{Math.toDegrees(lng), Math.toDegrees(lat)};
    }

    private static boolean isTaipeiLngLat(double lng, double lat) {
        return lng >= 121.0 && lng <= 122.2 && lat >= 24.7 && lat <= 25.4;
    }

    private static String googleMapsDrivingUrl(double lat, double lng) {
        return "https://www.google.com/maps/dir/?api=1&destination=" + lat + "," + lng + "&travelmode=driving";
    }

    private static double haversineMeters(double lat1, double lng1, double lat2, double lng2) {
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

    private static String text(JsonNode node, String... fields) {
        for (String field : fields) {
            JsonNode value = node.path(field);
            if (!value.isMissingNode() && !value.isNull()) {
                String text = value.asText("").trim();
                if (!text.isBlank()) {
                    return repairMojibake(text);
                }
            }
        }
        return "";
    }

    private static String repairMojibake(String text) {
        boolean hasMojibakeMarker = text.indexOf('\u00c3') >= 0
                || text.indexOf('\u00c2') >= 0
                || text.chars().anyMatch(ch -> ch >= 0x80 && ch <= 0x9F);
        if (!hasMojibakeMarker) {
            return text;
        }
        return new String(text.getBytes(StandardCharsets.ISO_8859_1), StandardCharsets.UTF_8);
    }

    private static Integer intValue(JsonNode node, String field) {
        String value = text(node, field);
        if (value.isBlank() || value.equalsIgnoreCase("null")) {
            return null;
        }
        try {
            return (int) Math.round(Double.parseDouble(value));
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private static Double doubleValue(JsonNode node, String... fields) {
        for (String field : fields) {
            String value = text(node, field);
            if (value.isBlank() || value.equalsIgnoreCase("null")) {
                continue;
            }
            try {
                return Double.parseDouble(value);
            } catch (NumberFormatException ignored) {
                // try next field
            }
        }
        return null;
    }

    record ParkingLot(
            String id,
            String name,
            String area,
            String address,
            double lng,
            double lat,
            Integer totalCar,
            String payText,
            String serviceTime
    ) {
    }

    record Availability(Integer availableCar, String updatedAt) {
    }

    public record NearbyParkingLotView(
            String id,
            String name,
            String area,
            String address,
            double lng,
            double lat,
            int distanceMeters,
            Integer totalCar,
            Integer availableCar,
            String payText,
            String serviceTime,
            String updatedAt,
            String navigationUrl
    ) {
    }
}
