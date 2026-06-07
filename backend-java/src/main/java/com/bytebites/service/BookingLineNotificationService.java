package com.bytebites.service;

import com.bytebites.entity.Shop;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.service.jpa.UserJpaService;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class BookingLineNotificationService {

    private final IShopService shopService;
    private final LineNotificationClient lineNotificationClient;
    private final UserJpaService userJpaService;

    public BookingLineNotificationService(
            IShopService shopService,
            LineNotificationClient lineNotificationClient,
            UserJpaService userJpaService
    ) {
        this.shopService = shopService;
        this.lineNotificationClient = lineNotificationClient;
        this.userJpaService = userJpaService;
    }

    public void pushBookingUpdated(BookingJpa booking, String phase) {
        if (booking == null || booking.getUserId() == null) {
            return;
        }
        Shop shop = booking.getShopId() == null ? null : shopService.getById(booking.getShopId());
        String shopName = shop != null ? shop.getName() : null;
        Map<String, Object> payload = bookingPayload(booking, shopName);
        userJpaService.findLineNotificationUserId(booking.getUserId())
                .ifPresent(lineUserId -> lineNotificationClient.pushBookingUpdated(lineUserId, payload, phase));
    }

    private Map<String, Object> bookingPayload(BookingJpa booking, String shopName) {
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
        out.put(
                "status",
                booking.getStatus() == BookingHoldService.STATUS_PENDING_PAYMENT
                        ? "PENDING_PAYMENT"
                        : booking.getStatus() == BookingHoldService.STATUS_PAID
                        ? "PAID"
                        : booking.getStatus() == BookingHoldService.STATUS_CANCELED
                        ? "CANCELED"
                        : booking.getStatus() == BookingHoldService.STATUS_EXPIRED ? "EXPIRED" : "CONFIRMED"
        );
        out.put("paymentTransId", booking.getPaymentTransId());
        out.put("holdExpiresAt", booking.getHoldExpiresAt() != null ? booking.getHoldExpiresAt().toString() : null);
        out.put("holdMinutes", BookingHoldService.HOLD_MINUTES);
        out.put("createdAt", booking.getCreatedAt() != null ? booking.getCreatedAt().toString() : null);
        out.put("updatedAt", booking.getUpdatedAt() != null ? booking.getUpdatedAt().toString() : null);
        out.put("idempotentReplay", false);
        return out;
    }
}
