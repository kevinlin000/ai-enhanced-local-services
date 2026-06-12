package com.bytebites.service;

import com.bytebites.entity.Shop;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.service.jpa.UserJpaService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
@Slf4j
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
        userJpaService.findLineNotificationUserId(booking.getUserId()).ifPresentOrElse(
                lineUserId -> lineNotificationClient.pushBookingUpdated(lineUserId, payload, phase),
                () -> log.info(
                        "[LINE booking push] skipped bookingCode={} userId={} reason=no_linked_line_user",
                        booking.getBookingCode(),
                        booking.getUserId()
                )
        );
    }

    public void pushParkingReminder(BookingJpa booking, List<ParkingService.NearbyParkingLotView> parkingLots) {
        if (booking == null || booking.getUserId() == null) {
            return;
        }
        Shop shop = booking.getShopId() == null ? null : shopService.getById(booking.getShopId());
        String shopName = shop != null ? shop.getName() : null;
        Map<String, Object> payload = bookingPayload(booking, shopName);
        payload.put("parkingLots", parkingPayload(parkingLots));
        payload.put("parkingDataSource", "台北市停車場即時剩餘車位資料");
        payload.put("parkingDataNote", "車位會快速變動，請以到場狀況為準。");
        userJpaService.findLineNotificationUserId(booking.getUserId()).ifPresentOrElse(
                lineUserId -> lineNotificationClient.pushParkingReminder(lineUserId, payload),
                () -> log.info(
                        "[LINE parking push] skipped bookingCode={} userId={} reason=no_linked_line_user",
                        booking.getBookingCode(),
                        booking.getUserId()
                )
        );
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
        out.put("drivingToBooking", Boolean.TRUE.equals(booking.getDrivingToBooking()));
        out.put("parkingReminderEnabled", Boolean.TRUE.equals(booking.getParkingReminderEnabled()));
        out.put("parkingReminderSentAt", booking.getParkingReminderSentAt() != null ? booking.getParkingReminderSentAt().toString() : null);
        out.put("createdAt", booking.getCreatedAt() != null ? booking.getCreatedAt().toString() : null);
        out.put("updatedAt", booking.getUpdatedAt() != null ? booking.getUpdatedAt().toString() : null);
        out.put("idempotentReplay", false);
        return out;
    }

    private List<Map<String, Object>> parkingPayload(List<ParkingService.NearbyParkingLotView> parkingLots) {
        if (parkingLots == null || parkingLots.isEmpty()) {
            return List.of();
        }
        return parkingLots.stream().limit(3).map(lot -> {
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("id", lot.id());
            out.put("name", lot.name());
            out.put("area", lot.area());
            out.put("address", lot.address());
            out.put("distanceMeters", lot.distanceMeters());
            out.put("totalCar", lot.totalCar());
            out.put("availableCar", lot.availableCar());
            out.put("updatedAt", lot.updatedAt());
            out.put("navigationUrl", lot.navigationUrl());
            return out;
        }).toList();
    }
}
