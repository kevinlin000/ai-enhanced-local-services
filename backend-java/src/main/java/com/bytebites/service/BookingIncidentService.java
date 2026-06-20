package com.bytebites.service;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.Shop;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.utils.UserHolder;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class BookingIncidentService {
    private static final ZoneId BUSINESS_ZONE = ZoneId.of("Asia/Taipei");
    private static final int DEFAULT_DELAY_MINUTES = 15;
    private static final int MAX_DELAY_MINUTES = 45;

    private final JdbcTemplate jdbcTemplate;
    private final BookingJpaRepository bookingRepo;
    private final IShopService shopService;
    private final BookingLineNotificationService bookingLineNotificationService;
    private final LineActionTokenService lineActionTokenService;

    public Result createIncident(String bookingCode, Map<String, Object> body) {
        BookingJpa booking = findBookingOrNull(bookingCode);
        if (booking == null) return Result.fail("訂位不存在");
        if (!canAccessBooking(booking, body)) return Result.fail("無權建立此訂位的救場通知");
        if (booking.getStatus() == BookingHoldService.STATUS_CANCELED
                || booking.getStatus() == BookingHoldService.STATUS_EXPIRED) {
            return Result.fail("已取消或逾期訂位無法建立救場通知");
        }

        IncidentDraft draft = draftFor(booking, body != null ? body : Map.of());
        if (!draft.valid()) return Result.fail(draft.error());

        Shop shop = booking.getShopId() == null ? null : shopService.getById(booking.getShopId());
        String shopName = shop != null ? shop.getName() : "店家 " + booking.getShopId();

        jdbcTemplate.update(
                """
                INSERT INTO tb_booking_incident
                    (booking_code, user_id, shop_id, incident_type, status, delay_minutes,
                     original_time, adjusted_time, title, customer_message, action_label, source)
                VALUES (?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?)
                """,
                booking.getBookingCode(),
                booking.getUserId(),
                booking.getShopId(),
                draft.incidentType(),
                draft.delayMinutes(),
                booking.getBookingTime(),
                draft.adjustedTime(),
                draft.title(),
                draft.customerMessage(),
                draft.actionLabel(),
                draft.source()
        );

        Map<String, Object> incident = latestIncidentForBookingCode(booking.getBookingCode()).orElseGet(() ->
                incidentPayload(
                        null,
                        booking,
                        shopName,
                        draft.incidentType(),
                        "OPEN",
                        draft.delayMinutes(),
                        booking.getBookingTime(),
                        draft.adjustedTime(),
                        draft.title(),
                        draft.customerMessage(),
                        draft.actionLabel(),
                        draft.source(),
                        null,
                        null,
                        null
                )
        );
        bookingLineNotificationService.pushBookingIncident(booking, incident);
        return Result.ok(incident);
    }

    public Result listIncidents(String bookingCode, Map<String, Object> body) {
        BookingJpa booking = findBookingOrNull(bookingCode);
        if (booking == null) return Result.fail("訂位不存在");
        if (!canAccessBooking(booking, body)) return Result.fail("無權讀取此訂位的救場通知");

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                """
                SELECT i.id, i.booking_code AS bookingCode, i.user_id AS userId, i.shop_id AS shopId,
                       s.name AS shopName, i.incident_type AS incidentType, i.status,
                       i.delay_minutes AS delayMinutes, i.original_time AS originalTime,
                       i.adjusted_time AS adjustedTime, i.title, i.customer_message AS customerMessage,
                       i.action_label AS actionLabel, i.source, i.created_at AS createdAt,
                       i.proposal_status AS proposalStatus, i.proposed_date AS proposedDate,
                       i.proposed_time AS proposedTime, i.proposed_table_type AS proposedTableType,
                       i.proposed_people AS proposedPeople, i.proposal_message AS proposalMessage,
                       i.proposed_at AS proposedAt, i.proposal_expires_at AS proposalExpiresAt,
                       i.proposal_accepted_at AS proposalAcceptedAt, i.proposal_declined_at AS proposalDeclinedAt,
                       i.updated_at AS updatedAt, i.resolved_at AS resolvedAt
                FROM tb_booking_incident i
                JOIN tb_shop s ON s.id = i.shop_id
                WHERE i.booking_code = ?
                ORDER BY i.created_at DESC
                LIMIT 20
                """,
                booking.getBookingCode()
        );
        return Result.ok(rows.stream().map(this::normalizeIncidentRow).toList());
    }

    public Result resolveIncident(String bookingCode, Long incidentId, Map<String, Object> body) {
        BookingJpa booking = findBookingOrNull(bookingCode);
        if (booking == null) return Result.fail("訂位不存在");
        if (incidentId == null) return Result.fail("incidentId 必填");
        if (!canAccessBooking(booking, body)) return Result.fail("無權處理此訂位的救場通知");

        int updated = jdbcTemplate.update(
                """
                UPDATE tb_booking_incident
                SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP
                WHERE id = ? AND booking_code = ? AND status = 'OPEN'
                """,
                incidentId,
                booking.getBookingCode()
        );
        if (updated == 0) return Result.fail("救場通知不存在或已處理");
        return latestIncidentForBookingCode(booking.getBookingCode())
                .map(Result::ok)
                .orElseGet(() -> Result.ok(Map.of("id", incidentId, "status", "RESOLVED")));
    }

    public Optional<Map<String, Object>> latestIncidentForBookingCode(String bookingCode) {
        if (bookingCode == null || bookingCode.isBlank()) return Optional.empty();
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                """
                SELECT i.id, i.booking_code AS bookingCode, i.user_id AS userId, i.shop_id AS shopId,
                       s.name AS shopName, i.incident_type AS incidentType, i.status,
                       i.delay_minutes AS delayMinutes, i.original_time AS originalTime,
                       i.adjusted_time AS adjustedTime, i.title, i.customer_message AS customerMessage,
                       i.action_label AS actionLabel, i.source, i.created_at AS createdAt,
                       i.proposal_status AS proposalStatus, i.proposed_date AS proposedDate,
                       i.proposed_time AS proposedTime, i.proposed_table_type AS proposedTableType,
                       i.proposed_people AS proposedPeople, i.proposal_message AS proposalMessage,
                       i.proposed_at AS proposedAt, i.proposal_expires_at AS proposalExpiresAt,
                       i.proposal_accepted_at AS proposalAcceptedAt, i.proposal_declined_at AS proposalDeclinedAt,
                       i.updated_at AS updatedAt, i.resolved_at AS resolvedAt
                FROM tb_booking_incident i
                JOIN tb_shop s ON s.id = i.shop_id
                WHERE i.booking_code = ?
                  AND i.status = 'OPEN'
                ORDER BY i.created_at DESC
                LIMIT 1
                """,
                bookingCode.trim()
        );
        return rows.stream().findFirst().map(this::normalizeIncidentRow);
    }

    private BookingJpa findBookingOrNull(String bookingCode) {
        if (bookingCode == null || bookingCode.isBlank()) return null;
        return bookingRepo.findByBookingCode(bookingCode.trim()).orElse(null);
    }

    private IncidentDraft draftFor(BookingJpa booking, Map<String, Object> body) {
        String incidentType = normalizeIncidentType(body.get("incidentType"));
        if (incidentType.isBlank()) incidentType = normalizeIncidentType(body.get("type"));
        if (incidentType.isBlank()) incidentType = "RESTAURANT_DELAY";

        int delayMinutes = parseDelayMinutes(body.get("delayMinutes"));
        String adjustedTime = adjustedTime(booking.getBookingTime(), delayMinutes);
        String source = textOrDefault(body.get("source"), "AI_RESCUE");
        String customMessage = textOrBlank(body.get("message"));

        return switch (incidentType) {
            case "CUSTOMER_LATE" -> IncidentDraft.ok(
                    "CUSTOMER_LATE",
                    delayMinutes,
                    adjustedTime,
                    "已通知店家你會晚到 " + delayMinutes + " 分鐘",
                    customMessage.isBlank()
                            ? "系統已記錄你可能晚到，會協助店家保留到 " + adjustedTime + "。若超過保留時間，座位仍可能依現場狀況釋出。"
                            : customMessage,
                    "已通知店家",
                    source
            );
            case "RESTAURANT_DELAY" -> IncidentDraft.ok(
                    "RESTAURANT_DELAY",
                    delayMinutes,
                    adjustedTime,
                    "店家回報約延 " + delayMinutes + " 分鐘",
                    customMessage.isBlank()
                            ? "店家剛回報前面桌用餐延長，預估 " + adjustedTime + " 左右可入座。你可以先保留原訂位，系統會持續同步狀態。"
                            : customMessage,
                    "已保留原訂位",
                    source
            );
            default -> IncidentDraft.fail("incidentType 僅支援 RESTAURANT_DELAY / CUSTOMER_LATE");
        };
    }

    private Map<String, Object> normalizeIncidentRow(Map<String, Object> row) {
        return incidentPayload(
                row.get("id"),
                null,
                textOrBlank(row.get("shopName")),
                textOrBlank(row.get("incidentType")),
                textOrBlank(row.get("status")),
                toInt(row.get("delayMinutes")),
                textOrBlank(row.get("originalTime")),
                textOrBlank(row.get("adjustedTime")),
                textOrBlank(row.get("title")),
                textOrBlank(row.get("customerMessage")),
                textOrBlank(row.get("actionLabel")),
                textOrBlank(row.get("source")),
                row,
                row.get("createdAt"),
                row.get("resolvedAt")
        );
    }

    private Map<String, Object> incidentPayload(
            Object id,
            BookingJpa booking,
            String shopName,
            String incidentType,
            String status,
            int delayMinutes,
            String originalTime,
            String adjustedTime,
            String title,
            String customerMessage,
            String actionLabel,
            String source,
            Map<String, Object> row,
            Object createdAt,
            Object resolvedAt
    ) {
        Map<String, Object> out = new LinkedHashMap<>();
        if (id != null) out.put("id", id);
        String bookingCode = booking != null ? booking.getBookingCode() : textOrBlank(row.get("bookingCode"));
        Long userId = booking != null ? booking.getUserId() : toLong(row.get("userId"));
        Long shopId = booking != null ? booking.getShopId() : toLong(row.get("shopId"));
        out.put("bookingCode", bookingCode);
        out.put("userId", userId);
        out.put("shopId", shopId);
        out.put("shopName", !shopName.isBlank() ? shopName : "店家 " + shopId);
        out.put("incidentType", incidentType);
        out.put("status", !status.isBlank() ? status : "OPEN");
        out.put("delayMinutes", delayMinutes);
        out.put("originalTime", originalTime);
        out.put("adjustedTime", adjustedTime);
        out.put("title", title);
        out.put("customerMessage", customerMessage);
        out.put("actionLabel", actionLabel);
        out.put("source", source);
        if (createdAt != null) out.put("createdAt", createdAt.toString());
        Map<String, Object> proposedChange = proposedChangePayload(row);
        if (!proposedChange.isEmpty()) out.put("proposedChange", proposedChange);
        Object updatedAt = row != null ? row.get("updatedAt") : null;
        if (updatedAt != null) out.put("updatedAt", updatedAt.toString());
        if (resolvedAt != null) out.put("resolvedAt", resolvedAt.toString());
        return out;
    }

    private Map<String, Object> proposedChangePayload(Map<String, Object> row) {
        if (row == null) return Map.of();
        String proposalStatus = effectiveProposalStatus(row);
        if (proposalStatus.isBlank()) return Map.of();
        Map<String, Object> proposal = new LinkedHashMap<>();
        proposal.put("status", proposalStatus);
        proposal.put("date", textOrBlank(row.get("proposedDate")));
        proposal.put("time", textOrBlank(row.get("proposedTime")));
        proposal.put("tableType", textOrBlank(row.get("proposedTableType")));
        proposal.put("people", toInt(row.get("proposedPeople")));
        proposal.put("message", textOrBlank(row.get("proposalMessage")));
        Object proposedAt = row.get("proposedAt");
        if (proposedAt != null) proposal.put("proposedAt", proposedAt.toString());
        Object expiresAt = row.get("proposalExpiresAt");
        if (expiresAt != null) proposal.put("expiresAt", expiresAt.toString());
        Object acceptedAt = row.get("proposalAcceptedAt");
        if (acceptedAt != null) proposal.put("acceptedAt", acceptedAt.toString());
        Object declinedAt = row.get("proposalDeclinedAt");
        if (declinedAt != null) proposal.put("declinedAt", declinedAt.toString());
        return proposal;
    }

    private String effectiveProposalStatus(Map<String, Object> row) {
        String proposalStatus = textOrBlank(row.get("proposalStatus"));
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
        String raw = textOrBlank(value);
        if (raw.isBlank()) return null;
        try {
            return LocalDateTime.parse(raw.replace(" ", "T"));
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }

    private boolean canAccessBooking(BookingJpa booking, Map<String, Object> body) {
        if (booking == null || booking.getUserId() == null) return false;
        UserDTO user = UserHolder.getUser();
        if (user != null && booking.getUserId().equals(user.getId())) {
            return true;
        }
        return lineActionTokenService.resolveOwnerId(body != null ? body : Map.of())
                .map(booking.getUserId()::equals)
                .orElse(false);
    }

    private String normalizeIncidentType(Object raw) {
        String text = textOrBlank(raw).toUpperCase(Locale.ROOT).replace('-', '_').replace(' ', '_');
        return switch (text) {
            case "RESTAURANT_DELAY", "STORE_DELAY", "DELAY" -> "RESTAURANT_DELAY";
            case "CUSTOMER_LATE", "USER_LATE", "LATE_ARRIVAL" -> "CUSTOMER_LATE";
            default -> text;
        };
    }

    private int parseDelayMinutes(Object raw) {
        int value = toInt(raw);
        if (value <= 0) value = DEFAULT_DELAY_MINUTES;
        return Math.min(value, MAX_DELAY_MINUTES);
    }

    private String adjustedTime(String rawTime, int delayMinutes) {
        try {
            return LocalTime.parse(rawTime).plusMinutes(delayMinutes).toString();
        } catch (Exception ignored) {
            return rawTime;
        }
    }

    private int toInt(Object raw) {
        if (raw instanceof Number number) return number.intValue();
        if (raw == null) return 0;
        try {
            return Integer.parseInt(raw.toString().trim());
        } catch (NumberFormatException ex) {
            return 0;
        }
    }

    private Long toLong(Object raw) {
        if (raw instanceof Number number) return number.longValue();
        if (raw == null) return null;
        try {
            return Long.parseLong(raw.toString().trim());
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private String textOrDefault(Object raw, String fallback) {
        String text = textOrBlank(raw);
        return text.isBlank() ? fallback : text;
    }

    private String textOrBlank(Object raw) {
        return raw != null ? raw.toString().trim() : "";
    }

    private record IncidentDraft(
            boolean valid,
            String error,
            String incidentType,
            int delayMinutes,
            String adjustedTime,
            String title,
            String customerMessage,
            String actionLabel,
            String source
    ) {
        static IncidentDraft ok(
                String incidentType,
                int delayMinutes,
                String adjustedTime,
                String title,
                String customerMessage,
                String actionLabel,
                String source
        ) {
            return new IncidentDraft(true, null, incidentType, delayMinutes, adjustedTime, title, customerMessage, actionLabel, source);
        }

        static IncidentDraft fail(String error) {
            return new IncidentDraft(false, error, "", 0, "", "", "", "", "");
        }
    }
}
