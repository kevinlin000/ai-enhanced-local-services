package com.bytebites.service;

import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class BookingDepositAdjustmentServiceTest {
    private static final Long SHOP_ID = 10009L;
    private static final Long USER_ID = 1012L;

    @Mock
    private JdbcTemplate jdbcTemplate;
    @Mock
    private BookingJpaRepository bookingRepo;
    @Mock
    private BookingRescheduleService bookingRescheduleService;

    private BookingDepositAdjustmentService service;

    @BeforeEach
    void setUp() {
        service = new BookingDepositAdjustmentService(jdbcTemplate, bookingRepo, bookingRescheduleService);
    }

    @Test
    void recordRequiredUpsertsOpenManualAdjustment() {
        BookingJpa booking = paidBooking();
        BookingRescheduleService.DepositAdjustment adjustment =
                BookingRescheduleService.DepositAdjustment.blocked(
                        600,
                        1200,
                        600,
                        "改單會增加訂金 NT$ 600，需由店家人工處理後再確認。"
                );

        service.recordRequired(
                booking,
                7L,
                LocalDate.of(2026, 6, 20),
                "19:30",
                "normal",
                4,
                adjustment,
                "INCIDENT_PROPOSAL"
        );

        verify(jdbcTemplate).update(
                contains("status = 'SUPERSEDED'"),
                eq("BK-DEPOSIT-ADJ")
        );
        verify(jdbcTemplate).update(
                contains("INSERT INTO tb_booking_deposit_adjustment"),
                eq("BK-DEPOSIT-ADJ"),
                eq(7L),
                eq(USER_ID),
                eq(SHOP_ID),
                eq("TOP_UP"),
                eq("INCIDENT_PROPOSAL"),
                eq(600),
                eq(1200),
                eq(600),
                eq(LocalDate.of(2026, 6, 20)),
                eq("19:30"),
                eq("normal"),
                eq(4),
                eq("改單會增加訂金 NT$ 600，需由店家人工處理後再確認。"),
                eq(600)
        );
    }

    @Test
    void recordSettlementMarksOpenAdjustmentCompletedWithPspReference() {
        Map<String, Object> pending = adjustmentRow("OPEN", false);
        pending.put("settlementStatus", "PENDING");
        Map<String, Object> completed = adjustmentRow("OPEN", false);
        completed.put("settlementStatus", "COMPLETED");
        completed.put("settlementProvider", "TAPPAY");
        completed.put("settlementTransId", "TPY-TOPUP-001");
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq(SHOP_ID)))
                .thenReturn(List.of(pending), List.of(completed));

        Map<String, Object> result = service.recordSettlementForMerchantShop(
                SHOP_ID,
                77L,
                1001L,
                "tappay",
                "TPY-TOPUP-001",
                "TapPay 補款完成"
        );

        assertThat(result)
                .containsEntry("id", 77L)
                .containsEntry("settlementStatus", "COMPLETED")
                .containsEntry("settlementProvider", "TAPPAY")
                .containsEntry("settlementTransId", "TPY-TOPUP-001")
                .containsEntry("settlementAmount", 600);
        verify(jdbcTemplate).update(
                contains("settlement_status = 'COMPLETED'"),
                eq("TAPPAY"),
                eq("TPY-TOPUP-001"),
                eq(600),
                eq("TapPay 補款完成"),
                eq(1001L),
                eq(77L),
                eq(SHOP_ID)
        );
    }

    @Test
    void recordSettlementRejectsRefundDirectCompletion() {
        Map<String, Object> pendingRefund = refundAdjustmentRow("PENDING");
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq(SHOP_ID)))
                .thenReturn(List.of(pendingRefund));

        assertThatThrownBy(() -> service.recordSettlementForMerchantShop(
                SHOP_ID,
                77L,
                1001L,
                "TAPPAY",
                "RF-DIRECT-001",
                "退款完成"
        )).isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("退款需先建立退款請求");
    }

    @Test
    void requestRefundMovesRefundAdjustmentToProcessing() {
        Map<String, Object> pendingRefund = refundAdjustmentRow("PENDING");
        Map<String, Object> processingRefund = refundAdjustmentRow("PROCESSING");
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq(SHOP_ID)))
                .thenReturn(List.of(pendingRefund), List.of(processingRefund));

        Map<String, Object> result = service.requestRefundForMerchantShop(
                SHOP_ID,
                77L,
                1001L,
                "建立退款請求"
        );

        assertThat(result)
                .containsEntry("id", 77L)
                .containsEntry("adjustmentType", "REFUND")
                .containsEntry("settlementStatus", "PROCESSING")
                .containsEntry("settlementAmount", 600);
        verify(jdbcTemplate).update(
                contains("settlement_status = 'PROCESSING'"),
                eq(600),
                eq("建立退款請求"),
                eq(1001L),
                eq(77L),
                eq(SHOP_ID)
        );
        verify(jdbcTemplate).update(
                contains("INSERT IGNORE INTO tb_booking_refund_reconciliation_event"),
                isNull(),
                eq(77L),
                eq("BK-DEPOSIT-ADJ"),
                eq("REFUND_REQUESTED"),
                eq("PROCESSING"),
                eq(600),
                isNull(),
                eq("建立退款請求"),
                eq(1001L)
        );
    }

    @Test
    void refundSlaSummaryCountsFailedAndStuckProcessingRefunds() {
        Map<String, Object> failedRefund = refundAdjustmentRow("FAILED");
        failedRefund.put("settlementRequestedAt", LocalDateTime.of(2026, 6, 20, 10, 0));
        Map<String, Object> stuckRefund = refundAdjustmentRow("PROCESSING");
        stuckRefund.put("id", 78L);
        stuckRefund.put("settlementRequestedAt", LocalDateTime.of(2026, 6, 20, 9, 30));
        when(jdbcTemplate.queryForList(anyString(), eq(SHOP_ID), eq(30)))
                .thenReturn(List.of(failedRefund, stuckRefund));

        Map<String, Object> result = service.refundSlaSummaryForMerchantShop(SHOP_ID, 30);

        assertThat(result)
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("stuckMinutes", 30)
                .containsEntry("stuckProcessingCount", 1)
                .containsEntry("failedCount", 1)
                .containsEntry("totalAttentionCount", 2)
                .containsEntry("oldestRequestedAt", "2026-06-20T09:30");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) result.get("items");
        assertThat(items).extracting(item -> item.get("slaReason"))
                .containsExactly("FAILED_REFUND", "STUCK_PROCESSING");
        verify(jdbcTemplate).queryForList(
                contains("DATE_SUB(CURRENT_TIMESTAMP, INTERVAL ? MINUTE)"),
                eq(SHOP_ID),
                eq(30)
        );
    }

    @Test
    void refundOperationsReportSplitsPendingAndEscalatedRefunds() {
        Map<String, Object> failedRefund = refundAdjustmentRow("FAILED");
        failedRefund.put("settlementRequestedAt", LocalDateTime.of(2026, 6, 20, 10, 0));
        Map<String, Object> escalatedStuckRefund = refundAdjustmentRow("PROCESSING");
        escalatedStuckRefund.put("id", 78L);
        escalatedStuckRefund.put("settlementRequestedAt", LocalDateTime.of(2026, 6, 20, 9, 30));
        escalatedStuckRefund.put("refundEscalatedAt", LocalDateTime.of(2026, 6, 20, 11, 0));
        escalatedStuckRefund.put("refundEscalationNote", "已建立 TapPay 後台工單 RF-001");
        when(jdbcTemplate.queryForList(anyString(), eq(SHOP_ID), eq(30)))
                .thenReturn(List.of(failedRefund, escalatedStuckRefund));

        Map<String, Object> result = service.refundOperationsReportForMerchantShop(SHOP_ID, 30);

        assertThat(result)
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("status", "ACTION_REQUIRED")
                .containsEntry("recommendedAction", "ESCALATE_FAILED_REFUNDS")
                .containsEntry("headline", "1 件退款需要升級處理")
                .containsEntry("pendingEscalationCount", 1)
                .containsEntry("escalatedCount", 1)
                .containsEntry("pendingFailedCount", 1)
                .containsEntry("escalatedStuckProcessingCount", 1)
                .containsEntry("oldestPendingRequestedAt", "2026-06-20T10:00")
                .containsEntry("oldestEscalatedAt", "2026-06-20T11:00");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> pending = (List<Map<String, Object>>) result.get("pendingEscalationItems");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> escalated = (List<Map<String, Object>>) result.get("escalatedItems");
        assertThat(pending).extracting(item -> item.get("slaReason")).containsExactly("FAILED_REFUND");
        assertThat(escalated).extracting(item -> item.get("slaReason")).containsExactly("STUCK_PROCESSING");
    }

    @Test
    void refundOperationsNotificationPolicyAllowsDispatchWhenAttentionAndNoCooldown() {
        Map<String, Object> failedRefund = refundAdjustmentRow("FAILED");
        failedRefund.put("settlementRequestedAt", LocalDateTime.of(2026, 6, 20, 10, 0));
        when(jdbcTemplate.queryForList(anyString(), eq(SHOP_ID), eq(30)))
                .thenReturn(List.of(failedRefund));
        when(jdbcTemplate.queryForList(
                contains("tb_merchant_notification_dispatch"),
                eq(120),
                eq(120),
                eq(SHOP_ID),
                eq("REFUND_OPERATIONS_DIGEST")
        )).thenReturn(List.of());

        Map<String, Object> result = service.refundOperationsNotificationPolicyForMerchantShop(SHOP_ID, 30, 120);

        assertThat(result)
                .containsEntry("notificationType", "REFUND_OPERATIONS_DIGEST")
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("cooldownMinutes", 120)
                .containsEntry("shouldNotify", true)
                .containsEntry("reason", "ACTION_REQUIRED")
                .containsEntry("totalAttentionCount", 1)
                .containsEntry("pendingEscalationCount", 1);
    }

    @Test
    void refundOperationsNotificationPolicySkipsDuringCooldown() {
        Map<String, Object> failedRefund = refundAdjustmentRow("FAILED");
        failedRefund.put("settlementRequestedAt", LocalDateTime.of(2026, 6, 20, 10, 0));
        Map<String, Object> lastSent = new LinkedHashMap<>();
        lastSent.put("lastSentAt", LocalDateTime.of(2026, 6, 20, 11, 0));
        lastSent.put("nextEligibleAt", LocalDateTime.of(2026, 6, 20, 13, 0));
        lastSent.put("cooldownActive", 1);
        when(jdbcTemplate.queryForList(anyString(), eq(SHOP_ID), eq(30)))
                .thenReturn(List.of(failedRefund));
        when(jdbcTemplate.queryForList(
                contains("tb_merchant_notification_dispatch"),
                eq(120),
                eq(120),
                eq(SHOP_ID),
                eq("REFUND_OPERATIONS_DIGEST")
        )).thenReturn(List.of(lastSent));

        Map<String, Object> result = service.refundOperationsNotificationPolicyForMerchantShop(SHOP_ID, 30, 120);

        assertThat(result)
                .containsEntry("shouldNotify", false)
                .containsEntry("reason", "COOLDOWN_ACTIVE")
                .containsEntry("lastSentAt", "2026-06-20T11:00")
                .containsEntry("nextEligibleAt", "2026-06-20T13:00");
    }

    @Test
    void recordRefundOperationsNotificationDispatchWritesAuditRow() {
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("stuckMinutes", 30);
        report.put("status", "ACTION_REQUIRED");
        report.put("headline", "1 件退款需要升級處理");
        report.put("totalAttentionCount", 2);
        report.put("pendingEscalationCount", 1);
        report.put("escalatedCount", 1);

        service.recordRefundOperationsNotificationDispatch(
                SHOP_ID,
                "scheduled",
                "sent",
                "ACTION_REQUIRED",
                report,
                120,
                "Umerchant123"
        );

        verify(jdbcTemplate).update(
                contains("INSERT INTO tb_merchant_notification_dispatch"),
                eq(SHOP_ID),
                eq("REFUND_OPERATIONS_DIGEST"),
                eq("SCHEDULED"),
                eq("SENT"),
                eq("ACTION_REQUIRED"),
                eq("ACTION_REQUIRED"),
                eq(2),
                eq(1),
                eq(1),
                eq(30),
                eq(120),
                eq("Umerchant123"),
                eq("1 件退款需要升級處理"),
                eq("SENT")
        );
    }

    @Test
    void escalateRefundMarksAdjustmentAndWritesAuditEvent() {
        Map<String, Object> failedRefund = refundAdjustmentRow("FAILED");
        Map<String, Object> escalatedRefund = refundAdjustmentRow("FAILED");
        escalatedRefund.put("refundEscalatedAt", LocalDateTime.of(2026, 6, 20, 11, 0));
        escalatedRefund.put("refundEscalationNote", "已建立 TapPay 後台工單 RF-001");
        escalatedRefund.put("refundEscalatedByUserId", 1001L);
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq(SHOP_ID)))
                .thenReturn(List.of(failedRefund), List.of(escalatedRefund));

        Map<String, Object> result = service.escalateRefundForMerchantShop(
                SHOP_ID,
                77L,
                1001L,
                "已建立 TapPay 後台工單 RF-001"
        );

        assertThat(result)
                .containsEntry("id", 77L)
                .containsEntry("adjustmentType", "REFUND")
                .containsEntry("settlementStatus", "FAILED")
                .containsEntry("refundEscalationNote", "已建立 TapPay 後台工單 RF-001")
                .containsEntry("refundEscalatedByUserId", 1001L);
        verify(jdbcTemplate).update(
                contains("refund_escalated_at = CURRENT_TIMESTAMP"),
                eq("已建立 TapPay 後台工單 RF-001"),
                eq(1001L),
                eq(77L),
                eq(SHOP_ID)
        );
        verify(jdbcTemplate).update(
                contains("INSERT IGNORE INTO tb_booking_refund_reconciliation_event"),
                isNull(),
                eq(77L),
                eq("BK-DEPOSIT-ADJ"),
                eq("REFUND_ESCALATED"),
                eq("FAILED"),
                eq(600),
                isNull(),
                eq("已建立 TapPay 後台工單 RF-001"),
                eq(1001L)
        );
    }

    @Test
    void reconcileRefundCompletedMarksRefundSettlementComplete() {
        Map<String, Object> processingRefund = refundAdjustmentRow("PROCESSING");
        Map<String, Object> completedRefund = refundAdjustmentRow("COMPLETED");
        completedRefund.put("settlementTransId", "RF-TAPPAY-001");
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq("BK-DEPOSIT-ADJ")))
                .thenReturn(List.of(processingRefund), List.of(completedRefund));

        Map<String, Object> result = service.reconcileRefund(
                77L,
                "BK-DEPOSIT-ADJ",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "TapPay refund completed"
        );

        assertThat(result)
                .containsEntry("id", 77L)
                .containsEntry("adjustmentType", "REFUND")
                .containsEntry("settlementStatus", "COMPLETED")
                .containsEntry("settlementTransId", "RF-TAPPAY-001");
        verify(jdbcTemplate).update(
                contains("settlement_status = 'COMPLETED'"),
                eq("RF-TAPPAY-001"),
                eq(600),
                eq("TapPay refund completed"),
                eq(77L),
                eq("BK-DEPOSIT-ADJ")
        );
    }

    @Test
    void reconcileRefundDuplicateEventKeyReturnsIdempotentReplay() {
        Map<String, Object> processingRefund = refundAdjustmentRow("PROCESSING");
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq("BK-DEPOSIT-ADJ")))
                .thenReturn(List.of(processingRefund));
        when(jdbcTemplate.update(
                contains("INSERT IGNORE INTO tb_booking_refund_reconciliation_event"),
                eq("evt-refund-001"),
                eq(77L),
                eq("BK-DEPOSIT-ADJ"),
                eq("REFUND_RECONCILIATION"),
                eq("COMPLETED"),
                eq(600),
                eq("RF-TAPPAY-001"),
                eq("TapPay refund completed"),
                isNull()
        )).thenReturn(0);

        Map<String, Object> result = service.reconcileRefund(
                77L,
                "BK-DEPOSIT-ADJ",
                600,
                "COMPLETED",
                "RF-TAPPAY-001",
                "TapPay refund completed",
                "evt-refund-001"
        );

        assertThat(result)
                .containsEntry("id", 77L)
                .containsEntry("settlementStatus", "PROCESSING")
                .containsEntry("idempotentReplay", true);
    }

    @Test
    void reconcileRefundFailedKeepsRefundUnapplied() {
        Map<String, Object> processingRefund = refundAdjustmentRow("PROCESSING");
        Map<String, Object> failedRefund = refundAdjustmentRow("FAILED");
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq("BK-DEPOSIT-ADJ")))
                .thenReturn(List.of(processingRefund), List.of(failedRefund));

        Map<String, Object> result = service.reconcileRefund(
                77L,
                "BK-DEPOSIT-ADJ",
                600,
                "FAILED",
                null,
                "TapPay refund failed"
        );

        assertThat(result)
                .containsEntry("id", 77L)
                .containsEntry("adjustmentType", "REFUND")
                .containsEntry("settlementStatus", "FAILED");
    }

    @Test
    void listOpenTopUpsForCustomerReturnsCustomerPayload() {
        Map<String, Object> pending = adjustmentRow("OPEN", false);
        pending.put("settlementStatus", "PENDING");
        when(jdbcTemplate.queryForList(anyString(), eq(USER_ID)))
                .thenReturn(List.of(pending));

        List<Map<String, Object>> result = service.listOpenTopUpsForCustomer(USER_ID);

        assertThat(result).hasSize(1);
        assertThat(result.get(0))
                .containsEntry("id", 77L)
                .containsEntry("adjustmentType", "TOP_UP")
                .containsEntry("settlementStatus", "PENDING")
                .containsEntry("deltaAmount", 600);
    }

    @Test
    void payableTopUpRejectsAlreadyCompletedSettlement() {
        Map<String, Object> completed = adjustmentRow("OPEN", false);
        completed.put("settlementStatus", "COMPLETED");
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq(USER_ID)))
                .thenReturn(List.of(completed));

        assertThatThrownBy(() -> service.payableTopUpForCustomer(USER_ID, 77L))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("已完成");
    }

    @Test
    void recordCustomerTopUpSettlementMarksCustomerAdjustmentCompleted() {
        Map<String, Object> pending = adjustmentRow("OPEN", false);
        pending.put("settlementStatus", "PENDING");
        Map<String, Object> completed = adjustmentRow("OPEN", false);
        completed.put("settlementStatus", "COMPLETED");
        completed.put("settlementTransId", "TPY-CUSTOMER-TOPUP");
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq(USER_ID)))
                .thenReturn(List.of(pending), List.of(completed));

        Map<String, Object> result = service.recordCustomerTopUpSettlement(
                USER_ID,
                77L,
                "TPY-CUSTOMER-TOPUP",
                "Customer TapPay top-up completed"
        );

        assertThat(result)
                .containsEntry("id", 77L)
                .containsEntry("settlementStatus", "COMPLETED")
                .containsEntry("settlementTransId", "TPY-CUSTOMER-TOPUP")
                .containsEntry("settlementAmount", 600);
        verify(jdbcTemplate).update(
                contains("settlement_provider = 'TAPPAY'"),
                eq("TPY-CUSTOMER-TOPUP"),
                eq(600),
                eq("Customer TapPay top-up completed"),
                eq(USER_ID),
                eq(77L),
                eq(USER_ID)
        );
    }

    @Test
    void resolveAndApplyRejectsBeforeSettlementCompletes() {
        Map<String, Object> open = adjustmentRow("OPEN", false);
        open.put("settlementStatus", "PENDING");
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq(SHOP_ID)))
                .thenReturn(List.of(open));

        assertThatThrownBy(() -> service.resolveAndApplyForMerchantShop(
                SHOP_ID,
                77L,
                1001L,
                "直接套用"
        )).isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("PSP");
    }

    @Test
    void resolveAndApplyUsesManualRescheduleOverrideAndClosesIncidentProposal() {
        BookingJpa booking = paidBooking();
        Map<String, Object> open = adjustmentRow("OPEN", false);
        Map<String, Object> resolved = adjustmentRow("RESOLVED", true);
        when(jdbcTemplate.queryForList(anyString(), eq(77L), eq(SHOP_ID)))
                .thenReturn(List.of(open), List.of(resolved));
        when(bookingRepo.findByBookingCode("BK-DEPOSIT-ADJ")).thenReturn(Optional.of(booking));
        when(bookingRescheduleService.rescheduleAfterManualDepositHandling(
                booking,
                LocalDate.of(2026, 6, 20),
                "19:30",
                "normal",
                4
        )).thenReturn(BookingRescheduleService.RescheduleResult.ok(booking, true));

        Map<String, Object> result = service.resolveAndApplyForMerchantShop(
                SHOP_ID,
                77L,
                1001L,
                "已人工補收 NT$ 600"
        );

        assertThat(result)
                .containsEntry("id", 77L)
                .containsEntry("status", "RESOLVED")
                .containsEntry("appliedBookingUpdate", true);
        verify(jdbcTemplate).update(
                contains("UPDATE tb_booking_deposit_adjustment"),
                eq("已人工補收 NT$ 600"),
                eq(1001L),
                eq(77L),
                eq(SHOP_ID)
        );
        verify(jdbcTemplate).update(
                contains("UPDATE tb_booking_incident"),
                eq(7L),
                eq("BK-DEPOSIT-ADJ")
        );
    }

    private BookingJpa paidBooking() {
        BookingJpa booking = new BookingJpa();
        booking.setBookingCode("BK-DEPOSIT-ADJ");
        booking.setUserId(USER_ID);
        booking.setShopId(SHOP_ID);
        booking.setStatus(BookingHoldService.STATUS_PAID);
        booking.setNeedsDeposit(true);
        booking.setDepositPerPerson(300);
        booking.setDepositTotal(600);
        return booking;
    }

    private Map<String, Object> adjustmentRow(String status, boolean applied) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", 77L);
        row.put("bookingCode", "BK-DEPOSIT-ADJ");
        row.put("incidentId", 7L);
        row.put("userId", USER_ID);
        row.put("shopId", SHOP_ID);
        row.put("shopName", "橘色涮涮屋 信義館");
        row.put("bookingDate", LocalDate.of(2026, 6, 20));
        row.put("bookingTime", "19:00");
        row.put("bookingPeople", 2);
        row.put("bookingTableType", "normal");
        row.put("bookingStatus", BookingHoldService.STATUS_PAID);
        row.put("status", status);
        row.put("adjustmentType", "TOP_UP");
        row.put("source", "INCIDENT_PROPOSAL");
        row.put("currentDepositTotal", 600);
        row.put("proposedDepositTotal", 1200);
        row.put("deltaAmount", 600);
        row.put("proposedDate", LocalDate.of(2026, 6, 20));
        row.put("proposedTime", "19:30");
        row.put("proposedTableType", "normal");
        row.put("proposedPeople", 4);
        row.put("message", "改單會增加訂金 NT$ 600，需由店家人工處理後再確認。");
        row.put("appliedBookingUpdate", applied ? 1 : 0);
        row.put("settlementStatus", "COMPLETED");
        row.put("settlementProvider", "TAPPAY");
        row.put("settlementTransId", "TPY-TOPUP-001");
        row.put("settlementAmount", 600);
        row.put("settlementNote", "TapPay 補款完成");
        return row;
    }

    private Map<String, Object> refundAdjustmentRow(String settlementStatus) {
        Map<String, Object> row = adjustmentRow("OPEN", false);
        row.put("adjustmentType", "REFUND");
        row.put("currentDepositTotal", 1200);
        row.put("proposedDepositTotal", 600);
        row.put("deltaAmount", -600);
        row.put("message", "改單會退還訂金 NT$ 600，需等待 PSP 退款完成後再確認。");
        row.put("settlementStatus", settlementStatus);
        row.put("settlementTransId", "");
        row.put("settlementAmount", 600);
        row.put("settlementNote", "TapPay 退款處理");
        return row;
    }
}
