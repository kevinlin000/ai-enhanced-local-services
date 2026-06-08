package com.bytebites.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestTemplate;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ParkingServiceTest {

    @Test
    void nearbyMergesOfficialLotDescriptionAndAvailability() {
        ParkingService service = new FixtureParkingService();

        List<ParkingService.NearbyParkingLotView> lots = service.nearby(121.56510, 25.03300, 700, 3);

        assertThat(lots).hasSize(2);
        assertThat(lots.get(0))
                .extracting("id", "name", "area", "availableCar", "totalCar")
                .containsExactly("P001", "市府轉運站停車場", "信義區", 12, 120);
        assertThat(lots.get(0).distanceMeters()).isLessThan(100);
        assertThat(lots.get(0).navigationUrl()).contains("travelmode=driving", "25.0331,121.5652");
        assertThat(lots.get(1))
                .extracting("id", "name", "availableCar")
                .containsExactly("P002", "信義行政中心停車場", 5);
    }

    @Test
    void nearbyReturnsEmptyForInvalidCoordinates() {
        ParkingService service = new FixtureParkingService();

        assertThat(service.nearby(0, 0, 700, 3)).isEmpty();
    }

    @Test
    void parseLotsRepairsOfficialMojibakeText() throws Exception {
        ParkingService service = new FixtureParkingService();

        var lots = service.parseLots("""
                {
                  "data": {
                    "park": [
                      {
                        "id": "P004",
                        "area": "%s",
                        "name": "%s",
                        "address": "%s",
                        "totalcar": "83",
                        "EntranceCoord": {
                          "EntrancecoordInfo": [{"Xcod": "25.0328", "Ycod": "121.5650"}]
                        }
                      }
                    ]
                  }
                }
                """.formatted(
                mojibake("信義區"),
                mojibake("詮營信義101停車場"),
                mojibake("信義路5段101大樓對面空地")
        ));

        assertThat(lots).hasSize(1);
        assertThat(lots.get(0).name()).isEqualTo("詮營信義101停車場");
        assertThat(lots.get(0).area()).isEqualTo("信義區");
        assertThat(lots.get(0).address()).isEqualTo("信義路5段101大樓對面空地");
    }

    private static String mojibake(String value) {
        return new String(value.getBytes(StandardCharsets.UTF_8), StandardCharsets.ISO_8859_1);
    }

    private static class FixtureParkingService extends ParkingService {
        FixtureParkingService() {
            super(new ObjectMapper(), new RestTemplate(), Clock.fixed(Instant.parse("2026-06-08T04:00:00Z"), ZoneOffset.UTC));
        }

        @Override
        protected String fetchDescJson() {
            return """
                    {
                      "data": {
                        "park": [
                          {
                            "id": "P001",
                            "area": "信義區",
                            "name": "市府轉運站停車場",
                            "address": "台北市信義區忠孝東路五段6號",
                            "totalcar": "120",
                            "payex": "小型車每小時 60 元",
                            "servicetime": "00:00-24:00",
                            "EntranceCoord": [{"Xcod": "121.5652", "Ycod": "25.0331"}]
                          },
                          {
                            "id": "P002",
                            "area": "信義區",
                            "name": "信義行政中心停車場",
                            "address": "台北市信義區信義路五段15號",
                            "totalcar": "80",
                            "payex": "小型車每小時 50 元",
                            "serviceTime": "07:00-22:00",
                            "EntranceCoord": {
                              "EntrancecoordInfo": [{"Xcod": "25.0315", "Ycod": "121.5630", "Address": "入口"}]
                            }
                          },
                          {
                            "id": "P003",
                            "area": "北投區",
                            "name": "太遠停車場",
                            "address": "台北市北投區",
                            "totalcar": "50",
                            "EntranceCoord": [{"Xcod": "121.5000", "Ycod": "25.1300"}]
                          }
                        ]
                      }
                    }
                    """;
        }

        @Override
        protected String fetchAvailableJson() {
            return """
                    {
                      "data": {
                        "park": [
                          {"id": "P001", "availablecar": "12", "updatetime": "2026-06-08 12:00:00"},
                          {"id": "P002", "availablecar": "5", "updatetime": "2026-06-08 12:00:00"},
                          {"id": "P003", "availablecar": "30", "updatetime": "2026-06-08 12:00:00"}
                        ]
                      }
                    }
                    """;
        }
    }
}
