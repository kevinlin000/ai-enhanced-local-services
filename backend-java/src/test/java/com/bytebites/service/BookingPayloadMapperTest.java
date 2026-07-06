package com.bytebites.service;

import com.bytebites.entity.jpa.BookingJpa;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class BookingPayloadMapperTest {

    @Test
    void holdExpiryIncludesOffsetForBrowserCountdowns() {
        LocalDateTime expiry = LocalDateTime.of(2026, 7, 6, 7, 33, 18);
        BookingJpa booking = new BookingJpa();
        booking.setBookingCode("BK-TIMEZONE");
        booking.setShopId(1L);
        booking.setBookingDate(LocalDate.of(2026, 7, 7));
        booking.setStatus(BookingHoldService.STATUS_PENDING_PAYMENT);
        booking.setHoldExpiresAt(expiry);

        Map<String, Object> payload = new BookingPayloadMapper().toPayload(booking, "測試店", false);
        OffsetDateTime serialized = OffsetDateTime.parse((String) payload.get("holdExpiresAt"));

        assertThat(serialized.toLocalDateTime()).isEqualTo(expiry);
    }
}
