package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.service.AvailabilityNotificationService;
import com.bytebites.service.BookingDepositAdjustmentService;
import com.bytebites.service.BookingLineNotificationService;
import com.bytebites.service.LineNotificationClient;
import com.bytebites.service.jpa.UserJpaService;
import com.bytebites.utils.UserHolder;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@RequiredArgsConstructor
@RestController
@RequestMapping({"/merchant", "/api/merchant"})
public class MerchantController {
    private static final ZoneId BUSINESS_ZONE = ZoneId.of("Asia/Taipei");

    private static final List<String> DEFAULT_TIMES = List.of(
            "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"
    );

    private final JdbcTemplate jdbcTemplate;
    private final AvailabilityNotificationService availabilityNotificationService;
    private final BookingLineNotificationService bookingLineNotificationService;
    private final BookingDepositAdjustmentService bookingDepositAdjustmentService;
    private final UserJpaService userJpaService;
    private final LineNotificationClient lineNotificationClient;

    @GetMapping("/shops")
    public Result shops() {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");

        List<Map<String, Object>> shops = jdbcTemplate.queryForList(
                """
                SELECT s.id, s.name, s.district, s.address, ms.role
                FROM tb_merchant_shop ms
                JOIN tb_shop s ON s.id = ms.shop_id
                WHERE ms.user_id = ?
                ORDER BY s.name
                """,
                userId
        );
        return Result.ok(shops);
    }

    @GetMapping("/shops/{shopId}/slots")
    @Transactional
    public Result slots(
            @PathVariable Long shopId,
            @RequestParam String date,
            @RequestParam(defaultValue = "normal") String tableType
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");

        LocalDate bookingDate = parseDate(date);
        if (bookingDate == null) return Result.fail("date 格式需為 YYYY-MM-DD");
        if (!bookingDate.isAfter(today())) return Result.fail("僅可管理明天或之後的時段");
        if (!isSupportedTableType(tableType)) return Result.fail("tableType 僅支援 normal/bar/private");

        for (String time : DEFAULT_TIMES) {
            ensureSlot(shopId, bookingDate, time, tableType);
        }

        List<Map<String, Object>> slots = jdbcTemplate.queryForList(
                """
                SELECT booking_time AS time,
                       table_type AS tableType,
                       capacity,
                       booked_count AS bookedCount,
                       GREATEST(capacity - booked_count, 0) AS remaining
                FROM tb_booking_slot_inventory
                WHERE shop_id = ? AND booking_date = ? AND table_type = ?
                ORDER BY booking_time
                """,
                shopId,
                bookingDate,
                tableType
        );

        return Result.ok(Map.of(
                "shopId", shopId,
                "date", bookingDate.toString(),
                "tableType", tableType,
                "slots", slots
        ));
    }

    @PutMapping("/shops/{shopId}/slots")
    @Transactional
    public Result updateSlots(@PathVariable Long shopId, @RequestBody Map<String, Object> body) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");

        Object dateValue = body.get("date");
        if (dateValue == null) return Result.fail("date 必填");
        LocalDate bookingDate = parseDate(dateValue.toString());
        if (bookingDate == null) return Result.fail("date 格式需為 YYYY-MM-DD");
        if (!bookingDate.isAfter(today())) return Result.fail("僅可管理明天或之後的時段");

        String tableType = String.valueOf(body.getOrDefault("tableType", "normal"));
        if (!isSupportedTableType(tableType)) return Result.fail("tableType 僅支援 normal/bar/private");

        Object slotsValue = body.get("slots");
        if (!(slotsValue instanceof List<?> slots) || slots.isEmpty()) {
            return Result.fail("slots 必須是非空陣列");
        }

