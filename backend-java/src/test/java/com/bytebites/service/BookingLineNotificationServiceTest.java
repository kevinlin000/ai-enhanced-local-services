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
