package com.bytebites.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class LineNotificationClientTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void bookingUpdatedPostsPythonInternalWebhookPayload() throws Exception {
        RestTemplate restTemplate = new RestTemplate();
        MockRestServiceServer server = MockRestServiceServer.bindTo(restTemplate).build();
        LineNotificationClient client = new LineNotificationClient(
                restTemplate,
                "http://localhost:8000/",
                "sync-secret"
        );
        Map<String, Object> booking = new LinkedHashMap<>();
        booking.put("bookingCode", "BK-LINE-SYNC-001");
        booking.put("shopId", 10009L);
        booking.put("shopName", "橘色涮涮屋 信義館");
        booking.put("date", "2026-06-10");
        booking.put("time", "19:00");
        booking.put("people", 2);
        booking.put("status", "PAID");
        booking.put("paymentTransId", "TPY-SYNC-001");

        Map<String, Object> expectedPayload = new LinkedHashMap<>();
        expectedPayload.put("lineUserId", "Udemo-sync");
        expectedPayload.put("phase", "paid");
        expectedPayload.put("booking", booking);
        expectedPayload.put("secret", "sync-secret");

        server.expect(requestTo("http://localhost:8000/internal/line/booking-updated"))
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(content().json(objectMapper.writeValueAsString(expectedPayload)))
                .andRespond(withSuccess("{\"ok\":true}", MediaType.APPLICATION_JSON));

        client.pushBookingUpdated(" Udemo-sync ", booking, "paid");

        server.verify();
    }

    @Test
    void availabilityReleasedPostsPythonInternalWebhookPayload() throws Exception {
        RestTemplate restTemplate = new RestTemplate();
        MockRestServiceServer server = MockRestServiceServer.bindTo(restTemplate).build();
        LineNotificationClient client = new LineNotificationClient(
                restTemplate,
                "http://localhost:8000",
                "sync-secret"
        );
        Map<String, Object> watch = new LinkedHashMap<>();
        watch.put("id", 701L);
        watch.put("line_user_id", "Udemo-sync");
        watch.put("shop_id", 10009L);
        watch.put("shop_name", "橘色涮涮屋 信義館");
        watch.put("booking_date", "2026-06-10");
        watch.put("booking_time", "19:00");
        watch.put("table_type", "normal");
        watch.put("people", 2);

        Map<String, Object> expectedPayload = new LinkedHashMap<>();
        expectedPayload.put("lineUserId", "Udemo-sync");
        expectedPayload.put("notificationId", 501L);
        expectedPayload.put("watchId", 701L);
        expectedPayload.put("shopId", 10009L);
        expectedPayload.put("shopName", "橘色涮涮屋 信義館");
        expectedPayload.put("date", "2026-06-10");
        expectedPayload.put("time", "19:00");
        expectedPayload.put("tableType", "normal");
        expectedPayload.put("people", 2);
        expectedPayload.put("secret", "sync-secret");

        server.expect(requestTo("http://localhost:8000/internal/line/availability-released"))
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(content().json(objectMapper.writeValueAsString(expectedPayload)))
                .andRespond(withSuccess("{\"ok\":true}", MediaType.APPLICATION_JSON));

        client.pushAvailabilityReleased(watch, 501L);

        server.verify();
    }
}
