package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.utils.UserHolder;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.List;
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
        }

        return slots(shopId, bookingDate.toString(), tableType);
    }

    private Long requireUserId() {
        var user = UserHolder.getUser();
        return user == null ? null : user.getId();
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
