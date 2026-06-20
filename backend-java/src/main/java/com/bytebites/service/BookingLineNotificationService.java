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
    private final BookingPayloadMapper bookingPayloadMapper;

    public BookingLineNotificationService(
            IShopService shopService,
            LineNotificationClient lineNotificationClient,
            UserJpaService userJpaService,
            BookingPayloadMapper bookingPayloadMapper
    ) {
        this.shopService = shopService;
        this.lineNotificationClient = lineNotificationClient;
        this.userJpaService = userJpaService;
        this.bookingPayloadMapper = bookingPayloadMapper;
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

    public void pushBookingIncident(BookingJpa booking, Map<String, Object> incident) {
        if (booking == null || booking.getUserId() == null || incident == null || incident.isEmpty()) {
            return;
        }
        Shop shop = booking.getShopId() == null ? null : shopService.getById(booking.getShopId());
        String shopName = shop != null ? shop.getName() : null;
        Map<String, Object> payload = new LinkedHashMap<>(incident);
        payload.put("booking", bookingPayload(booking, shopName));
        payload.putIfAbsent("date", booking.getBookingDate() != null ? booking.getBookingDate().toString() : "");
        payload.putIfAbsent("time", booking.getBookingTime());
        payload.putIfAbsent("people", booking.getPeople());
        payload.putIfAbsent("tableType", booking.getTableType());
        userJpaService.findLineNotificationUserId(booking.getUserId()).ifPresentOrElse(
                lineUserId -> lineNotificationClient.pushBookingIncident(lineUserId, payload),
                () -> log.info(
                        "[LINE incident push] skipped bookingCode={} userId={} reason=no_linked_line_user",
                        booking.getBookingCode(),
                        booking.getUserId()
                )
        );
    }

    public void pushBookingIncidentProposal(Map<String, Object> incident) {
        if (incident == null || incident.isEmpty()) {
            return;
        }
        Long userId = toLong(incident.get("userId"));
        if (userId == null) {
            return;
        }
        userJpaService.findLineNotificationUserId(userId).ifPresentOrElse(
                lineUserId -> lineNotificationClient.pushBookingIncidentProposal(lineUserId, new LinkedHashMap<>(incident)),
                () -> log.info(
                        "[LINE incident proposal push] skipped bookingCode={} userId={} reason=no_linked_line_user",
                        incident.get("bookingCode"),
                        userId
                )
        );
    }

    private Map<String, Object> bookingPayload(BookingJpa booking, String shopName) {
        return bookingPayloadMapper.toPayload(booking, shopName, false);
    }

    private Long toLong(Object value) {
        if (value == null) return null;
        if (value instanceof Number number) return number.longValue();
        String raw = value.toString().trim();
        if (raw.isBlank()) return null;
        try {
            return Long.parseLong(raw);
        } catch (NumberFormatException ex) {
            return null;
        }
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
