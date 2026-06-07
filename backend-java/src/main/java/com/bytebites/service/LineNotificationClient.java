package com.bytebites.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.LinkedHashMap;
import java.util.Map;

@Slf4j
@Service
public class LineNotificationClient {
    private final RestTemplate restTemplate = new RestTemplate();
    private final String aiServiceUrl;
    private final String internalSecret;

    public LineNotificationClient(
            @Value("${bytebites.ai-service-url:http://localhost:8000}") String aiServiceUrl,
            @Value("${bytebites.line-internal-secret:}") String internalSecret
    ) {
        this.aiServiceUrl = aiServiceUrl;
        this.internalSecret = internalSecret;
    }

    public void pushAvailabilityReleased(Map<String, Object> watch, Long notificationId) {
        String lineUserId = String.valueOf(watch.getOrDefault("line_user_id", "")).trim();
        if (lineUserId.isBlank() || "null".equals(lineUserId)) return;

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("lineUserId", lineUserId);
        payload.put("notificationId", notificationId);
        payload.put("watchId", watch.get("id"));
        payload.put("shopId", watch.get("shop_id"));
        payload.put("shopName", watch.get("shop_name"));
        payload.put("date", String.valueOf(watch.get("booking_date")));
        payload.put("time", String.valueOf(watch.get("booking_time")));
        payload.put("tableType", watch.get("table_type"));
        payload.put("people", watch.get("people"));
        if (!internalSecret.isBlank()) {
            payload.put("secret", internalSecret);
        }

        try {
            Map<?, ?> response = restTemplate.postForObject(
                    aiServiceUrl.replaceAll("/+$", "") + "/internal/line/availability-released",
                    payload,
                    Map.class
            );
            if (response != null && Boolean.FALSE.equals(response.get("ok"))) {
                log.warn("[LINE availability push] not ok watchId={} lineUserId={} response={}",
                        watch.get("id"), lineUserId, response);
            }
        } catch (RestClientException ex) {
            log.warn("[LINE availability push] failed watchId={} lineUserId={}", watch.get("id"), lineUserId, ex);
        }
    }

    public void pushBookingUpdated(String lineUserId, Map<String, Object> booking, String phase) {
        String userId = lineUserId == null ? "" : lineUserId.trim();
        if (userId.isBlank() || "null".equals(userId) || booking == null || booking.isEmpty()) return;

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("lineUserId", userId);
        payload.put("phase", phase);
        payload.put("booking", booking);
        if (!internalSecret.isBlank()) {
            payload.put("secret", internalSecret);
        }

        try {
            Map<?, ?> response = restTemplate.postForObject(
                    aiServiceUrl.replaceAll("/+$", "") + "/internal/line/booking-updated",
                    payload,
                    Map.class
            );
            if (response != null && Boolean.FALSE.equals(response.get("ok"))) {
                log.warn("[LINE booking push] not ok bookingCode={} phase={} lineUserId={} response={}",
                        booking.get("bookingCode"), phase, userId, response);
            }
        } catch (RestClientException ex) {
            log.warn("[LINE booking push] failed bookingCode={} phase={} lineUserId={}",
                    booking.get("bookingCode"), phase, userId, ex);
        }
    }
}