        for (Object rawSlot : slots) {
            if (!(rawSlot instanceof Map<?, ?> slot)) {
                return Result.fail("slot 格式錯誤");
            }
            Object timeValue = slot.get("time");
            Object capacityValue = slot.get("capacity");
            if (timeValue == null || capacityValue == null) {
                return Result.fail("slot time/capacity 必填");
            }
            String time = normalizeTime(timeValue.toString());
            Integer capacity = parseCapacity(capacityValue);
            if (time == null) return Result.fail("slot time 格式需為 HH:mm");
            if (capacity == null || capacity < 0 || capacity > 80) {
                return Result.fail("capacity 需介於 0-80");
            }

            ensureSlot(shopId, bookingDate, time, tableType);
            Map<String, Object> current = lockSlot(shopId, bookingDate, time, tableType);
            int bookedCount = ((Number) current.get("booked_count")).intValue();
            if (capacity < bookedCount) {
                return Result.fail(time + " 已有 " + bookedCount + " 人訂位，容量不可低於已訂人數");
            }
            jdbcTemplate.update(
                    """
                    UPDATE tb_booking_slot_inventory
                    SET capacity = ?
                    WHERE shop_id = ? AND booking_date = ? AND booking_time = ? AND table_type = ?
                    """,
                    capacity,
                    shopId,
                    bookingDate,
                    time,
                    tableType
            );
            availabilityNotificationService.triggerIfAvailable(shopId, bookingDate, time, tableType);
        }

