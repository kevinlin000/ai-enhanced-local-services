package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.service.BookingDepositAdjustmentService;
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
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.test.util.ReflectionTestUtils;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HexFormat;
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
    @Mock
    private BookingDepositAdjustmentService bookingDepositAdjustmentService;

    private PaymentController controller;

    @BeforeEach
    void setUp() {
        controller = new PaymentController();
        ReflectionTestUtils.setField(controller, "tapPay", tapPayService);
        ReflectionTestUtils.setField(controller, "bookingRepo", bookingRepo);
        ReflectionTestUtils.setField(controller, "bookingHoldService", bookingHoldService);
        ReflectionTestUtils.setField(controller, "bookingLineNotificationService", bookingLineNotificationService);
        ReflectionTestUtils.setField(controller, "bookingDepositAdjustmentService", bookingDepositAdjustmentService);
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

    @Test
    void customerTopUpPayByPrimeRecordsAdjustmentSettlementWithoutChangingBooking() {
        UserHolder.saveUser(webUser());
        Map<String, Object> payable = depositAdjustmentPayload("PENDING");
        Map<String, Object> completed = depositAdjustmentPayload("COMPLETED");
        completed.put("settlementTransId", "TPY-TOPUP-001");
        when(bookingDepositAdjustmentService.payableTopUpForCustomer(USER_ID, 77L))
                .thenReturn(payable);
        when(tapPayService.payByPrime("topup-prime", 600L, 45678L))
                .thenReturn(Map.of("status", 0, "rec_trade_id", "TPY-TOPUP-001", "msg", "Success"));
        when(bookingDepositAdjustmentService.recordCustomerTopUpSettlement(
                USER_ID,
                77L,
                "TPY-TOPUP-001",
                "Customer TapPay top-up completed"
        )).thenReturn(completed);

        Result result = controller.payTopUpByPrime(
                77L,
                Map.of(
                        "prime", "topup-prime",
                        "orderId", 45678L
                )
        );

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("adjustmentId", 77L)
                .containsEntry("bookingCode", "BK-PAY-001")
                .containsEntry("amount", 600L)
                .containsEntry("rec_trade_id", "TPY-TOPUP-001")
                .containsEntry("status", "PAID");
    }

    @Test
    void refundReconcileCallbackCompletesRefundAdjustment() {
        Map<String, Object> completed = depositAdjustmentPayload("COMPLETED");
        completed.put("adjustmentType", "REFUND");
        completed.put("deltaAmount", -600);
        completed.put("settlementTransId", "RF-TAPPAY-001");
        when(bookingDepositAdjustmentService.reconcileRefund(
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "TapPay refund completed",
                "evt-refund-001"
        )).thenReturn(completed);

        Result result = controller.reconcileRefundAdjustment(
                77L,
                Map.of(
                        "bookingCode", "BK-PAY-001",
                        "amount", 600,
                        "status", "COMPLETED",
                        "settlementTransId", "RF-TAPPAY-001",
                        "settlementNote", "TapPay refund completed",
                        "eventKey", "evt-refund-001"
                ),
                null,
                null,
                null
        );

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("id", 77L)
                .containsEntry("adjustmentType", "REFUND")
                .containsEntry("settlementStatus", "COMPLETED")
                .containsEntry("settlementTransId", "RF-TAPPAY-001");
        verify(bookingDepositAdjustmentService).reconcileRefund(
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "TapPay refund completed",
                "evt-refund-001"
        );
    }

    @Test
    void refundReconcileCallbackAcceptsValidHmacSignatureWhenSecretConfigured() {
        ReflectionTestUtils.setField(controller, "refundWebhookSecret", "refund-secret");
        Map<String, Object> completed = depositAdjustmentPayload("COMPLETED");
        completed.put("adjustmentType", "REFUND");
        completed.put("deltaAmount", -600);
        completed.put("settlementTransId", "RF-TAPPAY-001");
        when(bookingDepositAdjustmentService.reconcileRefund(
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "TapPay refund completed",
                "evt-refund-001"
        )).thenReturn(completed);
        String timestamp = String.valueOf(Instant.now().getEpochSecond());
        String signature = "sha256=" + refundSignature(
                "refund-secret",
                timestamp,
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "evt-refund-001"
        );

        Result result = controller.reconcileRefundAdjustment(
                77L,
                refundBody(),
                signature,
                timestamp,
                null
        );

        assertThat(result.getSuccess()).isTrue();
        verify(bookingDepositAdjustmentService).reconcileRefund(
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "TapPay refund completed",
                "evt-refund-001"
        );
    }

    @Test
    void refundReconcileCallbackAcceptsPreviousHmacSecretDuringRotation() {
        ReflectionTestUtils.setField(controller, "refundWebhookSecret", "new-refund-secret");
        ReflectionTestUtils.setField(controller, "refundWebhookPreviousSecret", "old-refund-secret");
        Map<String, Object> completed = depositAdjustmentPayload("COMPLETED");
        completed.put("adjustmentType", "REFUND");
        completed.put("deltaAmount", -600);
        completed.put("settlementTransId", "RF-TAPPAY-001");
        when(bookingDepositAdjustmentService.reconcileRefund(
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "TapPay refund completed",
                "evt-refund-001"
        )).thenReturn(completed);
        String timestamp = String.valueOf(Instant.now().getEpochSecond());
        String signature = "sha256=" + refundSignature(
                "old-refund-secret",
                timestamp,
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "evt-refund-001"
        );

        Result result = controller.reconcileRefundAdjustment(
                77L,
                refundBody(),
                signature,
                timestamp,
                null
        );

        assertThat(result.getSuccess()).isTrue();
        verify(bookingDepositAdjustmentService).reconcileRefund(
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "TapPay refund completed",
                "evt-refund-001"
        );
    }

    @Test
    void refundReconcileCallbackRejectsInvalidHmacSignatureWhenSecretConfigured() {
        ReflectionTestUtils.setField(controller, "refundWebhookSecret", "refund-secret");

        Result result = controller.reconcileRefundAdjustment(
                77L,
                refundBody(),
                "sha256=" + "0".repeat(64),
                String.valueOf(Instant.now().getEpochSecond()),
                null
        );

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).contains("簽章驗證失敗");
    }

    @Test
    void refundReconcileCallbackRejectsExpiredHmacTimestampWhenSecretConfigured() {
        ReflectionTestUtils.setField(controller, "refundWebhookSecret", "refund-secret");
        String timestamp = String.valueOf(Instant.now().minusSeconds(600).getEpochSecond());
        String signature = "sha256=" + refundSignature(
                "refund-secret",
                timestamp,
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "evt-refund-001"
        );

        Result result = controller.reconcileRefundAdjustment(
                77L,
                refundBody(),
                signature,
                timestamp,
                null
        );

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).contains("簽章驗證失敗");
    }

    @Test
    void refundReconcileCallbackAcceptsDirectAllowedSourceWhenAllowlistConfigured() {
        ReflectionTestUtils.setField(controller, "refundWebhookAllowedSources", "203.0.113.10");
        Map<String, Object> completed = depositAdjustmentPayload("COMPLETED");
        completed.put("adjustmentType", "REFUND");
        completed.put("deltaAmount", -600);
        completed.put("settlementTransId", "RF-TAPPAY-001");
        when(bookingDepositAdjustmentService.reconcileRefund(
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "TapPay refund completed",
                "evt-refund-001"
        )).thenReturn(completed);

        Result result = controller.reconcileRefundAdjustment(
                77L,
                refundBody(),
                null,
                null,
                requestFrom("203.0.113.10")
        );

        assertThat(result.getSuccess()).isTrue();
    }

    @Test
    void refundReconcileCallbackAcceptsForwardedSourceOnlyFromTrustedProxy() {
        ReflectionTestUtils.setField(controller, "refundWebhookAllowedSources", "198.51.100.12");
        ReflectionTestUtils.setField(controller, "refundWebhookTrustedProxies", "10.0.0.0/24");
        ReflectionTestUtils.setField(controller, "refundWebhookSourceHeader", "X-Forwarded-For");
        Map<String, Object> completed = depositAdjustmentPayload("COMPLETED");
        completed.put("adjustmentType", "REFUND");
        completed.put("deltaAmount", -600);
        completed.put("settlementTransId", "RF-TAPPAY-001");
        when(bookingDepositAdjustmentService.reconcileRefund(
                77L,
                "BK-PAY-001",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "TapPay refund completed",
                "evt-refund-001"
        )).thenReturn(completed);
        MockHttpServletRequest request = requestFrom("10.0.0.15");
        request.addHeader("X-Forwarded-For", "198.51.100.12, 10.0.0.15");

        Result result = controller.reconcileRefundAdjustment(
                77L,
                refundBody(),
                null,
                null,
                request
        );

        assertThat(result.getSuccess()).isTrue();
    }

    @Test
    void refundReconcileCallbackRejectsSpoofedForwardedSourceFromUntrustedProxy() {
        ReflectionTestUtils.setField(controller, "refundWebhookAllowedSources", "198.51.100.12");
        ReflectionTestUtils.setField(controller, "refundWebhookTrustedProxies", "10.0.0.0/24");
        MockHttpServletRequest request = requestFrom("10.1.0.15");
        request.addHeader("X-Forwarded-For", "198.51.100.12");

        Result result = controller.reconcileRefundAdjustment(
                77L,
                refundBody(),
                null,
                null,
                request
        );

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).contains("來源驗證失敗");
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

    private Map<String, Object> depositAdjustmentPayload(String settlementStatus) {
        return new java.util.LinkedHashMap<>(Map.ofEntries(
                Map.entry("id", 77L),
                Map.entry("bookingCode", "BK-PAY-001"),
                Map.entry("userId", USER_ID),
                Map.entry("shopId", SHOP_ID),
                Map.entry("shopName", "橘色涮涮屋 信義館"),
                Map.entry("bookingDate", LocalDate.now().plusDays(3).toString()),
                Map.entry("bookingTime", "19:00"),
                Map.entry("bookingPeople", 2),
                Map.entry("bookingTableType", "normal"),
                Map.entry("bookingStatus", "PAID"),
                Map.entry("status", "OPEN"),
                Map.entry("adjustmentType", "TOP_UP"),
                Map.entry("source", "CUSTOMER_RESCHEDULE"),
                Map.entry("currentDepositTotal", 600),
                Map.entry("proposedDepositTotal", 1200),
                Map.entry("deltaAmount", 600),
                Map.entry("proposedDate", LocalDate.now().plusDays(3).toString()),
                Map.entry("proposedTime", "19:30"),
                Map.entry("proposedTableType", "normal"),
                Map.entry("proposedPeople", 4),
                Map.entry("message", "改單會增加訂金 NT$ 600"),
                Map.entry("appliedBookingUpdate", false),
                Map.entry("settlementStatus", settlementStatus),
                Map.entry("settlementProvider", "TAPPAY"),
                Map.entry("settlementAmount", 600)
        ));
    }

    private Map<String, Object> refundBody() {
        return Map.of(
                "bookingCode", "BK-PAY-001",
                "amount", 600,
                "status", "COMPLETED",
                "settlementTransId", "RF-TAPPAY-001",
                "settlementNote", "TapPay refund completed",
                "eventKey", "evt-refund-001"
        );
    }

    private MockHttpServletRequest requestFrom(String remoteAddress) {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setRemoteAddr(remoteAddress);
        return request;
    }

    private String refundSignature(
            String secret,
            String timestamp,
            Long adjustmentId,
            String bookingCode,
            int amount,
            String status,
            String settlementTransId,
            String eventKey
    ) {
        try {
            String payload = String.join("\n",
                    timestamp,
                    "refund-reconcile",
                    String.valueOf(adjustmentId),
                    bookingCode,
                    String.valueOf(amount),
                    status.toUpperCase(),
                    settlementTransId,
                    eventKey
            );
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return HexFormat.of().formatHex(mac.doFinal(payload.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception ex) {
            throw new AssertionError(ex);
        }
    }
}
