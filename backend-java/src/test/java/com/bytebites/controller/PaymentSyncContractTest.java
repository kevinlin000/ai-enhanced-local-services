package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.service.BookingHoldService;
import com.bytebites.service.BookingLineNotificationService;
import com.bytebites.service.TapPayService;
import com.bytebites.utils.UserHolder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PaymentSyncContractTest {
    private static final Long USER_ID = 1012L;
    private static final Long SHOP_ID = 10009L;

    @Mock
    private TapPayService tapPayService;
    @Mock
    private BookingJpaRepository bookingRepo;
    @Mock
    private BookingHoldService bookingHoldService;
    @Mock
    private BookingLineNotificationService bookingLineNotificationService;

    private PaymentController controller;

    @BeforeEach
    void setUp() {
        controller = new PaymentController();
        ReflectionTestUtils.setField(controller, "tapPay", tapPayService);
        ReflectionTestUtils.setField(controller, "bookingRepo", bookingRepo);
        ReflectionTestUtils.setField(controller, "bookingHoldService", bookingHoldService);
        ReflectionTestUtils.setField(controller, "bookingLineNotificationService", bookingLineNotificationService);
    }

    @AfterEach
    void tearDown() {
        UserHolder.removeUser();
    }

    @Test
    void webTapPaySuccessMarksBookingPaidAndPushesLineUpdate() {
        UserHolder.saveUser(webUser());
        BookingJpa booking = pendingBooking();
        when(bookingRepo.findByBookingCode("BK-PAY-001")).thenReturn(Optional.of(booking));
        when(bookingHoldService.expireIfDue(booking)).thenReturn(false);
        when(tapPayService.payByPrime("test-prime", 600L, 12345L))
                .thenReturn(Map.of("status", 0, "rec_trade_id", "TPY-SYNC-001", "msg", "Success"));

        Result result = controller.payByPrime(Map.of(
                "prime", "test-prime",
                "bookingCode", "BK-PAY-001",
                "orderId", 12345L
        ));

        assertThat(result.getSuccess()).isTrue();
        assertThat(booking.getStatus()).isEqualTo(BookingHoldService.STATUS_PAID);
        assertThat(booking.getPaymentTransId()).isEqualTo("TPY-SYNC-001");
        verify(bookingRepo).save(booking);
        verify(bookingLineNotificationService).pushBookingUpdated(booking, "paid");
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("bookingCode", "BK-PAY-001")
                .containsEntry("status", "PAID")
                .containsEntry("rec_trade_id", "TPY-SYNC-001")
                .containsEntry("amount", 600L);
    }

    private UserDTO webUser() {
        UserDTO user = new UserDTO();
        user.setId(USER_ID);
        user.setLineUserId("Udemo-sync");
        user.setNickName("Demo User");
        return user;
    }

    private BookingJpa pendingBooking() {
        BookingJpa booking = new BookingJpa();
        booking.setId(1L);
        booking.setUserId(USER_ID);
        booking.setBookingCode("BK-PAY-001");
        booking.setShopId(SHOP_ID);
        booking.setPeople(2);
        booking.setBookingDate(LocalDate.now().plusDays(3));
        booking.setBookingTime("19:00");
        booking.setTableType("normal");
        booking.setStatus(BookingHoldService.STATUS_PENDING_PAYMENT);
        booking.setNeedsDeposit(true);
        booking.setDepositPerPerson(300);
        booking.setDepositTotal(600);
        booking.setHoldExpiresAt(LocalDateTime.now().plusMinutes(8));
        booking.setCreatedAt(LocalDateTime.now().minusMinutes(5));
        booking.setUpdatedAt(LocalDateTime.now().minusMinutes(4));
        return booking;
    }
}
