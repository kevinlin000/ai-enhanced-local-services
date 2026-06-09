package com.bytebites.service;

import com.bytebites.entity.Shop;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.service.jpa.UserJpaService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class BookingLineNotificationServiceTest {
    private static final Long USER_ID = 1012L;
    private static final Long SHOP_ID = 10009L;
    private static final String LINE_USER_ID = "Udemo-sync";

    @Mock
    private IShopService shopService;
    @Mock
    private LineNotificationClient lineNotificationClient;
    @Mock
    private UserJpaService userJpaService;

    private BookingLineNotificationService service;

    @BeforeEach
    void setUp() {
        service = new BookingLineNotificationService(shopService, lineNotificationClient, userJpaService);
    }

    @Test
    void paidBookingPushPayloadContainsSharedWebLineStateContract() {
        BookingJpa booking = booking(BookingHoldService.STATUS_PAID, "TPY-SYNC-001");
        when(shopService.getById(SHOP_ID)).thenReturn(shop());
        when(userJpaService.findLineNotificationUserId(USER_ID)).thenReturn(Optional.of(LINE_USER_ID));

        service.pushBookingUpdated(booking, "paid");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> bookingCaptor = ArgumentCaptor.forClass(Map.class);
        verify(lineNotificationClient).pushBookingUpdated(
                org.mockito.ArgumentMatchers.eq(LINE_USER_ID),
                bookingCaptor.capture(),
                org.mockito.ArgumentMatchers.eq("paid")
        );
        assertThat(bookingCaptor.getValue())
                .containsEntry("bookingCode", "BK-LINE-001")
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("shopName", "橘色涮涮屋 信義館")
                .containsEntry("status", "PAID")
                .containsEntry("paymentTransId", "TPY-SYNC-001")
                .containsEntry("needsDeposit", true)
                .containsEntry("depositTotal", 600);
    }

    @Test
    void canceledBookingPushPayloadUsesCanceledStatus() {
        BookingJpa booking = booking(BookingHoldService.STATUS_CANCELED, "TPY-SYNC-001");
        when(shopService.getById(SHOP_ID)).thenReturn(shop());
        when(userJpaService.findLineNotificationUserId(USER_ID)).thenReturn(Optional.of(LINE_USER_ID));

        service.pushBookingUpdated(booking, "canceled");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> bookingCaptor = ArgumentCaptor.forClass(Map.class);
        verify(lineNotificationClient).pushBookingUpdated(
                org.mockito.ArgumentMatchers.eq(LINE_USER_ID),
                bookingCaptor.capture(),
                org.mockito.ArgumentMatchers.eq("canceled")
        );
        assertThat(bookingCaptor.getValue())
                .containsEntry("bookingCode", "BK-LINE-001")
                .containsEntry("status", "CANCELED")
                .containsEntry("paymentTransId", "TPY-SYNC-001");
    }

    @Test
    void bookingWithoutLinkedLineUserDoesNotPush() {
        BookingJpa booking = booking(BookingHoldService.STATUS_PAID, "TPY-SYNC-001");
        when(shopService.getById(SHOP_ID)).thenReturn(shop());
        when(userJpaService.findLineNotificationUserId(USER_ID)).thenReturn(Optional.empty());

        service.pushBookingUpdated(booking, "paid");

        verify(lineNotificationClient, never()).pushBookingUpdated(
                org.mockito.ArgumentMatchers.anyString(),
                org.mockito.ArgumentMatchers.anyMap(),
                org.mockito.ArgumentMatchers.anyString()
        );
    }

    @Test
    void parkingReminderPayloadContainsBookingAndNearbyLots() {
        BookingJpa booking = booking(BookingHoldService.STATUS_CONFIRMED, null);
        booking.setDrivingToBooking(true);
        booking.setParkingReminderEnabled(true);
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
        when(shopService.getById(SHOP_ID)).thenReturn(shop());
        when(userJpaService.findLineNotificationUserId(USER_ID)).thenReturn(Optional.of(LINE_USER_ID));

        service.pushParkingReminder(booking, lots);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> reminderCaptor = ArgumentCaptor.forClass(Map.class);
        verify(lineNotificationClient).pushParkingReminder(
                org.mockito.ArgumentMatchers.eq(LINE_USER_ID),
                reminderCaptor.capture()
        );
        assertThat(reminderCaptor.getValue())
                .containsEntry("bookingCode", "BK-LINE-001")
                .containsEntry("shopName", "橘色涮涮屋 信義館")
                .containsEntry("parkingDataSource", "台北市停車場即時剩餘車位資料");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> parkingLots = (List<Map<String, Object>>) reminderCaptor.getValue().get("parkingLots");
        assertThat(parkingLots).hasSize(1);
        assertThat(parkingLots.get(0))
                .containsEntry("name", "市府轉運站停車場")
                .containsEntry("availableCar", 18)
                .containsEntry("distanceMeters", 180);
    }

    private BookingJpa booking(int status, String paymentTransId) {
        BookingJpa booking = new BookingJpa();
        booking.setId(1L);
        booking.setUserId(USER_ID);
        booking.setBookingCode("BK-LINE-001");
        booking.setShopId(SHOP_ID);
        booking.setPeople(2);
        booking.setBookingDate(LocalDate.now().plusDays(3));
        booking.setBookingTime("19:00");
        booking.setTableType("normal");
        booking.setStatus(status);
        booking.setNeedsDeposit(true);
        booking.setDepositPerPerson(300);
        booking.setDepositTotal(600);
        booking.setPaymentTransId(paymentTransId);
        booking.setCreatedAt(LocalDateTime.now().minusMinutes(5));
        booking.setUpdatedAt(LocalDateTime.now().minusMinutes(4));
        return booking;
    }

    private Shop shop() {
        Shop shop = new Shop();
        shop.setId(SHOP_ID);
        shop.setName("橘色涮涮屋 信義館");
        return shop;
    }
}
