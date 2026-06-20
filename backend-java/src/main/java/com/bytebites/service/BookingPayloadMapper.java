package com.bytebites.service;

import com.bytebites.entity.jpa.BookingJpa;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

@Component
public class BookingPayloadMapper {

    public Map<String, Object> toPayload(BookingJpa booking, String shopName, boolean idempotentReplay) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("bookingCode", booking.getBookingCode());
        out.put("userId", booking.getUserId());
        out.put("shopId", booking.getShopId());
        out.put("shopName", shopName != null ? shopName : "店家 " + booking.getShopId());
        out.put("people", booking.getPeople());
        out.put("date", booking.getBookingDate().toString());
        out.put("time", booking.getBookingTime());
        out.put("tableType", booking.getTableType());
        out.put("needsDeposit", booking.getNeedsDeposit());
        out.put("depositTotal", booking.getDepositTotal());
        out.put("status", statusLabel(booking.getStatus()));
        out.put("paymentTransId", booking.getPaymentTransId());
        out.put("holdExpiresAt", booking.getHoldExpiresAt() != null ? booking.getHoldExpiresAt().toString() : null);
        out.put("holdMinutes", BookingHoldService.HOLD_MINUTES);
        out.put("drivingToBooking", Boolean.TRUE.equals(booking.getDrivingToBooking()));
        out.put("parkingReminderEnabled", Boolean.TRUE.equals(booking.getParkingReminderEnabled()));
        out.put("parkingReminderSentAt", booking.getParkingReminderSentAt() != null ? booking.getParkingReminderSentAt().toString() : null);
        out.put("createdAt", booking.getCreatedAt() != null ? booking.getCreatedAt().toString() : null);
        out.put("updatedAt", booking.getUpdatedAt() != null ? booking.getUpdatedAt().toString() : null);
        out.put("idempotentReplay", idempotentReplay);
        return out;
    }

    public String statusLabel(Integer status) {
        if (status == null) {
            return "CONFIRMED";
        }
        return switch (status) {
            case BookingHoldService.STATUS_PENDING_PAYMENT -> "PENDING_PAYMENT";
            case BookingHoldService.STATUS_PAID -> "PAID";
            case BookingHoldService.STATUS_CANCELED -> "CANCELED";
            case BookingHoldService.STATUS_EXPIRED -> "EXPIRED";
            default -> "CONFIRMED";
        };
    }
}