        return slots(shopId, bookingDate.toString(), tableType);
    }

    @GetMapping("/shops/{shopId}/incidents")
    public Result incidents(
            @PathVariable Long shopId,
            @RequestParam(defaultValue = "OPEN") String status
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");

        String normalizedStatus = normalizeIncidentStatus(status);
        if (normalizedStatus == null) return Result.fail("status 僅支援 OPEN/RESOLVED/ALL");

        List<Map<String, Object>> rows;
        if ("ALL".equals(normalizedStatus)) {
            rows = jdbcTemplate.queryForList(
                    merchantIncidentSql("""
                            WHERE i.shop_id = ?
                            """),
                    shopId
            );
        } else {
            rows = jdbcTemplate.queryForList(
                    merchantIncidentSql("""
                            WHERE i.shop_id = ?
                              AND i.status = ?
                            """),
                    shopId,
                    normalizedStatus
            );
        }

        return Result.ok(Map.of(
                "shopId", shopId,
                "status", normalizedStatus,
                "incidents", rows.stream().map(this::merchantIncidentPayload).toList()
        ));
    }

    @PostMapping("/shops/{shopId}/incidents/{incidentId}/resolve")
    public Result resolveIncident(@PathVariable Long shopId, @PathVariable Long incidentId) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");
        if (incidentId == null) return Result.fail("incidentId 必填");

        int updated = jdbcTemplate.update(
                """
                UPDATE tb_booking_incident
                SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP
                WHERE id = ? AND shop_id = ? AND status = 'OPEN'
                """,
                incidentId,
                shopId
        );
        if (updated == 0) return Result.fail("救場通知不存在或已處理");

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                merchantIncidentSql("""
                        WHERE i.id = ?
                          AND i.shop_id = ?
                        """),
                incidentId,
                shopId
        );
        return rows.stream().findFirst()
                .map(row -> Result.ok(merchantIncidentPayload(row)))
                .orElseGet(() -> Result.ok(Map.of("id", incidentId, "status", "RESOLVED")));
    }

    @PostMapping("/shops/{shopId}/incidents/{incidentId}/proposal")
    public Result proposeIncidentSlot(
            @PathVariable Long shopId,
            @PathVariable Long incidentId,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");
        if (incidentId == null) return Result.fail("incidentId 必填");

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                merchantIncidentSql("""
                        WHERE i.id = ?
                          AND i.shop_id = ?
                          AND i.status = 'OPEN'
                        """),
                incidentId,
                shopId
        );
        if (rows.isEmpty()) return Result.fail("救場通知不存在或已處理");
        Map<String, Object> incident = rows.get(0);
        Map<String, Object> requestBody = body != null ? body : Map.of();

        String proposedTime = normalizeTime(text(requestBody.get("time")));
        if (proposedTime == null) return Result.fail("time 格式需為 HH:mm");
        LocalDate bookingDate = parseDate(text(incident.get("bookingDate")));
        LocalDate proposedDate = parseDate(text(requestBody.get("date")));
        if (proposedDate == null) proposedDate = bookingDate;
        String proposedTableType = normalizeTableType(textOrDefault(requestBody.get("tableType"), text(incident.get("tableType"))));
        int proposedPeople = toInt(requestBody.get("people"));
        if (proposedPeople <= 0) proposedPeople = toInt(incident.get("people"));

        if (bookingDate == null || !bookingDate.equals(proposedDate)) {
            return Result.fail("目前僅支援同日替代時段提案");
        }
        if (!proposedTableType.equals(normalizeTableType(text(incident.get("tableType"))))
                || proposedPeople != toInt(incident.get("people"))) {
            return Result.fail("目前僅支援同桌型、同人數替代時段提案");
        }
        if (!isSuggestedSlot(incident, proposedTime)) {
            return Result.fail("請選擇目前仍有足夠座位的替代時段");
        }

        String message = textOrDefault(
                requestBody.get("message"),
                "店家建議改到 " + proposedDate + " " + proposedTime + "，請確認是否接受。"
        );
        int updated = jdbcTemplate.update(
                """
                UPDATE tb_booking_incident
                SET proposal_status = 'PENDING',
                    proposed_date = ?,
                    proposed_time = ?,
                    proposed_table_type = ?,
                    proposed_people = ?,
                    proposal_message = ?,
                    proposed_at = CURRENT_TIMESTAMP,
                    proposal_expires_at = DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 30 MINUTE),
                    proposal_accepted_at = NULL,
                    proposal_declined_at = NULL
                WHERE id = ? AND shop_id = ? AND status = 'OPEN'
                """,
                proposedDate,
                proposedTime,
                proposedTableType,
                proposedPeople,
                message,
                incidentId,
                shopId
        );
        if (updated == 0) return Result.fail("替代時段提案建立失敗");

        List<Map<String, Object>> refreshedRows = jdbcTemplate.queryForList(
                merchantIncidentSql("""
                        WHERE i.id = ?
                          AND i.shop_id = ?
                        """),
                incidentId,
                shopId
        );
        return refreshedRows.stream().findFirst()
                .map(row -> {
                    Map<String, Object> payload = merchantIncidentPayload(row);
                    bookingLineNotificationService.pushBookingIncidentProposal(payload);
                    return Result.ok(payload);
                })
                .orElseGet(() -> Result.ok(Map.of("id", incidentId, "proposalStatus", "PENDING")));
    }

    @GetMapping("/shops/{shopId}/deposit-adjustments")
    public Result depositAdjustments(
            @PathVariable Long shopId,
            @RequestParam(defaultValue = "OPEN") String status
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");

        String normalizedStatus = normalizeAdjustmentStatus(status);
        if (normalizedStatus == null) return Result.fail("status 僅支援 OPEN/RESOLVED/ALL");
        return Result.ok(Map.of(
                "shopId", shopId,
                "status", normalizedStatus,
                "adjustments", bookingDepositAdjustmentService.listForMerchantShop(shopId, normalizedStatus)
        ));
    }

    @GetMapping("/shops/{shopId}/deposit-adjustments/refund-sla")
    public Result refundSlaSummary(
            @PathVariable Long shopId,
            @RequestParam(defaultValue = "30") int stuckMinutes
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");

        return Result.ok(bookingDepositAdjustmentService.refundSlaSummaryForMerchantShop(shopId, stuckMinutes));
    }

    @GetMapping("/shops/{shopId}/deposit-adjustments/refund-report")
    public Result refundOperationsReport(
            @PathVariable Long shopId,
            @RequestParam(defaultValue = "30") int stuckMinutes
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");

        return Result.ok(bookingDepositAdjustmentService.refundOperationsReportForMerchantShop(shopId, stuckMinutes));
    }

    @PostMapping("/shops/{shopId}/deposit-adjustments/refund-report/notify")
    public Result notifyRefundOperationsReport(
            @PathVariable Long shopId,
            @RequestParam(defaultValue = "30") int stuckMinutes
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");

        return refundOperationsDigestNotification(shopId, userId, stuckMinutes, 120, "MANUAL", false);
    }

    @GetMapping("/shops/{shopId}/deposit-adjustments/refund-report/notification-policy")
    public Result refundOperationsNotificationPolicy(
            @PathVariable Long shopId,
            @RequestParam(defaultValue = "30") int stuckMinutes,
            @RequestParam(defaultValue = "120") int cooldownMinutes
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");

        Map<String, Object> report = refundOperationsReportWithShopName(shopId, stuckMinutes);
        return Result.ok(bookingDepositAdjustmentService.refundOperationsNotificationPolicyForReport(
                report,
                cooldownMinutes
        ));
    }

    @PostMapping("/shops/{shopId}/deposit-adjustments/refund-report/dispatch-due")
    public Result dispatchRefundOperationsReportIfDue(
            @PathVariable Long shopId,
            @RequestParam(defaultValue = "30") int stuckMinutes,
            @RequestParam(defaultValue = "120") int cooldownMinutes
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");

        return refundOperationsDigestNotification(shopId, userId, stuckMinutes, cooldownMinutes, "SCHEDULED", true);
    }

    private Result refundOperationsDigestNotification(
            Long shopId,
            Long userId,
            int stuckMinutes,
            int cooldownMinutes,
            String dispatchSource,
            boolean enforcePolicy
    ) {
        Map<String, Object> report = refundOperationsReportWithShopName(shopId, stuckMinutes);
        Map<String, Object> policy = bookingDepositAdjustmentService.refundOperationsNotificationPolicyForReport(
                report,
                cooldownMinutes
        );
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("shopId", shopId);
        result.put("report", report);
        result.put("policy", policy);

        if (enforcePolicy && !truthy(policy.get("shouldNotify"))) {
            result.put("lineNotification", "SKIPPED");
            result.put("skipped", true);
            result.put("reason", textOrDefault(policy.get("reason"), "POLICY_SKIPPED"));
            return Result.ok(result);
        }

        if (toInt(report.get("totalAttentionCount")) <= 0) {
            result.put("lineNotification", "SKIPPED");
            result.put("skipped", true);
            result.put("reason", "NO_REFUND_ATTENTION");
            if (!enforcePolicy) {
                bookingDepositAdjustmentService.recordRefundOperationsNotificationDispatch(
                        shopId,
                        dispatchSource,
                        "SKIPPED",
                        "NO_REFUND_ATTENTION",
                        report,
                        cooldownMinutes,
                        null
                );
            }
            return Result.ok(result);
        }

        return userJpaService.findLineNotificationUserId(userId)
                .map(lineUserId -> {
                    lineNotificationClient.pushRefundOperationsDigest(lineUserId, report);
                    bookingDepositAdjustmentService.recordRefundOperationsNotificationDispatch(
                            shopId,
                            dispatchSource,
                            "SENT",
                            enforcePolicy ? textOrDefault(policy.get("reason"), "ACTION_REQUIRED") : "MANUAL",
                            report,
                            cooldownMinutes,
                            lineUserId
                    );
                    result.put("lineNotification", "SENT");
                    result.put("skipped", false);
                    return Result.ok(result);
                })
                .orElseGet(() -> {
                    bookingDepositAdjustmentService.recordRefundOperationsNotificationDispatch(
                            shopId,
                            dispatchSource,
                            "SKIPPED",
                            "NO_LINKED_LINE_USER",
                            report,
                            cooldownMinutes,
                            null
                    );
                    result.put("lineNotification", "SKIPPED");
                    result.put("skipped", true);
                    result.put("reason", "NO_LINKED_LINE_USER");
                    return Result.ok(result);
                });
    }

    private Map<String, Object> refundOperationsReportWithShopName(Long shopId, int stuckMinutes) {
        Map<String, Object> report = new LinkedHashMap<>(
                bookingDepositAdjustmentService.refundOperationsReportForMerchantShop(shopId, stuckMinutes)
        );
        report.putIfAbsent("shopId", shopId);
        report.putIfAbsent("shopName", refundReportShopName(report, shopId));
        return report;
    }

    @PostMapping("/shops/{shopId}/deposit-adjustments/{adjustmentId}/resolve")
    public Result resolveDepositAdjustment(
            @PathVariable Long shopId,
            @PathVariable Long adjustmentId,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");
        if (adjustmentId == null) return Result.fail("adjustmentId 必填");

        try {
            Map<String, Object> requestBody = body != null ? body : Map.of();
            String handlingNote = text(requestBody.get("handlingNote")).trim();
            return Result.ok(bookingDepositAdjustmentService.resolveAndApplyForMerchantShop(
                    shopId,
                    adjustmentId,
                    userId,
                    handlingNote
            ));
        } catch (IllegalArgumentException | IllegalStateException ex) {
            return Result.fail(ex.getMessage());
        }
    }

    @PostMapping("/shops/{shopId}/deposit-adjustments/{adjustmentId}/settlement")
    public Result recordDepositAdjustmentSettlement(
            @PathVariable Long shopId,
            @PathVariable Long adjustmentId,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");
        if (adjustmentId == null) return Result.fail("adjustmentId 必填");

        try {
            Map<String, Object> requestBody = body != null ? body : Map.of();
            return Result.ok(bookingDepositAdjustmentService.recordSettlementForMerchantShop(
                    shopId,
                    adjustmentId,
                    userId,
                    text(requestBody.getOrDefault("provider", "TAPPAY")),
                    text(requestBody.get("settlementTransId")),
                    text(requestBody.get("settlementNote"))
            ));
        } catch (IllegalArgumentException | IllegalStateException ex) {
            return Result.fail(ex.getMessage());
        }
    }

    @PostMapping("/shops/{shopId}/deposit-adjustments/{adjustmentId}/refund/request")
    public Result requestDepositAdjustmentRefund(
            @PathVariable Long shopId,
            @PathVariable Long adjustmentId,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");
        if (adjustmentId == null) return Result.fail("adjustmentId 必填");

        try {
            Map<String, Object> requestBody = body != null ? body : Map.of();
            return Result.ok(bookingDepositAdjustmentService.requestRefundForMerchantShop(
                    shopId,
                    adjustmentId,
                    userId,
                    text(requestBody.get("settlementNote"))
            ));
        } catch (IllegalArgumentException | IllegalStateException ex) {
            return Result.fail(ex.getMessage());
        }
    }

    @PostMapping("/shops/{shopId}/deposit-adjustments/{adjustmentId}/refund/escalate")
    public Result escalateDepositAdjustmentRefund(
            @PathVariable Long shopId,
            @PathVariable Long adjustmentId,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        Long userId = requireUserId();
        if (userId == null) return Result.fail("請先登入店家帳號");
        if (!ownsShop(userId, shopId)) return Result.fail("沒有此店家的管理權限");
        if (adjustmentId == null) return Result.fail("adjustmentId 必填");

        try {
            Map<String, Object> requestBody = body != null ? body : Map.of();
            return Result.ok(bookingDepositAdjustmentService.escalateRefundForMerchantShop(
                    shopId,
                    adjustmentId,
                    userId,
                    text(requestBody.get("escalationNote"))
            ));
        } catch (IllegalArgumentException | IllegalStateException ex) {
            return Result.fail(ex.getMessage());
        }
    }

    private Long requireUserId() {
        var user = UserHolder.getUser();
        if (user != null && user.getId() != null) {
            return user.getId();
        }
        return null;
    }

    private LocalDate today() {
        return LocalDate.now(BUSINESS_ZONE);
    }

    private boolean ownsShop(Long userId, Long shopId) {
        Integer count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM tb_merchant_shop
                WHERE user_id = ? AND shop_id = ?
                """,
                Integer.class,
                userId,
                shopId
        );
        return count != null && count > 0;
    }

    private String merchantIncidentSql(String whereClause) {
        return """
                SELECT i.id, i.booking_code AS bookingCode, i.user_id AS userId, i.shop_id AS shopId,
                       s.name AS shopName, b.booking_date AS bookingDate, b.booking_time AS bookingTime,
                       b.people, b.table_type AS tableType, b.status AS bookingStatus,
                       i.incident_type AS incidentType, i.status, i.delay_minutes AS delayMinutes,
                       i.original_time AS originalTime, i.adjusted_time AS adjustedTime,
                       i.title, i.customer_message AS customerMessage, i.action_label AS actionLabel,
                       i.source, i.proposal_status AS proposalStatus, i.proposed_date AS proposedDate,
                       i.proposed_time AS proposedTime, i.proposed_table_type AS proposedTableType,
                       i.proposed_people AS proposedPeople, i.proposal_message AS proposalMessage,
                       i.proposed_at AS proposedAt, i.proposal_expires_at AS proposalExpiresAt,
                       i.proposal_accepted_at AS proposalAcceptedAt, i.proposal_declined_at AS proposalDeclinedAt,
                       i.created_at AS createdAt, i.updated_at AS updatedAt,
                       i.resolved_at AS resolvedAt
                FROM tb_booking_incident i
                JOIN tb_booking b ON b.booking_code = i.booking_code
                JOIN tb_shop s ON s.id = i.shop_id
                %s
                ORDER BY i.created_at DESC
                LIMIT 30
                """.formatted(whereClause);
    }

    private Map<String, Object> merchantIncidentPayload(Map<String, Object> row) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", row.get("id"));
        out.put("bookingCode", text(row.get("bookingCode")));
        out.put("userId", row.get("userId"));
        out.put("shopId", row.get("shopId"));
        out.put("shopName", text(row.get("shopName")));
        out.put("bookingDate", text(row.get("bookingDate")));
        out.put("bookingTime", text(row.get("bookingTime")));
        out.put("people", toInt(row.get("people")));
        out.put("tableType", text(row.get("tableType")));
        out.put("bookingStatus", bookingStatusName(row.get("bookingStatus")));
        out.put("incidentType", text(row.get("incidentType")));
        out.put("status", text(row.get("status")));
        out.put("delayMinutes", toInt(row.get("delayMinutes")));
        out.put("originalTime", text(row.get("originalTime")));
        out.put("adjustedTime", text(row.get("adjustedTime")));
        out.put("title", text(row.get("title")));
        out.put("customerMessage", text(row.get("customerMessage")));
        out.put("actionLabel", text(row.get("actionLabel")));
        out.put("source", text(row.get("source")));
        String proposalStatus = effectiveProposalStatus(row);
        out.put(
                "alternativeSlots",
                "OPEN".equals(text(row.get("status"))) && !"PENDING".equals(proposalStatus)
                        ? alternativeSlotsFor(row)
                        : List.of()
        );
        Map<String, Object> proposedChange = proposedChangePayload(row);
        if (!proposedChange.isEmpty()) out.put("proposedChange", proposedChange);
        putIfPresent(out, "createdAt", row.get("createdAt"));
        putIfPresent(out, "updatedAt", row.get("updatedAt"));
        putIfPresent(out, "resolvedAt", row.get("resolvedAt"));
        return out;
    }

    private boolean isSuggestedSlot(Map<String, Object> incidentRow, String proposedTime) {
        return alternativeSlotsFor(incidentRow).stream()
                .anyMatch(slot -> proposedTime.equals(text(slot.get("time"))));
    }

    private Map<String, Object> proposedChangePayload(Map<String, Object> row) {
        String proposalStatus = effectiveProposalStatus(row);
        if (proposalStatus.isBlank()) return Map.of();
        Map<String, Object> proposal = new LinkedHashMap<>();
        proposal.put("status", proposalStatus);
        proposal.put("date", text(row.get("proposedDate")));
        proposal.put("time", text(row.get("proposedTime")));
        proposal.put("tableType", text(row.get("proposedTableType")));
        proposal.put("people", toInt(row.get("proposedPeople")));
        proposal.put("message", text(row.get("proposalMessage")));
        putIfPresent(proposal, "proposedAt", row.get("proposedAt"));
        putIfPresent(proposal, "expiresAt", row.get("proposalExpiresAt"));
        putIfPresent(proposal, "acceptedAt", row.get("proposalAcceptedAt"));
        putIfPresent(proposal, "declinedAt", row.get("proposalDeclinedAt"));
        return proposal;
    }

    private String effectiveProposalStatus(Map<String, Object> row) {
        String proposalStatus = text(row.get("proposalStatus"));
        if ("PENDING".equals(proposalStatus) && isPast(row.get("proposalExpiresAt"))) {
            return "EXPIRED";
        }
        return proposalStatus;
    }

    private boolean isPast(Object value) {
        LocalDateTime dateTime = toLocalDateTime(value);
        return dateTime != null && !dateTime.isAfter(LocalDateTime.now(BUSINESS_ZONE));
    }

    private LocalDateTime toLocalDateTime(Object value) {
        if (value == null) return null;
        if (value instanceof LocalDateTime dateTime) return dateTime;
        if (value instanceof java.sql.Timestamp timestamp) return timestamp.toLocalDateTime();
        String raw = text(value);
        if (raw.isBlank()) return null;
        try {
            return LocalDateTime.parse(raw.replace(" ", "T"));
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }

    private List<Map<String, Object>> alternativeSlotsFor(Map<String, Object> incidentRow) {
        Long shopId = toLong(incidentRow.get("shopId"));
        LocalDate bookingDate = parseDate(text(incidentRow.get("bookingDate")));
        String tableType = normalizeTableType(text(incidentRow.get("tableType")));
        LocalTime baseline = parseTime(text(incidentRow.get("adjustedTime")));
        LocalTime originalTime = parseTime(text(incidentRow.get("bookingTime")));
        int people = toInt(incidentRow.get("people"));
        if (baseline == null) baseline = originalTime;
        if (shopId == null || bookingDate == null || baseline == null || people <= 0) return List.of();

        List<Map<String, Object>> existingRows = jdbcTemplate.queryForList(
                """
                SELECT booking_time AS time,
                       table_type AS tableType,
                       capacity,
                       booked_count AS bookedCount,
                       GREATEST(capacity - booked_count, 0) AS remaining
                FROM tb_booking_slot_inventory
                WHERE shop_id = ? AND booking_date = ? AND table_type = ?
                """,
                shopId,
                bookingDate,
                tableType
        );
        Map<String, Map<String, Object>> existingByTime = new LinkedHashMap<>();
        for (Map<String, Object> row : existingRows) {
            String time = normalizeTime(text(row.get("time")));
            if (time != null) existingByTime.put(time, row);
        }

        List<Map<String, Object>> suggestions = new ArrayList<>();
        for (String rawTime : DEFAULT_TIMES) {
            String time = normalizeTime(rawTime);
            if (time == null) continue;
            LocalTime candidateTime = parseTime(time);
            if (candidateTime == null || candidateTime.isBefore(baseline)) continue;
            if (originalTime != null && candidateTime.equals(originalTime)) continue;

            Map<String, Object> inventoryRow = existingByTime.get(time);
            int capacity = inventoryRow != null ? toInt(inventoryRow.get("capacity")) : defaultSlotCapacity(tableType);
            int bookedCount = inventoryRow != null ? toInt(inventoryRow.get("bookedCount")) : 0;
            int remaining = Math.max(capacity - bookedCount, 0);
            if (remaining < people) continue;

            Map<String, Object> slot = new LinkedHashMap<>();
            slot.put("time", time);
            slot.put("tableType", tableType);
            slot.put("capacity", capacity);
            slot.put("bookedCount", bookedCount);
            slot.put("remaining", remaining);
            slot.put("label", "同日 " + time);
            suggestions.add(slot);
            if (suggestions.size() >= 3) break;
        }
        return suggestions;
    }

    private String normalizeIncidentStatus(String raw) {
        String status = raw == null || raw.isBlank()
                ? "OPEN"
                : raw.trim().toUpperCase(Locale.ROOT);
        return switch (status) {
            case "OPEN", "RESOLVED", "ALL" -> status;
            default -> null;
        };
    }

    private String normalizeAdjustmentStatus(String raw) {
        String status = raw == null || raw.isBlank()
                ? "OPEN"
                : raw.trim().toUpperCase(Locale.ROOT);
        return switch (status) {
            case "OPEN", "RESOLVED", "ALL" -> status;
            default -> null;
        };
    }

    private String bookingStatusName(Object raw) {
        return switch (toInt(raw)) {
            case 1 -> "PENDING_PAYMENT";
            case 2 -> "PAID";
            case 3 -> "CONFIRMED";
            case 4 -> "CANCELED";
            case 5 -> "EXPIRED";
            default -> "UNKNOWN";
        };
    }

    private String refundReportShopName(Map<String, Object> report, Long shopId) {
        String direct = text(report.get("shopName")).trim();
        if (!direct.isBlank()) return direct;
        for (String key : List.of("pendingEscalationItems", "escalatedItems")) {
            Object raw = report.get(key);
            if (raw instanceof List<?> items) {
                for (Object item : items) {
                    if (item instanceof Map<?, ?> map) {
                        String shopName = text(map.get("shopName")).trim();
                        if (!shopName.isBlank()) return shopName;
                    }
                }
            }
        }
        return "店家 " + shopId;
    }

    private void putIfPresent(Map<String, Object> out, String key, Object value) {
        if (value != null) out.put(key, value.toString());
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

    private String text(Object value) {
        return value == null ? "" : value.toString();
    }

    private String textOrDefault(Object value, String fallback) {
        String text = text(value).trim();
        return text.isBlank() ? fallback : text;
    }

    private void ensureSlot(Long shopId, LocalDate bookingDate, String time, String tableType) {
        jdbcTemplate.update(
                """
                INSERT IGNORE INTO tb_booking_slot_inventory
                    (shop_id, booking_date, booking_time, table_type, capacity, booked_count)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                shopId,
                bookingDate,
                time,
                tableType,
                defaultSlotCapacity(tableType)
        );
    }

    private Map<String, Object> lockSlot(Long shopId, LocalDate bookingDate, String time, String tableType) {
        return jdbcTemplate.queryForMap(
                """
                SELECT capacity, booked_count
                FROM tb_booking_slot_inventory
                WHERE shop_id = ? AND booking_date = ? AND booking_time = ? AND table_type = ?
                FOR UPDATE
                """,
                shopId,
                bookingDate,
                time,
                tableType
        );
    }

    private LocalDate parseDate(String raw) {
        try {
            return LocalDate.parse(raw);
        } catch (DateTimeParseException ex) {
            return null;
        }
    }

    private String normalizeTime(String raw) {
        if (raw == null || !raw.matches("^\\d{1,2}:\\d{2}$")) return null;
        String[] parts = raw.split(":");
        int hour = Integer.parseInt(parts[0]);
        int minute = Integer.parseInt(parts[1]);
        if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
        return "%02d:%02d".formatted(hour, minute);
    }

    private LocalTime parseTime(String raw) {
        String normalized = normalizeTime(raw);
        if (normalized == null) return null;
        try {
            return LocalTime.parse(normalized);
        } catch (DateTimeParseException ex) {
            return null;
        }
    }

    private String normalizeTableType(String tableType) {
        if (tableType == null || tableType.isBlank()) return "normal";
        return isSupportedTableType(tableType) ? tableType : "normal";
    }

    private Integer parseCapacity(Object value) {
        try {
            return Integer.parseInt(value.toString());
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private boolean isSupportedTableType(String tableType) {
        return tableType.equals("normal") || tableType.equals("bar") || tableType.equals("private");
    }

    private int defaultSlotCapacity(String tableType) {
        return switch (tableType) {
            case "private" -> 4;
            case "bar" -> 6;
            default -> 8;
        };
    }
}
