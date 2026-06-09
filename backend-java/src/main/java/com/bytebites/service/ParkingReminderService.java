package com.bytebites.service;

import com.bytebites.entity.Shop;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

@Slf4j
@Service
public class ParkingReminderService {
    private static final ZoneId BUSINESS_ZONE = ZoneId.of("Asia/Taipei");
    private static final Duration LOOKAHEAD = Duration.ofHours(2);

    private final BookingJpaRepository bookingRepo;
    private final IShopService shopService;
    private final ParkingService parkingService;
    private final BookingLineNotificationService bookingLineNotificationService;

    public ParkingReminderService(
            BookingJpaRepository bookingRepo,
            IShopService shopService,
            ParkingService parkingService,
            BookingLineNotificationService bookingLineNotificationService
    ) {
        this.bookingRepo = bookingRepo;
        this.shopService = shopService;
        this.parkingService = parkingService;
        this.bookingLineNotificationService = bookingLineNotificationService;
    }

    @Scheduled(fixedDelay = 300_000, initialDelay = 60_000)
    public void sendDueParkingReminders() {
        LocalDateTime now = LocalDateTime.now(BUSINESS_ZONE);
        sendDueParkingReminders(now);
    }

    void sendDueParkingReminders(LocalDateTime now) {
        LocalDateTime cutoff = now.plus(LOOKAHEAD);
        List<BookingJpa> due = bookingRepo.findUpcomingParkingReminderCandidates(now, cutoff);
        for (BookingJpa booking : due) {
            sendParkingReminder(booking, now);
        }
    }

    private void sendParkingReminder(BookingJpa booking, LocalDateTime now) {
        if (booking == null || !Boolean.TRUE.equals(booking.getParkingReminderEnabled())) {
            return;
        }
        Shop shop = booking.getShopId() == null ? null : shopService.getById(booking.getShopId());
        List<ParkingService.NearbyParkingLotView> lots = List.of();
        if (shop != null && shop.getX() != null && shop.getY() != null) {
            lots = parkingService.nearby(shop.getX(), shop.getY(), 900, 3);
        }
        bookingLineNotificationService.pushParkingReminder(booking, lots);
        booking.setParkingReminderSentAt(now);
        bookingRepo.save(booking);
        log.info("[Parking reminder] bookingCode={} shop={} lots={}",
                booking.getBookingCode(), booking.getShopId(), lots.size());
    }
}
