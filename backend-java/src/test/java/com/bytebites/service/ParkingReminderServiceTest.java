package com.bytebites.service;

import com.bytebites.entity.Shop;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ParkingReminderServiceTest {
    private static final Long USER_ID = 1012L;
    private static final Long SHOP_ID = 10009L;

    @Mock
    private BookingJpaRepository bookingRepo;
    @Mock
    private IShopService shopService;
    @Mock
    private ParkingService parkingService;
    @Mock
    private BookingLineNotificationService bookingLineNotificationService;

    private ParkingReminderService service;

    @BeforeEach
    void setUp() {
        service = new ParkingReminderService(
                bookingRepo,
                shopService,
                parkingService,
                bookingLineNotificationService
        );
    }

    @Test
    void sendsDueReminderWithFreshNearbyParkingSnapshotAndMarksSent() {
        LocalDateTime now = LocalDateTime.of(2026, 6, 10, 17, 0);
        BookingJpa booking = booking();
        Shop shop = shop();
        List<ParkingService.NearbyParkingLotView> lots = List.of(
                new ParkingService.NearbyParkingLotView(
                        "P001",
                        "市府轉運站停車場",
                        "信義",
                        "台北市信義區忠孝東路",
                        121.565,
                        25.033,
                        180,
                        120,
                        18,
                        "小時計費",
                        "24 小時",
                        "2026-06-10 17:00:00",
                        "https://www.google.com/maps/dir/?api=1&destination=25.033,121.565&travelmode=driving"
                )
        );

        when(bookingRepo.findUpcomingParkingReminderCandidates(now, now.plusHours(2))).thenReturn(List.of(booking));
        when(shopService.getById(SHOP_ID)).thenReturn(shop);
        when(parkingService.nearby(121.565, 25.033, 900, 3)).thenReturn(lots);

        service.sendDueParkingReminders(now);

        verify(bookingLineNotificationService).pushParkingReminder(booking, lots);
        assertThat(booking.getParkingReminderSentAt()).isEqualTo(now);
        verify(bookingRepo).save(booking);
    }

    private BookingJpa booking() {
        BookingJpa booking = new BookingJpa();
        booking.setId(1L);
        booking.setUserId(USER_ID);
        booking.setBookingCode("BK-PARK-001");
        booking.setShopId(SHOP_ID);
        booking.setPeople(2);
        booking.setBookingDate(LocalDate.of(2026, 6, 10));
        booking.setBookingTime("19:00");
        booking.setTableType("normal");
        booking.setStatus(BookingHoldService.STATUS_CONFIRMED);
        booking.setNeedsDeposit(false);
        booking.setDepositPerPerson(0);
        booking.setDepositTotal(0);
        booking.setDrivingToBooking(true);
        booking.setParkingReminderEnabled(true);
        return booking;
    }

    private Shop shop() {
        Shop shop = new Shop();
        shop.setId(SHOP_ID);
        shop.setName("橘色涮涮屋 信義館");
        shop.setX(121.565);
        shop.setY(25.033);
        return shop;
    }
}
