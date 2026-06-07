package com.bytebites.service;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.service.jpa.UserJpaService;
import com.bytebites.utils.UserHolder;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class AvailabilityNotificationService {
    private static final ZoneId BUSINESS_ZONE = ZoneId.of("Asia/Taipei");
    private static final String STATUS_ACTIVE = "ACTIVE";
    private static final String STATUS_TRIGGERED = "TRIGGERED";
    private static final String STATUS_CANCELED = "CANCELED";
    private static final String STATUS_UNREAD = "UNREAD";
    private static final String STATUS_READ = "READ";

    private final JdbcTemplate jdbcTemplate;
    private final LineNotificationClient lineNotificationClient;
    private final UserJpaService userJpaService;

    public Result createWatch(Long shopId, LocalDate bookingDate, String time, String tableType, int people) {
        return createWatch(shopId, bookingDate, time, tableType, people, null);
    }

    public Result createWatch(Long shopId, LocalDate bookingDate, String time, String tableType, int people, String lineUserId) {
        Long userId = resolveOwnerId(lineUserId);
        if (userId == null) return Result.fail("請先用 LINE 登入網頁，再回來設定空位通知");
        if (shopId == null) return Result.fail("shopId 必填");
        if (bookingDate == null) return Result.fail("date 必填");
        if (!bookingDate.isAfter(LocalDate.now(BUSINESS_ZONE))) return Result.fail("只能設定明天或之後的空位通知");
        if (!isSupportedTableType(tableType)) return Result.fail("tableType 僅支援 normal/bar/private");
        if (people < 1 || people > 12) return Result.fail("通知人數需介於 1-12 人");

        ensureSlot(shopId, bookingDate, time, tableType);
        Map<String, Object> slot = slot(shopId, bookingDate, time, tableType);
        int remaining = ((Number) slot.get("remaining")).intValue();
        if (remaining >= people) {
            return Result.fail("此時段目前仍有空位，請直接訂位");
        }

        jdbcTemplate.update(
                """
                INSERT INTO tb_availability_watch
                    (user_id, line_user_id, shop_id, booking_date, booking_time, table_type, people, status, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
                ON DUPLICATE KEY UPDATE
                    line_user_id = COALESCE(VALUES(line_user_id), line_user_id),
                    expires_at = VALUES(expires_at),
                    updated_at = CURRENT_TIMESTAMP
                """,
                userId,
                normalizeLineUserId(lineUserId),
                shopId,
                bookingDate,
                normalizeTime(time),
                tableType,
                people,
                bookingDate.plusDays(1).atStartOfDay()
        );

        Map<String, Object> watch = jdbcTemplate.queryForMap(
                """
                SELECT w.id, w.user_id AS userId, w.shop_id AS shopId, s.name AS shopName,
                       w.booking_date AS date, w.booking_time AS time, w.table_type AS tableType,
                       w.people, w.status, w.expires_at AS expiresAt, w.created_at AS createdAt,
                       w.line_user_id AS lineUserId
                FROM tb_availability_watch w
                JOIN tb_shop s ON s.id = w.shop_id
                WHERE w.user_id = ? AND w.shop_id = ? AND w.booking_date = ?
                  AND w.booking_time = ? AND w.table_type = ? AND w.people = ? AND w.status = 'ACTIVE'
                """,
                userId,
                shopId,
                bookingDate,
                normalizeTime(time),
                tableType,
                people
        );
        return Result.ok(watch);
    }

    public Result myWatches() {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先用 LINE 登入");
        expireOldWatches(userId);
        return Result.ok(jdbcTemplate.queryForList(
                """
                SELECT w.id, w.shop_id AS shopId, s.name AS shopName,
                       w.booking_date AS date, w.booking_time AS time, w.table_type AS tableType,
                       w.people, w.status, w.triggered_at AS triggeredAt,
                       w.expires_at AS expiresAt, w.created_at AS createdAt
                FROM tb_availability_watch w
                JOIN tb_shop s ON s.id = w.shop_id
                WHERE w.user_id = ?
                ORDER BY w.created_at DESC
                LIMIT 50
                """,
                userId
        ));
    }

    public Result myNotifications() {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先用 LINE 登入");
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                """
                SELECT n.id, n.type, n.title, n.body, n.shop_id AS shopId, n.watch_id AS watchId,
                       n.status, n.created_at AS createdAt, n.read_at AS readAt,
                       w.booking_date AS date, w.booking_time AS time, w.table_type AS tableType, w.people,
                       w.line_user_id AS lineUserId,
                       s.name AS shopName
                FROM tb_user_notification n
                LEFT JOIN tb_availability_watch w ON w.id = n.watch_id
                LEFT JOIN tb_shop s ON s.id = n.shop_id
                WHERE n.user_id = ?
                  AND LOWER(n.title) NOT LIKE '%smoke test%'
                  AND LOWER(n.body) NOT LIKE '%smoke test%'
                ORDER BY n.created_at DESC
                LIMIT 50
                """,
                userId
        );
        Integer unread = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM tb_user_notification
                WHERE user_id = ? AND status = 'UNREAD'
                  AND LOWER(title) NOT LIKE '%smoke test%'
                  AND LOWER(body) NOT LIKE '%smoke test%'
                """,
                Integer.class,
                userId
        );
        return Result.ok(Map.of(
                "unreadCount", unread == null ? 0 : unread,
                "items", rows
        ));
    }

    public Result cancelWatch(Long watchId) {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先用 LINE 登入");
        int updated = jdbcTemplate.update(
                """
                UPDATE tb_availability_watch
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ? AND status = ?
                """,
                STATUS_CANCELED,
                watchId,
                userId,
                STATUS_ACTIVE
        );
        return updated == 1
                ? Result.ok(Map.of("id", watchId, "status", STATUS_CANCELED))
                : Result.fail("此空位追蹤不存在或已結束");
    }

    public Result markRead(Long notificationId) {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先用 LINE 登入");
        int updated = jdbcTemplate.update(
                """
                UPDATE tb_user_notification
                SET status = ?, read_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
                """,
                STATUS_READ,
                notificationId,
                userId
        );
        return updated == 1 ? Result.ok(Map.of("id", notificationId, "status", STATUS_READ)) : Result.fail("通知不存在");
    }

    public Result markAllRead() {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先用 LINE 登入");
        int updated = jdbcTemplate.update(
                """
                UPDATE tb_user_notification
                SET status = ?, read_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND status = ?
                """,
                STATUS_READ,
                userId,
                STATUS_UNREAD
        );
        return Result.ok(Map.of("updated", updated));
    }

    public void triggerIfAvailable(Long shopId, LocalDate bookingDate, String time, String tableType) {
        ensureSlot(shopId, bookingDate, time, tableType);
        Map<String, Object> slot = slot(shopId, bookingDate, time, tableType);
        int remaining = ((Number) slot.get("remaining")).intValue();
        if (remaining <= 0) return;

        List<Map<String, Object>> watches = jdbcTemplate.queryForList(
                """
                SELECT w.id, w.user_id, w.shop_id, s.name AS shop_name,
                       w.line_user_id, w.booking_date, w.booking_time, w.table_type, w.people
                FROM tb_availability_watch w
                JOIN tb_shop s ON s.id = w.shop_id
                WHERE w.status = 'ACTIVE'
                  AND w.shop_id = ?
                  AND w.booking_date = ?
                  AND w.booking_time = ?
                  AND w.table_type = ?
                  AND w.people <= ?
                  AND w.expires_at > CURRENT_TIMESTAMP
                ORDER BY w.created_at ASC
                FOR UPDATE
                """,
                shopId,
                bookingDate,
                normalizeTime(time),
                tableType,
                remaining
        );
        for (Map<String, Object> watch : watches) {
            Long watchId = ((Number) watch.get("id")).longValue();
            int updated = jdbcTemplate.update(
                    """
                    UPDATE tb_availability_watch
                    SET status = ?, triggered_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'ACTIVE'
                    """,
                    STATUS_TRIGGERED,
                    watchId
            );
            if (updated != 1) continue;
            String shopName = String.valueOf(watch.get("shop_name"));
            String title = shopName + " 有空位了";
            String body = "%s %s 可訂 %s 人，請盡快完成訂位。".formatted(
                    watch.get("booking_date"),
                    watch.get("booking_time"),
                    watch.get("people")
            );
            int inserted = jdbcTemplate.update(
                    """
                    INSERT IGNORE INTO tb_user_notification
                        (user_id, type, title, body, shop_id, watch_id, status)
                    VALUES (?, 'AVAILABILITY_RELEASED', ?, ?, ?, ?, ?)
                    """,
                    watch.get("user_id"),
                    title,
                    body,
                    shopId,
                    watchId,
                    STATUS_UNREAD
            );
            Long notificationId = inserted == 1 ? jdbcTemplate.queryForObject(
                    "SELECT id FROM tb_user_notification WHERE watch_id = ?",
                    Long.class,
                    watchId
            ) : null;
            lineNotificationClient.pushAvailabilityReleased(watch, notificationId);
        }
    }

    private void expireOldWatches(Long userId) {
        jdbcTemplate.update(
                """
                UPDATE tb_availability_watch
                SET status = 'EXPIRED'
                WHERE user_id = ? AND status = 'ACTIVE' AND expires_at <= CURRENT_TIMESTAMP
                """,
                userId
        );
    }

    private void ensureSlot(Long shopId, LocalDate bookingDate, String time, String tableType) {
        jdbcTemplate.update(
                """
                INSERT IGNORE INTO tb_booking_slot_inventory
                    (shop_id, booking_date, booking_time, table_type, capacity, booked_count)
                VALUES (?, ?, ?, ?, 8, 0)
                """,
                shopId,
                bookingDate,
                normalizeTime(time),
                tableType
        );
    }

    private Map<String, Object> slot(Long shopId, LocalDate bookingDate, String time, String tableType) {
        Map<String, Object> row = jdbcTemplate.queryForMap(
                """
                SELECT capacity, booked_count AS bookedCount,
                       GREATEST(capacity - booked_count, 0) AS remaining
                FROM tb_booking_slot_inventory
                WHERE shop_id = ? AND booking_date = ? AND booking_time = ? AND table_type = ?
                """,
                shopId,
                bookingDate,
                normalizeTime(time),
                tableType
        );
        return new LinkedHashMap<>(row);
    }

    private Long currentUserIdOrNull() {
        UserDTO user = UserHolder.getUser();
        return user != null ? user.getId() : null;
    }

    private Long resolveOwnerId(String lineUserId) {
        Long currentUserId = currentUserIdOrNull();
        if (currentUserId != null) return currentUserId;
        String normalizedLineUserId = normalizeLineUserId(lineUserId);
        if (normalizedLineUserId == null) return null;
        return userJpaService.resolveLineIdentity(normalizedLineUserId, null).getId();
    }

    private String normalizeTime(String raw) {
        if (raw == null || !raw.matches("^\\d{1,2}:\\d{2}$")) return raw;
        String[] parts = raw.split(":");
        return "%02d:%02d".formatted(Integer.parseInt(parts[0]), Integer.parseInt(parts[1]));
    }

    private String normalizeLineUserId(String raw) {
        if (raw == null) return null;
        String value = raw.trim();
        if (value.isBlank() || value.length() > 128) return null;
        return value;
    }

    private boolean isSupportedTableType(String tableType) {
        return tableType.equals("normal") || tableType.equals("bar") || tableType.equals("private");
    }
}
