package com.bytebites.service;

import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class BookingDepositAdjustmentService {
    private static final String SETTLEMENT_PENDING = "PENDING";
    private static final String SETTLEMENT_PROCESSING = "PROCESSING";
    private static final String SETTLEMENT_COMPLETED = "COMPLETED";
    private static final String SETTLEMENT_FAILED = "FAILED";
    private static final String REFUND_EVENT_REQUESTED = "REFUND_REQUESTED";
    private static final String REFUND_EVENT_RECONCILIATION = "REFUND_RECONCILIATION";
    private static final String REFUND_EVENT_ESCALATED = "REFUND_ESCALATED";
    private static final String NOTIFICATION_REFUND_OPERATIONS_DIGEST = "REFUND_OPERATIONS_DIGEST";
    private static final String DISPATCH_STATUS_SENT = "SENT";
    private static final String DISPATCH_STATUS_SKIPPED = "SKIPPED";

    private final JdbcTemplate jdbcTemplate;
    private final BookingJpaRepository bookingRepo;
    private final BookingRescheduleService bookingRescheduleService;

    public void recordRequired(
            BookingJpa booking,
            Long incidentId,
            LocalDate proposedDate,
            String proposedTime,
            String proposedTableType,
            int proposedPeople,
            BookingRescheduleService.DepositAdjustment adjustment,
            String source
    ) {
        if (booking == null || adjustment == null || adjustment.allowed() || !adjustment.manualHandlingRequired()) {
            return;
        }
        String adjustmentType = adjustment.delta() > 0 ? "TOP_UP" : "REFUND";
        jdbcTemplate.update(
                """
                INSERT INTO tb_booking_deposit_adjustment (
                    booking_code,
                    incident_id,
                    user_id,
                    shop_id,
                    status,
                    adjustment_type,
                    source,
                    current_deposit_total,
                    proposed_deposit_total,
                    delta_amount,
                    proposed_date,
                    proposed_time,
                    proposed_table_type,
                    proposed_people,
                    message,
                    settlement_status,
                    settlement_amount,
                    settlement_requested_at
                )
                VALUES (?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    incident_id = VALUES(incident_id),
                    user_id = VALUES(user_id),
                    shop_id = VALUES(shop_id),
                    adjustment_type = VALUES(adjustment_type),
                    source = VALUES(source),
                    current_deposit_total = VALUES(current_deposit_total),
                    proposed_deposit_total = VALUES(proposed_deposit_total),
                    message = VALUES(message),
                    settlement_status = CASE
                        WHEN settlement_status = 'COMPLETED' THEN settlement_status
                        ELSE VALUES(settlement_status)
                    END,
                    settlement_amount = VALUES(settlement_amount),
                    settlement_requested_at = COALESCE(settlement_requested_at, CURRENT_TIMESTAMP),
                    updated_at = CURRENT_TIMESTAMP
                """,
                booking.getBookingCode(),
                incidentId,
                booking.getUserId(),
                booking.getShopId(),
                adjustmentType,
                normalizeSource(source),
                adjustment.currentDepositTotal(),
                adjustment.proposedDepositTotal(),
                adjustment.delta(),
                proposedDate,
                proposedTime,
                normalizeTableType(proposedTableType),
                proposedPeople,
                adjustment.message(),
                Math.abs(adjustment.delta())
        );
    }

    public List<Map<String, Object>> listForMerchantShop(Long shopId, String status) {
        String normalizedStatus = normalizeStatus(status);
        List<Map<String, Object>> rows;
        if ("ALL".equals(normalizedStatus)) {
            rows = jdbcTemplate.queryForList(
                    depositAdjustmentSql("""
                            WHERE a.shop_id = ?
                            """),
                    shopId
            );
        } else {
            rows = jdbcTemplate.queryForList(
                    depositAdjustmentSql("""
                            WHERE a.shop_id = ?
                              AND a.status = ?
                            """),
                    shopId,
                    normalizedStatus
            );
        }
        return rows.stream().map(this::payload).toList();
    }

    public Map<String, Object> refundSlaSummaryForMerchantShop(Long shopId, int stuckMinutes) {
        int thresholdMinutes = normalizeStuckMinutes(stuckMinutes);
        if (shopId == null) {
            Map<String, Object> empty = new LinkedHashMap<>();
            empty.put("shopId", null);
            empty.put("stuckMinutes", thresholdMinutes);
            empty.put("stuckProcessingCount", 0);
            empty.put("failedCount", 0);
            empty.put("escalatedCount", 0);
            empty.put("pendingEscalationCount", 0);
            empty.put("totalAttentionCount", 0);
            empty.put("items", List.of());
            return empty;
        }

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.shop_id = ?
                          AND a.status = 'OPEN'
                          AND a.adjustment_type = 'REFUND'
                          AND (
                              a.settlement_status = 'FAILED'
                              OR (
                                  a.settlement_status = 'PROCESSING'
                                  AND a.settlement_requested_at IS NOT NULL
                                  AND a.settlement_requested_at <= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL ? MINUTE)
                              )
                          )
                        """),
                shopId,
                thresholdMinutes
        );

        int stuckProcessingCount = 0;
        int failedCount = 0;
        int escalatedCount = 0;
        String oldestRequestedAt = "";
        List<Map<String, Object>> items = rows.stream().map(row -> {
            Map<String, Object> item = payload(row);
            String settlementStatus = text(row.get("settlementStatus"));
            if (SETTLEMENT_FAILED.equals(settlementStatus)) {
                item.put("slaReason", "FAILED_REFUND");
            } else {
                item.put("slaReason", "STUCK_PROCESSING");
            }
            return item;
        }).toList();

        for (Map<String, Object> item : items) {
            String reason = text(item.get("slaReason"));
            if ("FAILED_REFUND".equals(reason)) {
                failedCount++;
            } else if ("STUCK_PROCESSING".equals(reason)) {
                stuckProcessingCount++;
            }
            if (!text(item.get("refundEscalatedAt")).isBlank()) {
                escalatedCount++;
            }
            String requestedAt = text(item.get("settlementRequestedAt"));
            if (!requestedAt.isBlank()
                    && (oldestRequestedAt.isBlank() || requestedAt.compareTo(oldestRequestedAt) < 0)) {
                oldestRequestedAt = requestedAt;
            }
        }

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("shopId", shopId);
        summary.put("stuckMinutes", thresholdMinutes);
        summary.put("stuckProcessingCount", stuckProcessingCount);
        summary.put("failedCount", failedCount);
        summary.put("escalatedCount", escalatedCount);
        summary.put("pendingEscalationCount", Math.max(stuckProcessingCount + failedCount - escalatedCount, 0));
        summary.put("totalAttentionCount", stuckProcessingCount + failedCount);
        if (!oldestRequestedAt.isBlank()) {
            summary.put("oldestRequestedAt", oldestRequestedAt);
        }
        summary.put("items", items);
        return summary;
    }

    public Map<String, Object> refundOperationsReportForMerchantShop(Long shopId, int stuckMinutes) {
        Map<String, Object> summary = refundSlaSummaryForMerchantShop(shopId, stuckMinutes);
        List<Map<String, Object>> items = refundSummaryItems(summary.get("items"));
        List<Map<String, Object>> pendingEscalationItems = new ArrayList<>();
        List<Map<String, Object>> escalatedItems = new ArrayList<>();
        int pendingFailedCount = 0;
        int pendingStuckProcessingCount = 0;
        int escalatedFailedCount = 0;
        int escalatedStuckProcessingCount = 0;

        for (Map<String, Object> item : items) {
            boolean escalated = !text(item.get("refundEscalatedAt")).isBlank();
            String reason = text(item.get("slaReason"));
            if (escalated) {
                escalatedItems.add(item);
                if ("FAILED_REFUND".equals(reason)) {
                    escalatedFailedCount++;
                } else if ("STUCK_PROCESSING".equals(reason)) {
                    escalatedStuckProcessingCount++;
                }
            } else {
                pendingEscalationItems.add(item);
                if ("FAILED_REFUND".equals(reason)) {
                    pendingFailedCount++;
                } else if ("STUCK_PROCESSING".equals(reason)) {
                    pendingStuckProcessingCount++;
                }
            }
        }

        int pendingCount = pendingEscalationItems.size();
        int escalatedCount = escalatedItems.size();
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("shopId", summary.get("shopId"));
        report.put("stuckMinutes", summary.get("stuckMinutes"));
        report.put("status", refundReportStatus(pendingCount, escalatedCount));
        report.put("recommendedAction", refundReportAction(pendingFailedCount, pendingStuckProcessingCount, escalatedCount));
        report.put("headline", refundReportHeadline(pendingCount, escalatedCount));
        report.put("totalAttentionCount", summary.get("totalAttentionCount"));
        report.put("pendingEscalationCount", pendingCount);
        report.put("escalatedCount", escalatedCount);
        report.put("failedCount", summary.get("failedCount"));
        report.put("stuckProcessingCount", summary.get("stuckProcessingCount"));
        report.put("pendingFailedCount", pendingFailedCount);
        report.put("pendingStuckProcessingCount", pendingStuckProcessingCount);
        report.put("escalatedFailedCount", escalatedFailedCount);
        report.put("escalatedStuckProcessingCount", escalatedStuckProcessingCount);
        String oldestPendingRequestedAt = oldestTimestamp(pendingEscalationItems, "settlementRequestedAt");
        String oldestEscalatedAt = oldestTimestamp(escalatedItems, "refundEscalatedAt");
        if (!oldestPendingRequestedAt.isBlank()) {
            report.put("oldestPendingRequestedAt", oldestPendingRequestedAt);
        }
        if (!oldestEscalatedAt.isBlank()) {
            report.put("oldestEscalatedAt", oldestEscalatedAt);
        }
        report.put("pendingEscalationItems", pendingEscalationItems);
        report.put("escalatedItems", escalatedItems);
        return report;
    }

    public Map<String, Object> refundOperationsNotificationPolicyForMerchantShop(
            Long shopId,
            int stuckMinutes,
            int cooldownMinutes
    ) {
        return refundOperationsNotificationPolicyForReport(
                refundOperationsReportForMerchantShop(shopId, stuckMinutes),
                cooldownMinutes
        );
    }

    public Map<String, Object> refundOperationsNotificationPolicyForReport(
            Map<String, Object> report,
            int cooldownMinutes
    ) {
        Map<String, Object> safeReport = report == null ? Map.of() : report;
        int normalizedCooldownMinutes = normalizeCooldownMinutes(cooldownMinutes);
        Long shopId = toLong(safeReport.get("shopId"));
        int totalAttentionCount = toInt(safeReport.get("totalAttentionCount"));

        Map<String, Object> policy = new LinkedHashMap<>();
        policy.put("notificationType", NOTIFICATION_REFUND_OPERATIONS_DIGEST);
        policy.put("shopId", shopId);
        policy.put("cooldownMinutes", normalizedCooldownMinutes);
        policy.put("reportStatus", text(safeReport.get("status")));
        policy.put("headline", text(safeReport.get("headline")));
        policy.put("totalAttentionCount", totalAttentionCount);
        policy.put("pendingEscalationCount", toInt(safeReport.get("pendingEscalationCount")));
        policy.put("escalatedCount", toInt(safeReport.get("escalatedCount")));
        policy.put("shouldNotify", false);

        if (shopId == null) {
            policy.put("reason", "MISSING_SHOP");
            return policy;
        }
        if (totalAttentionCount <= 0) {
            policy.put("reason", "NO_REFUND_ATTENTION");
            return policy;
        }

        Map<String, Object> lastSent = latestRefundOperationsDigestDispatch(shopId, normalizedCooldownMinutes);
        if (!lastSent.isEmpty()) {
            putIfPresent(policy, "lastSentAt", lastSent.get("lastSentAt"));
            putIfPresent(policy, "nextEligibleAt", lastSent.get("nextEligibleAt"));
            if (truthy(lastSent.get("cooldownActive"))) {
                policy.put("reason", "COOLDOWN_ACTIVE");
                return policy;
            }
        }

        policy.put("shouldNotify", true);
        policy.put("reason", "ACTION_REQUIRED");
        return policy;
    }

    public void recordRefundOperationsNotificationDispatch(
            Long shopId,
            String dispatchSource,
            String status,
            String reason,
            Map<String, Object> report,
            int cooldownMinutes,
            String lineUserId
    ) {
        if (shopId == null) return;
        Map<String, Object> safeReport = report == null ? Map.of() : report;
        String normalizedStatus = normalizeDispatchStatus(status);
        String normalizedSource = normalizeDispatchSource(dispatchSource);
        String normalizedReason = trimToNull(reason);
        int normalizedCooldownMinutes = normalizeCooldownMinutes(cooldownMinutes);
        int stuckMinutes = normalizeStuckMinutes(toInt(safeReport.get("stuckMinutes")));
        int attentionCount = Math.max(toInt(safeReport.get("totalAttentionCount")), 0);
        int pendingCount = Math.max(toInt(safeReport.get("pendingEscalationCount")), 0);
        int escalatedCount = Math.max(toInt(safeReport.get("escalatedCount")), 0);
        String normalizedLineUserId = trimToNull(lineUserId);
        jdbcTemplate.update(
                """
                INSERT INTO tb_merchant_notification_dispatch (
                    shop_id,
                    notification_type,
                    dispatch_source,
                    status,
                    reason,
                    report_status,
                    attention_count,
                    pending_escalation_count,
                    escalated_count,
                    stuck_minutes,
                    cooldown_minutes,
                    line_user_id,
                    headline,
                    sent_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'SENT' THEN CURRENT_TIMESTAMP ELSE NULL END)
                """,
                shopId,
                NOTIFICATION_REFUND_OPERATIONS_DIGEST,
                normalizedSource,
                normalizedStatus,
                normalizedReason,
                trimToNull(text(safeReport.get("status"))),
                attentionCount,
                pendingCount,
                escalatedCount,
                stuckMinutes,
                normalizedCooldownMinutes,
                normalizedLineUserId,
                truncate(text(safeReport.get("headline")), 200),
                normalizedStatus
        );
    }

    @Transactional
    public Map<String, Object> escalateRefundForMerchantShop(
            Long shopId,
            Long adjustmentId,
            Long merchantUserId,
            String escalationNote
    ) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.shop_id = ?
                          AND a.status = 'OPEN'
                          AND a.adjustment_type = 'REFUND'
                        FOR UPDATE
                        """),
                adjustmentId,
                shopId
        );
        if (rows.isEmpty()) {
            throw new IllegalArgumentException("退款差額處理不存在或已完成");
        }

        Map<String, Object> adjustment = rows.get(0);
        String settlementStatus = text(adjustment.get("settlementStatus"));
        if (!SETTLEMENT_FAILED.equals(settlementStatus) && !SETTLEMENT_PROCESSING.equals(settlementStatus)) {
            throw new IllegalStateException("只有退款失敗或處理中的退款可升級處理");
        }
        if (!text(adjustment.get("refundEscalatedAt")).isBlank()) {
            return payload(adjustment);
        }

        String normalizedNote = trimToNull(escalationNote);
        int expectedAmount = Math.abs(toInt(adjustment.get("deltaAmount")));
        jdbcTemplate.update(
                """
                UPDATE tb_booking_deposit_adjustment
                SET refund_escalated_at = CURRENT_TIMESTAMP,
                    refund_escalation_note = ?,
                    refund_escalated_by_user_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND shop_id = ?
                  AND status = 'OPEN'
                  AND adjustment_type = 'REFUND'
                  AND settlement_status IN ('FAILED', 'PROCESSING')
                  AND refund_escalated_at IS NULL
                """,
                normalizedNote,
                merchantUserId,
                adjustmentId,
                shopId
        );
        insertRefundAuditEvent(
                null,
                adjustmentId,
                text(adjustment.get("bookingCode")),
                REFUND_EVENT_ESCALATED,
                settlementStatus,
                expectedAmount,
                trimToNull(text(adjustment.get("settlementTransId"))),
                normalizedNote,
                merchantUserId
        );

        List<Map<String, Object>> refreshed = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.shop_id = ?
                        """),
                adjustmentId,
                shopId
        );
        return refreshed.stream().findFirst().map(this::payload).orElseGet(() -> {
            Map<String, Object> fallback = new LinkedHashMap<>();
            fallback.put("id", adjustmentId);
            fallback.put("adjustmentType", "REFUND");
            fallback.put("settlementStatus", settlementStatus);
            fallback.put("refundEscalatedByUserId", merchantUserId);
            if (normalizedNote != null) {
                fallback.put("refundEscalationNote", normalizedNote);
            }
            return fallback;
        });
    }

    public List<Map<String, Object>> listOpenTopUpsForCustomer(Long userId) {
        if (userId == null) return List.of();
        return jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.user_id = ?
                          AND a.status = 'OPEN'
                          AND a.adjustment_type = 'TOP_UP'
                        """),
                userId
        ).stream().map(this::payload).toList();
    }

    public Map<String, Object> payableTopUpForCustomer(Long userId, Long adjustmentId) {
        List<Map<String, Object>> rows = customerTopUpRows(userId, adjustmentId, false);
        if (rows.isEmpty()) {
            throw new IllegalArgumentException("補款項目不存在或無權操作");
        }
        Map<String, Object> adjustment = rows.get(0);
        if (SETTLEMENT_COMPLETED.equals(text(adjustment.get("settlementStatus")))) {
            throw new IllegalStateException("此補款已完成");
        }
        int expectedAmount = Math.abs(toInt(adjustment.get("deltaAmount")));
        if (expectedAmount <= 0) {
            throw new IllegalArgumentException("補款金額不可為 0");
        }
        return payload(adjustment);
    }

    @Transactional
    public Map<String, Object> recordCustomerTopUpSettlement(
            Long userId,
            Long adjustmentId,
            String settlementTransId,
            String settlementNote
    ) {
        List<Map<String, Object>> rows = customerTopUpRows(userId, adjustmentId, true);
        if (rows.isEmpty()) {
            throw new IllegalArgumentException("補款項目不存在或無權操作");
        }
        Map<String, Object> adjustment = rows.get(0);
        if (SETTLEMENT_COMPLETED.equals(text(adjustment.get("settlementStatus")))) {
            return payload(adjustment);
        }

        String normalizedTransId = trimToNull(settlementTransId);
        if (normalizedTransId == null) {
            throw new IllegalArgumentException("settlementTransId 必填");
        }
        int expectedAmount = Math.abs(toInt(adjustment.get("deltaAmount")));
        if (expectedAmount <= 0) {
            throw new IllegalArgumentException("補款金額不可為 0");
        }

        jdbcTemplate.update(
                """
                UPDATE tb_booking_deposit_adjustment
                SET settlement_status = 'COMPLETED',
                    settlement_provider = 'TAPPAY',
                    settlement_trans_id = ?,
                    settlement_amount = ?,
                    settlement_requested_at = COALESCE(settlement_requested_at, CURRENT_TIMESTAMP),
                    settlement_completed_at = CURRENT_TIMESTAMP,
                    settlement_note = ?,
                    settlement_recorded_by_user_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND user_id = ?
                  AND status = 'OPEN'
                  AND adjustment_type = 'TOP_UP'
                  AND settlement_status <> 'COMPLETED'
                """,
                normalizedTransId,
                expectedAmount,
                trimToNull(settlementNote),
                userId,
                adjustmentId,
                userId
        );

        List<Map<String, Object>> refreshed = customerTopUpRows(userId, adjustmentId, false);
        return refreshed.stream().findFirst().map(this::payload).orElseGet(() -> Map.of(
                "id", adjustmentId,
                "settlementStatus", SETTLEMENT_COMPLETED,
                "settlementProvider", "TAPPAY",
                "settlementTransId", normalizedTransId,
                "settlementAmount", expectedAmount
        ));
    }

    @Transactional
    public Map<String, Object> requestRefundForMerchantShop(
            Long shopId,
            Long adjustmentId,
            Long merchantUserId,
            String settlementNote
    ) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.shop_id = ?
                          AND a.status = 'OPEN'
                          AND a.adjustment_type = 'REFUND'
                        FOR UPDATE
                        """),
                adjustmentId,
                shopId
        );
        if (rows.isEmpty()) {
            throw new IllegalArgumentException("退款差額處理不存在或已完成");
        }

        Map<String, Object> adjustment = rows.get(0);
        String currentStatus = text(adjustment.get("settlementStatus"));
        if (SETTLEMENT_COMPLETED.equals(currentStatus)) {
            return payload(adjustment);
        }

        int expectedAmount = Math.abs(toInt(adjustment.get("deltaAmount")));
        if (expectedAmount <= 0) {
            throw new IllegalArgumentException("退款金額不可為 0");
        }

        jdbcTemplate.update(
                """
                UPDATE tb_booking_deposit_adjustment
                SET settlement_status = 'PROCESSING',
                    settlement_provider = 'TAPPAY',
                    settlement_trans_id = NULL,
                    settlement_amount = ?,
                    settlement_requested_at = COALESCE(settlement_requested_at, CURRENT_TIMESTAMP),
                    settlement_completed_at = NULL,
                    settlement_note = ?,
                    settlement_recorded_by_user_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND shop_id = ?
                  AND status = 'OPEN'
                  AND adjustment_type = 'REFUND'
                  AND settlement_status <> 'COMPLETED'
                """,
                expectedAmount,
                trimToNull(settlementNote),
                merchantUserId,
                adjustmentId,
                shopId
        );
        insertRefundAuditEvent(
                null,
                adjustmentId,
                text(adjustment.get("bookingCode")),
                REFUND_EVENT_REQUESTED,
                SETTLEMENT_PROCESSING,
                expectedAmount,
                null,
                trimToNull(settlementNote),
                merchantUserId
        );

        List<Map<String, Object>> refreshed = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.shop_id = ?
                        """),
                adjustmentId,
                shopId
        );
        return refreshed.stream().findFirst().map(this::payload).orElseGet(() -> Map.of(
                "id", adjustmentId,
                "adjustmentType", "REFUND",
                "settlementStatus", SETTLEMENT_PROCESSING,
                "settlementProvider", "TAPPAY",
                "settlementAmount", expectedAmount
        ));
    }

    @Transactional
    public Map<String, Object> reconcileRefund(
            Long adjustmentId,
            String bookingCode,
            int amount,
            String resultStatus,
            String settlementTransId,
            String settlementNote
    ) {
        return reconcileRefund(
                adjustmentId,
                bookingCode,
                amount,
                resultStatus,
                settlementTransId,
                settlementNote,
                null
        );
    }

    @Transactional
    public Map<String, Object> reconcileRefund(
            Long adjustmentId,
            String bookingCode,
            int amount,
            String resultStatus,
            String settlementTransId,
            String settlementNote,
            String eventKey
    ) {
        String normalizedBookingCode = trimToNull(bookingCode);
        if (adjustmentId == null || normalizedBookingCode == null) {
            throw new IllegalArgumentException("adjustmentId 與 bookingCode 必填");
        }
        String normalizedStatus = normalizeRefundReconciliationStatus(resultStatus);
        String normalizedTransId = trimToNull(settlementTransId);
        String normalizedEventKey = normalizeRefundEventKey(eventKey);
        if (SETTLEMENT_COMPLETED.equals(normalizedStatus) && normalizedTransId == null) {
            throw new IllegalArgumentException("退款完成時 settlementTransId 必填");
        }

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.booking_code = ?
                          AND a.status = 'OPEN'
                          AND a.adjustment_type = 'REFUND'
                        FOR UPDATE
                        """),
                adjustmentId,
                normalizedBookingCode
        );
        if (rows.isEmpty()) {
            throw new IllegalArgumentException("退款差額處理不存在或已完成");
        }

        Map<String, Object> adjustment = rows.get(0);
        String currentStatus = text(adjustment.get("settlementStatus"));
        if (SETTLEMENT_COMPLETED.equals(currentStatus)) {
            return payload(adjustment);
        }
        if (SETTLEMENT_PENDING.equals(currentStatus)) {
            throw new IllegalStateException("請先建立退款請求，再等待 PSP 對帳結果");
        }

        int expectedAmount = Math.abs(toInt(adjustment.get("deltaAmount")));
        if (expectedAmount <= 0) {
            throw new IllegalArgumentException("退款金額不可為 0");
        }
        if (amount != expectedAmount) {
            throw new IllegalArgumentException("退款金額與訂金差額不一致");
        }
        boolean eventInserted = insertRefundAuditEvent(
                normalizedEventKey,
                adjustmentId,
                normalizedBookingCode,
                REFUND_EVENT_RECONCILIATION,
                normalizedStatus,
                expectedAmount,
                normalizedTransId,
                trimToNull(settlementNote),
                null
        );
        if (normalizedEventKey != null && !eventInserted) {
            return payloadWithIdempotentReplay(adjustment);
        }

        if (SETTLEMENT_COMPLETED.equals(normalizedStatus)) {
            jdbcTemplate.update(
                    """
                    UPDATE tb_booking_deposit_adjustment
                    SET settlement_status = 'COMPLETED',
                        settlement_provider = 'TAPPAY',
                        settlement_trans_id = ?,
                        settlement_amount = ?,
                        settlement_requested_at = COALESCE(settlement_requested_at, CURRENT_TIMESTAMP),
                        settlement_completed_at = CURRENT_TIMESTAMP,
                        settlement_note = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                      AND booking_code = ?
                      AND status = 'OPEN'
                      AND adjustment_type = 'REFUND'
                    """,
                    normalizedTransId,
                    expectedAmount,
                    trimToNull(settlementNote),
                    adjustmentId,
                    normalizedBookingCode
            );
        } else {
            jdbcTemplate.update(
                    """
                    UPDATE tb_booking_deposit_adjustment
                    SET settlement_status = 'FAILED',
                        settlement_provider = 'TAPPAY',
                        settlement_trans_id = ?,
                        settlement_amount = ?,
                        settlement_completed_at = NULL,
                        settlement_note = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                      AND booking_code = ?
                      AND status = 'OPEN'
                      AND adjustment_type = 'REFUND'
                    """,
                    normalizedTransId,
                    expectedAmount,
                    trimToNull(settlementNote),
                    adjustmentId,
                    normalizedBookingCode
            );
        }

        List<Map<String, Object>> refreshed = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.booking_code = ?
                        """),
                adjustmentId,
                normalizedBookingCode
        );
        return refreshed.stream().findFirst().map(this::payload).orElseGet(() -> Map.of(
                "id", adjustmentId,
                "bookingCode", normalizedBookingCode,
                "adjustmentType", "REFUND",
                "settlementStatus", normalizedStatus,
                "settlementProvider", "TAPPAY",
                "settlementAmount", expectedAmount
        ));
    }

    private boolean insertRefundAuditEvent(
            String eventKey,
            Long adjustmentId,
            String bookingCode,
            String eventType,
            String resultStatus,
            int amount,
            String settlementTransId,
            String message,
            Long recordedByUserId
    ) {
        int inserted = jdbcTemplate.update(
                """
                INSERT IGNORE INTO tb_booking_refund_reconciliation_event (
                    event_key,
                    adjustment_id,
                    booking_code,
                    event_type,
                    result_status,
                    amount,
                    settlement_trans_id,
                    message,
                    recorded_by_user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                eventKey,
                adjustmentId,
                bookingCode,
                eventType,
                resultStatus,
                amount,
                settlementTransId,
                message,
                recordedByUserId
        );
        return inserted > 0;
    }

    @Transactional
    public Map<String, Object> recordSettlementForMerchantShop(
            Long shopId,
            Long adjustmentId,
            Long merchantUserId,
            String provider,
            String settlementTransId,
            String settlementNote
    ) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.shop_id = ?
                          AND a.status = 'OPEN'
                        FOR UPDATE
                        """),
                adjustmentId,
                shopId
        );
        if (rows.isEmpty()) {
            throw new IllegalArgumentException("訂金差額處理不存在或已完成");
        }

        Map<String, Object> adjustment = rows.get(0);
        if (SETTLEMENT_COMPLETED.equals(text(adjustment.get("settlementStatus")))) {
            return payload(adjustment);
        }
        if ("REFUND".equals(text(adjustment.get("adjustmentType")))) {
            throw new IllegalStateException("退款需先建立退款請求並等待 PSP 對帳回寫");
        }

        String normalizedTransId = trimToNull(settlementTransId);
        if (normalizedTransId == null) {
            throw new IllegalArgumentException("settlementTransId 必填");
        }

        int expectedAmount = Math.abs(toInt(adjustment.get("deltaAmount")));
        if (expectedAmount <= 0) {
            throw new IllegalArgumentException("訂金差額金額不可為 0");
        }

        String normalizedProvider = normalizeProvider(provider);
        jdbcTemplate.update(
                """
                UPDATE tb_booking_deposit_adjustment
                SET settlement_status = 'COMPLETED',
                    settlement_provider = ?,
                    settlement_trans_id = ?,
                    settlement_amount = ?,
                    settlement_requested_at = COALESCE(settlement_requested_at, CURRENT_TIMESTAMP),
                    settlement_completed_at = CURRENT_TIMESTAMP,
                    settlement_note = ?,
                    settlement_recorded_by_user_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND shop_id = ?
                  AND status = 'OPEN'
                  AND settlement_status <> 'COMPLETED'
                """,
                normalizedProvider,
                normalizedTransId,
                expectedAmount,
                trimToNull(settlementNote),
                merchantUserId,
                adjustmentId,
                shopId
        );

        List<Map<String, Object>> refreshed = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.shop_id = ?
                        """),
                adjustmentId,
                shopId
        );
        return refreshed.stream().findFirst().map(this::payload).orElseGet(() -> Map.of(
                "id", adjustmentId,
                "settlementStatus", SETTLEMENT_COMPLETED,
                "settlementProvider", normalizedProvider,
                "settlementTransId", normalizedTransId,
                "settlementAmount", expectedAmount
        ));
    }

    @Transactional
    public Map<String, Object> resolveAndApplyForMerchantShop(
            Long shopId,
            Long adjustmentId,
            Long merchantUserId,
            String handlingNote
    ) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.shop_id = ?
                          AND a.status = 'OPEN'
                        FOR UPDATE
                        """),
                adjustmentId,
                shopId
        );
        if (rows.isEmpty()) {
            throw new IllegalArgumentException("訂金差額處理不存在或已完成");
        }
        Map<String, Object> adjustment = rows.get(0);
        if (!SETTLEMENT_COMPLETED.equals(text(adjustment.get("settlementStatus")))) {
            throw new IllegalStateException("請先完成 PSP 補款/退款記錄，再套用改單");
        }

        String bookingCode = text(adjustment.get("bookingCode"));
        BookingJpa booking = bookingRepo.findByBookingCode(bookingCode).orElse(null);
        if (booking == null) {
            throw new IllegalArgumentException("訂位不存在");
        }

        LocalDate proposedDate = parseDate(text(adjustment.get("proposedDate")));
        String proposedTime = text(adjustment.get("proposedTime"));
        String proposedTableType = normalizeTableType(text(adjustment.get("proposedTableType")));
        int proposedPeople = toInt(adjustment.get("proposedPeople"));
        if (proposedDate == null || proposedTime.isBlank() || proposedPeople <= 0) {
            throw new IllegalArgumentException("訂金差額資料不完整，無法套用改單");
        }

        BookingRescheduleService.RescheduleResult result =
                bookingRescheduleService.rescheduleAfterManualDepositHandling(
                        booking,
                        proposedDate,
                        proposedTime,
                        proposedTableType,
                        proposedPeople
                );
        if (!result.success()) {
            throw new IllegalStateException(result.error());
        }

        jdbcTemplate.update(
                """
                UPDATE tb_booking_deposit_adjustment
                SET status = 'RESOLVED',
                    handling_note = ?,
                    handled_by_user_id = ?,
                    handled_at = CURRENT_TIMESTAMP,
                    applied_booking_update = 1
                WHERE id = ?
                  AND shop_id = ?
                  AND status = 'OPEN'
                """,
                trimToNull(handlingNote),
                merchantUserId,
                adjustmentId,
                shopId
        );

        Long incidentId = toLong(adjustment.get("incidentId"));
        if (incidentId != null) {
            jdbcTemplate.update(
                    """
                    UPDATE tb_booking_incident
                    SET proposal_status = 'ACCEPTED',
                        proposal_accepted_at = CURRENT_TIMESTAMP,
                        status = 'RESOLVED',
                        resolved_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                      AND booking_code = ?
                      AND proposal_status = 'PENDING'
                    """,
                    incidentId,
                    bookingCode
            );
        }

        List<Map<String, Object>> refreshed = jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.shop_id = ?
                        """),
                adjustmentId,
                shopId
        );
        return refreshed.stream().findFirst().map(this::payload).orElseGet(() -> Map.of(
                "id", adjustmentId,
                "status", "RESOLVED",
                "appliedBookingUpdate", true
        ));
    }

    private String depositAdjustmentSql(String whereClause) {
        return """
                SELECT a.id,
                       a.booking_code AS bookingCode,
                       a.incident_id AS incidentId,
                       a.user_id AS userId,
                       a.shop_id AS shopId,
                       s.name AS shopName,
                       b.booking_date AS bookingDate,
                       b.booking_time AS bookingTime,
                       b.people AS bookingPeople,
                       b.table_type AS bookingTableType,
                       b.status AS bookingStatus,
                       a.status,
                       a.adjustment_type AS adjustmentType,
                       a.source,
                       a.current_deposit_total AS currentDepositTotal,
                       a.proposed_deposit_total AS proposedDepositTotal,
                       a.delta_amount AS deltaAmount,
                       a.proposed_date AS proposedDate,
                       a.proposed_time AS proposedTime,
                       a.proposed_table_type AS proposedTableType,
                       a.proposed_people AS proposedPeople,
                       a.message,
                       a.handling_note AS handlingNote,
                       a.handled_by_user_id AS handledByUserId,
                       a.handled_at AS handledAt,
                       a.applied_booking_update AS appliedBookingUpdate,
                       a.settlement_status AS settlementStatus,
                       a.settlement_provider AS settlementProvider,
                       a.settlement_trans_id AS settlementTransId,
                       a.settlement_amount AS settlementAmount,
                       a.settlement_requested_at AS settlementRequestedAt,
                       a.settlement_completed_at AS settlementCompletedAt,
                       a.settlement_note AS settlementNote,
                       a.settlement_recorded_by_user_id AS settlementRecordedByUserId,
                       a.refund_escalated_at AS refundEscalatedAt,
                       a.refund_escalation_note AS refundEscalationNote,
                       a.refund_escalated_by_user_id AS refundEscalatedByUserId,
                       a.created_at AS createdAt,
                       a.updated_at AS updatedAt
                FROM tb_booking_deposit_adjustment a
                JOIN tb_booking b ON b.booking_code = a.booking_code
                JOIN tb_shop s ON s.id = a.shop_id
                %s
                ORDER BY a.created_at DESC
                LIMIT 50
                %s
                """.formatted(withoutLock(whereClause), lockClause(whereClause));
    }

    private List<Map<String, Object>> customerTopUpRows(Long userId, Long adjustmentId, boolean lock) {
        if (userId == null || adjustmentId == null) return List.of();
        return jdbcTemplate.queryForList(
                depositAdjustmentSql("""
                        WHERE a.id = ?
                          AND a.user_id = ?
                          AND a.status = 'OPEN'
                          AND a.adjustment_type = 'TOP_UP'
                        """ + (lock ? " FOR UPDATE" : "")),
                adjustmentId,
                userId
        );
    }

    private Map<String, Object> payload(Map<String, Object> row) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", row.get("id"));
        out.put("bookingCode", text(row.get("bookingCode")));
        out.put("incidentId", row.get("incidentId"));
        out.put("userId", row.get("userId"));
        out.put("shopId", row.get("shopId"));
        out.put("shopName", text(row.get("shopName")));
        out.put("bookingDate", text(row.get("bookingDate")));
        out.put("bookingTime", text(row.get("bookingTime")));
        out.put("bookingPeople", toInt(row.get("bookingPeople")));
        out.put("bookingTableType", text(row.get("bookingTableType")));
        out.put("bookingStatus", bookingStatusName(row.get("bookingStatus")));
        out.put("status", text(row.get("status")));
        out.put("adjustmentType", text(row.get("adjustmentType")));
        out.put("source", text(row.get("source")));
        out.put("currentDepositTotal", toInt(row.get("currentDepositTotal")));
        out.put("proposedDepositTotal", toInt(row.get("proposedDepositTotal")));
        out.put("deltaAmount", toInt(row.get("deltaAmount")));
        out.put("proposedDate", text(row.get("proposedDate")));
        out.put("proposedTime", text(row.get("proposedTime")));
        out.put("proposedTableType", text(row.get("proposedTableType")));
        out.put("proposedPeople", toInt(row.get("proposedPeople")));
        out.put("message", text(row.get("message")));
        out.put("handlingNote", text(row.get("handlingNote")));
        out.put("handledByUserId", row.get("handledByUserId"));
        putIfPresent(out, "handledAt", row.get("handledAt"));
        out.put("appliedBookingUpdate", truthy(row.get("appliedBookingUpdate")));
        out.put("settlementStatus", textOrDefault(row.get("settlementStatus"), SETTLEMENT_PENDING));
        out.put("settlementProvider", text(row.get("settlementProvider")));
        out.put("settlementTransId", text(row.get("settlementTransId")));
        out.put("settlementAmount", toInt(row.get("settlementAmount")));
        putIfPresent(out, "settlementRequestedAt", row.get("settlementRequestedAt"));
        putIfPresent(out, "settlementCompletedAt", row.get("settlementCompletedAt"));
        out.put("settlementNote", text(row.get("settlementNote")));
        out.put("settlementRecordedByUserId", row.get("settlementRecordedByUserId"));
        putIfPresent(out, "refundEscalatedAt", row.get("refundEscalatedAt"));
        out.put("refundEscalationNote", text(row.get("refundEscalationNote")));
        out.put("refundEscalatedByUserId", row.get("refundEscalatedByUserId"));
        putIfPresent(out, "createdAt", row.get("createdAt"));
        putIfPresent(out, "updatedAt", row.get("updatedAt"));
        return out;
    }

    private Map<String, Object> payloadWithIdempotentReplay(Map<String, Object> row) {
        Map<String, Object> out = payload(row);
        out.put("idempotentReplay", true);
        return out;
    }

    private Map<String, Object> latestRefundOperationsDigestDispatch(Long shopId, int cooldownMinutes) {
        if (shopId == null) return Map.of();
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                """
                SELECT sent_at AS lastSentAt,
                       DATE_ADD(sent_at, INTERVAL ? MINUTE) AS nextEligibleAt,
                       CASE
                           WHEN sent_at >= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL ? MINUTE) THEN 1
                           ELSE 0
                       END AS cooldownActive
                FROM tb_merchant_notification_dispatch
                WHERE shop_id = ?
                  AND notification_type = ?
                  AND status = 'SENT'
                  AND sent_at IS NOT NULL
                ORDER BY sent_at DESC
                LIMIT 1
                """,
                cooldownMinutes,
                cooldownMinutes,
                shopId,
                NOTIFICATION_REFUND_OPERATIONS_DIGEST
        );
        return rows.isEmpty() ? Map.of() : rows.get(0);
    }

    private String normalizeStatus(String raw) {
        String status = raw == null || raw.isBlank() ? "OPEN" : raw.trim().toUpperCase(Locale.ROOT);
        return switch (status) {
            case "OPEN", "RESOLVED", "ALL" -> status;
            default -> "OPEN";
        };
    }

    private int normalizeStuckMinutes(int raw) {
        if (raw < 5) return 5;
        return Math.min(raw, 1440);
    }

    private int normalizeCooldownMinutes(int raw) {
        if (raw < 15) return 15;
        return Math.min(raw, 1440);
    }

    private String normalizeDispatchStatus(String raw) {
        String status = raw == null || raw.isBlank() ? DISPATCH_STATUS_SKIPPED : raw.trim().toUpperCase(Locale.ROOT);
        return DISPATCH_STATUS_SENT.equals(status) ? DISPATCH_STATUS_SENT : DISPATCH_STATUS_SKIPPED;
    }

    private String normalizeDispatchSource(String raw) {
        String source = raw == null || raw.isBlank() ? "MANUAL" : raw.trim().toUpperCase(Locale.ROOT);
        return switch (source) {
            case "MANUAL", "SCHEDULED" -> source;
            default -> source.length() > 30 ? source.substring(0, 30) : source;
        };
    }

    private List<Map<String, Object>> refundSummaryItems(Object raw) {
        if (!(raw instanceof List<?> list)) return List.of();
        List<Map<String, Object>> items = new ArrayList<>();
        for (Object value : list) {
            if (value instanceof Map<?, ?> map) {
                Map<String, Object> item = new LinkedHashMap<>();
                for (Map.Entry<?, ?> entry : map.entrySet()) {
                    if (entry.getKey() != null) {
                        item.put(entry.getKey().toString(), entry.getValue());
                    }
                }
                items.add(item);
            }
        }
        return items;
    }

    private String refundReportStatus(int pendingCount, int escalatedCount) {
        if (pendingCount > 0) return "ACTION_REQUIRED";
        if (escalatedCount > 0) return "FOLLOW_UP";
        return "CLEAR";
    }

    private String refundReportAction(int pendingFailedCount, int pendingStuckProcessingCount, int escalatedCount) {
        if (pendingFailedCount > 0) return "ESCALATE_FAILED_REFUNDS";
        if (pendingStuckProcessingCount > 0) return "ESCALATE_STUCK_REFUNDS";
        if (escalatedCount > 0) return "FOLLOW_UP_ESCALATED_REFUNDS";
        return "NO_REFUND_ACTION";
    }

    private String refundReportHeadline(int pendingCount, int escalatedCount) {
        if (pendingCount > 0) {
            return String.format(Locale.ROOT, "%d 件退款需要升級處理", pendingCount);
        }
        if (escalatedCount > 0) {
            return String.format(Locale.ROOT, "%d 件退款已升級，等待後續追蹤", escalatedCount);
        }
        return "退款營運正常";
    }

    private String oldestTimestamp(List<Map<String, Object>> items, String key) {
        String oldest = "";
        for (Map<String, Object> item : items) {
            String value = text(item.get(key));
            if (!value.isBlank() && (oldest.isBlank() || value.compareTo(oldest) < 0)) {
                oldest = value;
            }
        }
        return oldest;
    }

    private String normalizeSource(String raw) {
        String source = raw == null || raw.isBlank() ? "CUSTOMER_RESCHEDULE" : raw.trim().toUpperCase(Locale.ROOT);
        return source.length() > 40 ? source.substring(0, 40) : source;
    }

    private String normalizeTableType(String tableType) {
        if (tableType == null || tableType.isBlank()) return "normal";
        return tableType.trim();
    }

    private String normalizeProvider(String raw) {
        String provider = raw == null || raw.isBlank() ? "TAPPAY" : raw.trim().toUpperCase(Locale.ROOT);
        return switch (provider) {
            case "TAPPAY", "PSP_BACKOFFICE", "MANUAL" -> provider;
            default -> provider.length() > 30 ? provider.substring(0, 30) : provider;
        };
    }

    private String normalizeRefundReconciliationStatus(String raw) {
        String status = raw == null || raw.isBlank()
                ? SETTLEMENT_COMPLETED
                : raw.trim().toUpperCase(Locale.ROOT);
        return switch (status) {
            case SETTLEMENT_COMPLETED, SETTLEMENT_FAILED -> status;
            default -> throw new IllegalArgumentException("退款對帳狀態僅支援 COMPLETED/FAILED");
        };
    }

    private String normalizeRefundEventKey(String raw) {
        String eventKey = trimToNull(raw);
        if (eventKey == null) return null;
        return eventKey.length() > 120 ? eventKey.substring(0, 120) : eventKey;
    }

    private String bookingStatusName(Object raw) {
        return switch (toInt(raw)) {
            case BookingHoldService.STATUS_PENDING_PAYMENT -> "PENDING_PAYMENT";
            case BookingHoldService.STATUS_PAID -> "PAID";
            case BookingHoldService.STATUS_CONFIRMED -> "CONFIRMED";
            case BookingHoldService.STATUS_CANCELED -> "CANCELED";
            case BookingHoldService.STATUS_EXPIRED -> "EXPIRED";
            default -> "UNKNOWN";
        };
    }

    private LocalDate parseDate(String raw) {
        try {
            return LocalDate.parse(raw);
        } catch (DateTimeParseException ex) {
            return null;
        }
    }

    private int toInt(Object value) {
        if (value instanceof Number number) return number.intValue();
        if (value == null) return 0;
        try {
            return Integer.parseInt(value.toString().trim());
        } catch (NumberFormatException ex) {
            return 0;
        }
    }

    private Long toLong(Object value) {
        if (value instanceof Number number) return number.longValue();
        if (value == null) return null;
        try {
            return Long.parseLong(value.toString().trim());
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private boolean truthy(Object value) {
        if (value instanceof Boolean bool) return bool;
        if (value instanceof Number number) return number.intValue() != 0;
        return value != null && Boolean.parseBoolean(value.toString());
    }

    private String trimToNull(String value) {
        if (value == null || value.isBlank()) return null;
        return value.trim();
    }

    private String text(Object value) {
        return value == null ? "" : value.toString();
    }

    private String textOrDefault(Object value, String fallback) {
        String text = text(value);
        return text.isBlank() ? fallback : text;
    }

    private String truncate(String value, int maxLength) {
        String normalized = trimToNull(value);
        if (normalized == null) return null;
        return normalized.length() > maxLength ? normalized.substring(0, maxLength) : normalized;
    }

    private String withoutLock(String whereClause) {
        String clause = whereClause == null ? "" : whereClause.trim();
        if (clause.toUpperCase(Locale.ROOT).endsWith("FOR UPDATE")) {
            return clause.substring(0, clause.length() - "FOR UPDATE".length()).trim();
        }
        return clause;
    }

    private String lockClause(String whereClause) {
        String clause = whereClause == null ? "" : whereClause.trim();
        return clause.toUpperCase(Locale.ROOT).endsWith("FOR UPDATE") ? "FOR UPDATE" : "";
    }

    private void putIfPresent(Map<String, Object> out, String key, Object value) {
        if (value != null) out.put(key, value.toString());
    }
}
