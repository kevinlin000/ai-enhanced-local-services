package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.service.AvailabilityNotificationService;
import com.bytebites.service.BookingDepositAdjustmentService;
import com.bytebites.service.BookingLineNotificationService;
import com.bytebites.service.LineNotificationClient;
import com.bytebites.service.jpa.UserJpaService;
import com.bytebites.utils.UserHolder;
import org.junit.jupiter.api.AfterEach;
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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class MerchantControllerTest {
    private static final Long MERCHANT_USER_ID = 1001L;
    private static final Long SHOP_ID = 10009L;

    @Mock
    private JdbcTemplate jdbcTemplate;
    @Mock
    private AvailabilityNotificationService availabilityNotificationService;
    @Mock
    private BookingLineNotificationService bookingLineNotificationService;
    @Mock
    private BookingDepositAdjustmentService bookingDepositAdjustmentService;
    @Mock
    private UserJpaService userJpaService;
    @Mock
    private LineNotificationClient lineNotificationClient;

    private MerchantController controller;

    @BeforeEach
    void setUp() {
        controller = new MerchantController(
                jdbcTemplate,
                availabilityNotificationService,
                bookingLineNotificationService,
                bookingDepositAdjustmentService,
                userJpaService,
                lineNotificationClient
        );
        UserDTO user = new UserDTO();
        user.setId(MERCHANT_USER_ID);
        UserHolder.saveUser(user);
    }

    @AfterEach
    void tearDown() {
        UserHolder.removeUser();
    }

    @Test
    void incidentsListsOpenIncidentsForOwnedShop() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        when(jdbcTemplate.queryForList(anyString(), eq(SHOP_ID), eq("OPEN")))
                .thenReturn(List.of(openIncidentRow()));
        when(jdbcTemplate.queryForList(anyString(), eq(SHOP_ID), eq(LocalDate.of(2026, 6, 20)), eq("normal")))
                .thenReturn(List.of(
                        slotRow("19:30", 6, 1),
                        slotRow("20:00", 2, 2)
                ));

        Result result = controller.incidents(SHOP_ID, "OPEN");

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> incidents = (List<Map<String, Object>>) data.get("incidents");
        assertThat(data).containsEntry("shopId", SHOP_ID).containsEntry("status", "OPEN");
        assertThat(incidents).hasSize(1);
        assertThat(incidents.get(0))
                .containsEntry("id", 7L)
                .containsEntry("bookingCode", "BK-MERCHANT-INC")
                .containsEntry("bookingStatus", "PAID")
                .containsEntry("incidentType", "CUSTOMER_LATE")
                .containsEntry("adjustedTime", "19:20");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> alternativeSlots =
                (List<Map<String, Object>>) incidents.get(0).get("alternativeSlots");
        assertThat(alternativeSlots).hasSize(3);
        assertThat(alternativeSlots.get(0))
                .containsEntry("time", "19:30")
                .containsEntry("remaining", 5)
                .containsEntry("label", "同日 19:30");
        assertThat(alternativeSlots)
                .extracting(slot -> slot.get("time"))
                .doesNotContain("20:00");
    }

    @Test
    void resolveIncidentOnlyUpdatesOpenIncidentForOwnedShop() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        when(jdbcTemplate.update(anyString(), eq(7L), eq(SHOP_ID))).thenReturn(1);
        Map<String, Object> resolved = openIncidentRow();
        resolved.put("status", "RESOLVED");
        resolved.put("resolvedAt", LocalDateTime.of(2026, 6, 19, 18, 55));
        when(jdbcTemplate.queryForList(anyString(), eq(7L), eq(SHOP_ID))).thenReturn(List.of(resolved));

        Result result = controller.resolveIncident(SHOP_ID, 7L);

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("id", 7L)
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("status", "RESOLVED");
    }

    @Test
    void proposeIncidentSlotCreatesPendingCustomerProposal() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> proposed = openIncidentRow();
        proposed.put("proposalStatus", "PENDING");
        proposed.put("proposedDate", LocalDate.of(2026, 6, 20));
        proposed.put("proposedTime", "19:30");
        proposed.put("proposedTableType", "normal");
        proposed.put("proposedPeople", 2);
        proposed.put("proposalMessage", "店家建議改到 2026-06-20 19:30，請確認是否接受。");
        proposed.put("proposedAt", LocalDateTime.of(2026, 6, 19, 18, 45));
        when(jdbcTemplate.queryForList(anyString(), eq(7L), eq(SHOP_ID)))
                .thenReturn(List.of(openIncidentRow()))
                .thenReturn(List.of(proposed));
        when(jdbcTemplate.queryForList(anyString(), eq(SHOP_ID), eq(LocalDate.of(2026, 6, 20)), eq("normal")))
                .thenReturn(List.of(slotRow("19:30", 6, 1)));
        when(jdbcTemplate.update(
                anyString(),
                eq(LocalDate.of(2026, 6, 20)),
                eq("19:30"),
                eq("normal"),
                eq(2),
                any(),
                eq(7L),
                eq(SHOP_ID)
        )).thenReturn(1);

        Result result = controller.proposeIncidentSlot(
                SHOP_ID,
                7L,
                Map.of("time", "19:30")
        );

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        @SuppressWarnings("unchecked")
        Map<String, Object> proposedChange = (Map<String, Object>) data.get("proposedChange");
        assertThat(proposedChange)
                .containsEntry("status", "PENDING")
                .containsEntry("date", "2026-06-20")
                .containsEntry("time", "19:30")
                .containsEntry("people", 2);
        verify(bookingLineNotificationService).pushBookingIncidentProposal(data);
    }

    @Test
    void incidentsRejectsShopWithoutMerchantOwnership() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(0);

        Result result = controller.incidents(SHOP_ID, "OPEN");

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).contains("管理權限");
    }

    @Test
    void depositAdjustmentsListsOpenItemsForOwnedShop() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        when(bookingDepositAdjustmentService.listForMerchantShop(SHOP_ID, "OPEN"))
                .thenReturn(List.of(depositAdjustmentPayload()));

        Result result = controller.depositAdjustments(SHOP_ID, "OPEN");

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> adjustments = (List<Map<String, Object>>) data.get("adjustments");
        assertThat(data).containsEntry("shopId", SHOP_ID).containsEntry("status", "OPEN");
        assertThat(adjustments).hasSize(1);
        assertThat(adjustments.get(0))
                .containsEntry("id", 77L)
                .containsEntry("bookingCode", "BK-MERCHANT-INC")
                .containsEntry("adjustmentType", "TOP_UP")
                .containsEntry("deltaAmount", 600);
    }

    @Test
    void refundSlaSummaryListsAttentionItemsForOwnedShop() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("shopId", SHOP_ID);
        summary.put("stuckMinutes", 30);
        summary.put("stuckProcessingCount", 1);
        summary.put("failedCount", 1);
        summary.put("totalAttentionCount", 2);
        summary.put("items", List.of(depositAdjustmentPayload()));
        when(bookingDepositAdjustmentService.refundSlaSummaryForMerchantShop(SHOP_ID, 30))
                .thenReturn(summary);

        Result result = controller.refundSlaSummary(SHOP_ID, 30);

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("stuckProcessingCount", 1)
                .containsEntry("failedCount", 1)
                .containsEntry("totalAttentionCount", 2);
        verify(bookingDepositAdjustmentService).refundSlaSummaryForMerchantShop(SHOP_ID, 30);
    }

    @Test
    void refundOperationsReportListsDigestForOwnedShop() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("shopId", SHOP_ID);
        report.put("status", "ACTION_REQUIRED");
        report.put("recommendedAction", "ESCALATE_FAILED_REFUNDS");
        report.put("headline", "1 件退款需要升級處理");
        report.put("pendingEscalationCount", 1);
        report.put("escalatedCount", 1);
        report.put("pendingEscalationItems", List.of(depositAdjustmentPayload()));
        report.put("escalatedItems", List.of(depositAdjustmentPayload()));
        when(bookingDepositAdjustmentService.refundOperationsReportForMerchantShop(SHOP_ID, 30))
                .thenReturn(report);

        Result result = controller.refundOperationsReport(SHOP_ID, 30);

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("status", "ACTION_REQUIRED")
                .containsEntry("recommendedAction", "ESCALATE_FAILED_REFUNDS")
                .containsEntry("pendingEscalationCount", 1)
                .containsEntry("escalatedCount", 1);
        verify(bookingDepositAdjustmentService).refundOperationsReportForMerchantShop(SHOP_ID, 30);
    }

    @Test
    void notifyRefundOperationsReportPushesLineDigestForLinkedMerchant() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("shopId", SHOP_ID);
        report.put("status", "ACTION_REQUIRED");
        report.put("headline", "1 件退款需要升級處理");
        report.put("totalAttentionCount", 1);
        report.put("pendingEscalationItems", List.of(depositAdjustmentPayload()));
        report.put("escalatedItems", List.of());
        when(bookingDepositAdjustmentService.refundOperationsReportForMerchantShop(SHOP_ID, 30))
                .thenReturn(report);
        when(userJpaService.findLineNotificationUserId(MERCHANT_USER_ID))
                .thenReturn(Optional.of("Umerchant123"));

        Result result = controller.notifyRefundOperationsReport(SHOP_ID, 30);

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("lineNotification", "SENT")
                .containsEntry("skipped", false);
        @SuppressWarnings("unchecked")
        Map<String, Object> pushedReport = (Map<String, Object>) data.get("report");
        assertThat(pushedReport)
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("shopName", "橘色涮涮屋 信義館");
        verify(lineNotificationClient).pushRefundOperationsDigest("Umerchant123", pushedReport);
    }

    @Test
    void notifyRefundOperationsReportSkipsWhenMerchantHasNoLinkedLineUser() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("shopId", SHOP_ID);
        report.put("headline", "1 件退款需要升級處理");
        report.put("totalAttentionCount", 1);
        report.put("pendingEscalationItems", List.of(depositAdjustmentPayload()));
        report.put("escalatedItems", List.of());
        when(bookingDepositAdjustmentService.refundOperationsReportForMerchantShop(SHOP_ID, 30))
                .thenReturn(report);
        when(userJpaService.findLineNotificationUserId(MERCHANT_USER_ID))
                .thenReturn(Optional.empty());

        Result result = controller.notifyRefundOperationsReport(SHOP_ID, 30);

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("lineNotification", "SKIPPED")
                .containsEntry("skipped", true)
                .containsEntry("reason", "NO_LINKED_LINE_USER");
    }

    @Test
    void refundOperationsNotificationPolicyReturnsDueStateForOwnedShop() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> report = refundReportPayload();
        Map<String, Object> policy = new LinkedHashMap<>();
        policy.put("notificationType", "REFUND_OPERATIONS_DIGEST");
        policy.put("shopId", SHOP_ID);
        policy.put("shouldNotify", true);
        policy.put("reason", "ACTION_REQUIRED");
        policy.put("cooldownMinutes", 120);
        policy.put("totalAttentionCount", 1);
        when(bookingDepositAdjustmentService.refundOperationsReportForMerchantShop(SHOP_ID, 30))
                .thenReturn(report);
        when(bookingDepositAdjustmentService.refundOperationsNotificationPolicyForReport(any(), eq(120)))
                .thenReturn(policy);

        Result result = controller.refundOperationsNotificationPolicy(SHOP_ID, 30, 120);

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("notificationType", "REFUND_OPERATIONS_DIGEST")
                .containsEntry("shouldNotify", true)
                .containsEntry("reason", "ACTION_REQUIRED");
    }

    @Test
    void dispatchRefundOperationsReportIfDueSkipsDuringCooldown() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> report = refundReportPayload();
        Map<String, Object> policy = new LinkedHashMap<>();
        policy.put("notificationType", "REFUND_OPERATIONS_DIGEST");
        policy.put("shopId", SHOP_ID);
        policy.put("shouldNotify", false);
        policy.put("reason", "COOLDOWN_ACTIVE");
        policy.put("cooldownMinutes", 120);
        policy.put("lastSentAt", "2026-06-20T11:00");
        policy.put("nextEligibleAt", "2026-06-20T13:00");
        when(bookingDepositAdjustmentService.refundOperationsReportForMerchantShop(SHOP_ID, 30))
                .thenReturn(report);
        when(bookingDepositAdjustmentService.refundOperationsNotificationPolicyForReport(any(), eq(120)))
                .thenReturn(policy);

        Result result = controller.dispatchRefundOperationsReportIfDue(SHOP_ID, 30, 120);

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("lineNotification", "SKIPPED")
                .containsEntry("skipped", true)
                .containsEntry("reason", "COOLDOWN_ACTIVE");
        verifyNoInteractions(lineNotificationClient);
    }

    @Test
    void dispatchRefundOperationsReportIfDuePushesLineDigestAndRecordsAuditWhenDue() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> report = refundReportPayload();
        Map<String, Object> policy = new LinkedHashMap<>();
        policy.put("notificationType", "REFUND_OPERATIONS_DIGEST");
        policy.put("shopId", SHOP_ID);
        policy.put("shouldNotify", true);
        policy.put("reason", "ACTION_REQUIRED");
        policy.put("cooldownMinutes", 120);
        when(bookingDepositAdjustmentService.refundOperationsReportForMerchantShop(SHOP_ID, 30))
                .thenReturn(report);
        when(bookingDepositAdjustmentService.refundOperationsNotificationPolicyForReport(any(), eq(120)))
                .thenReturn(policy);
        when(userJpaService.findLineNotificationUserId(MERCHANT_USER_ID))
                .thenReturn(Optional.of("Umerchant123"));

        Result result = controller.dispatchRefundOperationsReportIfDue(SHOP_ID, 30, 120);

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("lineNotification", "SENT")
                .containsEntry("skipped", false);
        verify(lineNotificationClient).pushRefundOperationsDigest(eq("Umerchant123"), any());
        verify(bookingDepositAdjustmentService).recordRefundOperationsNotificationDispatch(
                eq(SHOP_ID),
                eq("SCHEDULED"),
                eq("SENT"),
                eq("ACTION_REQUIRED"),
                any(),
                eq(120),
                eq("Umerchant123")
        );
    }

    @Test
    void resolveDepositAdjustmentAppliesManualChangeForOwnedShop() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> resolved = depositAdjustmentPayload();
        resolved.put("status", "RESOLVED");
        resolved.put("appliedBookingUpdate", true);
        when(bookingDepositAdjustmentService.resolveAndApplyForMerchantShop(
                eq(SHOP_ID),
                eq(77L),
                eq(MERCHANT_USER_ID),
                eq("已人工補收 NT$ 600")
        )).thenReturn(resolved);

        Result result = controller.resolveDepositAdjustment(
                SHOP_ID,
                77L,
                Map.of("handlingNote", "已人工補收 NT$ 600")
        );

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("id", 77L)
                .containsEntry("status", "RESOLVED")
                .containsEntry("appliedBookingUpdate", true);
    }

    @Test
    void recordDepositAdjustmentSettlementForOwnedShop() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> completed = depositAdjustmentPayload();
        completed.put("settlementStatus", "COMPLETED");
        completed.put("settlementProvider", "TAPPAY");
        completed.put("settlementTransId", "TPY-TOPUP-001");
        when(bookingDepositAdjustmentService.recordSettlementForMerchantShop(
                eq(SHOP_ID),
                eq(77L),
                eq(MERCHANT_USER_ID),
                eq("TAPPAY"),
                eq("TPY-TOPUP-001"),
                eq("PSP 已完成")
        )).thenReturn(completed);

        Result result = controller.recordDepositAdjustmentSettlement(
                SHOP_ID,
                77L,
                Map.of(
                        "provider", "TAPPAY",
                        "settlementTransId", "TPY-TOPUP-001",
                        "settlementNote", "PSP 已完成"
                )
        );

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("id", 77L)
                .containsEntry("settlementStatus", "COMPLETED")
                .containsEntry("settlementTransId", "TPY-TOPUP-001");
    }

    @Test
    void requestRefundAdjustmentForOwnedShop() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> processing = depositAdjustmentPayload();
        processing.put("adjustmentType", "REFUND");
        processing.put("deltaAmount", -600);
        processing.put("settlementStatus", "PROCESSING");
        when(bookingDepositAdjustmentService.requestRefundForMerchantShop(
                eq(SHOP_ID),
                eq(77L),
                eq(MERCHANT_USER_ID),
                eq("建立退款請求")
        )).thenReturn(processing);

        Result result = controller.requestDepositAdjustmentRefund(
                SHOP_ID,
                77L,
                Map.of("settlementNote", "建立退款請求")
        );

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("id", 77L)
                .containsEntry("adjustmentType", "REFUND")
                .containsEntry("settlementStatus", "PROCESSING");
    }

    @Test
    void escalateRefundAdjustmentForOwnedShop() {
        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), eq(MERCHANT_USER_ID), eq(SHOP_ID)))
                .thenReturn(1);
        Map<String, Object> escalated = depositAdjustmentPayload();
        escalated.put("adjustmentType", "REFUND");
        escalated.put("deltaAmount", -600);
        escalated.put("settlementStatus", "FAILED");
        escalated.put("refundEscalationNote", "已建立 TapPay 後台工單 RF-001");
        escalated.put("refundEscalatedByUserId", MERCHANT_USER_ID);
        when(bookingDepositAdjustmentService.escalateRefundForMerchantShop(
                eq(SHOP_ID),
                eq(77L),
                eq(MERCHANT_USER_ID),
                eq("已建立 TapPay 後台工單 RF-001")
        )).thenReturn(escalated);

        Result result = controller.escalateDepositAdjustmentRefund(
                SHOP_ID,
                77L,
                Map.of("escalationNote", "已建立 TapPay 後台工單 RF-001")
        );

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("id", 77L)
                .containsEntry("adjustmentType", "REFUND")
                .containsEntry("settlementStatus", "FAILED")
                .containsEntry("refundEscalationNote", "已建立 TapPay 後台工單 RF-001");
    }

    private Map<String, Object> openIncidentRow() {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", 7L);
        row.put("bookingCode", "BK-MERCHANT-INC");
        row.put("userId", 1012L);
        row.put("shopId", SHOP_ID);
        row.put("shopName", "橘色涮涮屋 信義館");
        row.put("bookingDate", LocalDate.of(2026, 6, 20));
        row.put("bookingTime", "19:00");
        row.put("people", 2);
        row.put("tableType", "normal");
        row.put("bookingStatus", 2);
        row.put("incidentType", "CUSTOMER_LATE");
        row.put("status", "OPEN");
        row.put("delayMinutes", 20);
        row.put("originalTime", "19:00");
        row.put("adjustedTime", "19:20");
        row.put("title", "已通知店家你會晚到 20 分鐘");
        row.put("customerMessage", "系統已記錄你可能晚到，會協助店家保留到 19:20。");
        row.put("actionLabel", "已通知店家");
        row.put("source", "AI_RESCUE");
        row.put("createdAt", LocalDateTime.of(2026, 6, 19, 18, 40));
        return row;
    }

    private Map<String, Object> slotRow(String time, int capacity, int bookedCount) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("time", time);
        row.put("tableType", "normal");
        row.put("capacity", capacity);
        row.put("bookedCount", bookedCount);
        row.put("remaining", Math.max(capacity - bookedCount, 0));
        return row;
    }

    private Map<String, Object> depositAdjustmentPayload() {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", 77L);
        row.put("bookingCode", "BK-MERCHANT-INC");
        row.put("incidentId", 7L);
        row.put("shopId", SHOP_ID);
        row.put("shopName", "橘色涮涮屋 信義館");
        row.put("bookingDate", "2026-06-20");
        row.put("bookingTime", "19:00");
        row.put("bookingPeople", 2);
        row.put("bookingStatus", "PAID");
        row.put("status", "OPEN");
        row.put("adjustmentType", "TOP_UP");
        row.put("source", "INCIDENT_PROPOSAL");
        row.put("currentDepositTotal", 600);
        row.put("proposedDepositTotal", 1200);
        row.put("deltaAmount", 600);
        row.put("proposedDate", "2026-06-20");
        row.put("proposedTime", "19:30");
        row.put("proposedPeople", 4);
        row.put("message", "改單會增加訂金 NT$ 600，需由店家人工處理後再確認。");
        row.put("appliedBookingUpdate", false);
        row.put("settlementStatus", "PENDING");
        row.put("settlementProvider", "");
        row.put("settlementTransId", "");
        row.put("settlementAmount", 600);
        return row;
    }

    private Map<String, Object> refundReportPayload() {
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("shopId", SHOP_ID);
        report.put("status", "ACTION_REQUIRED");
        report.put("headline", "1 件退款需要升級處理");
        report.put("totalAttentionCount", 1);
        report.put("pendingEscalationCount", 1);
        report.put("escalatedCount", 0);
        report.put("pendingEscalationItems", List.of(depositAdjustmentPayload()));
        report.put("escalatedItems", List.of());
        return report;
    }
}
