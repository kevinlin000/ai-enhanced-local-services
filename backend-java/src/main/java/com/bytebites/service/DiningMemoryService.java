package com.bytebites.service;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.Shop;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.utils.UserHolder;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class DiningMemoryService {
    private static final TypeReference<List<String>> STRING_LIST = new TypeReference<>() {};
    private static final int MAX_TAGS = 6;
    private static final int MAX_NOTE_LENGTH = 500;

    private final JdbcTemplate jdbcTemplate;
    private final BookingJpaRepository bookingRepo;
    private final IShopService shopService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public Result saveBookingMemory(String bookingCode, Map<String, Object> body) {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先登入後再記錄私人偏好");
        if (bookingCode == null || bookingCode.isBlank()) return Result.fail("bookingCode 必填");

        Optional<BookingJpa> bookingMaybe = bookingRepo.findByBookingCode(bookingCode.trim());
        if (bookingMaybe.isEmpty()) return Result.fail("訂位不存在");
        BookingJpa booking = bookingMaybe.get();
        if (booking.getUserId() == null || !booking.getUserId().equals(userId)) {
            return Result.fail("無權記錄此訂位偏好");
        }
        if (booking.getStatus() == BookingHoldService.STATUS_CANCELED
                || booking.getStatus() == BookingHoldService.STATUS_EXPIRED) {
            return Result.fail("已取消或逾期訂位不建立用餐記憶");
        }

        ParsedMemory parsed = parseMemory(body);
        if (!parsed.valid()) {
            return Result.fail(parsed.error());
        }

        String tagsJson;
        try {
            tagsJson = objectMapper.writeValueAsString(parsed.tags());
        } catch (JsonProcessingException ex) {
            return Result.fail("偏好標籤格式錯誤");
        }

        jdbcTemplate.update(
                """
                INSERT INTO tb_dining_memory
                    (user_id, booking_code, shop_id, rating, tags_json, note, do_not_recommend, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'BOOKING_FEEDBACK')
                ON DUPLICATE KEY UPDATE
                    shop_id = VALUES(shop_id),
                    rating = VALUES(rating),
                    tags_json = VALUES(tags_json),
                    note = VALUES(note),
                    do_not_recommend = VALUES(do_not_recommend),
                    updated_at = CURRENT_TIMESTAMP
                """,
                userId,
                booking.getBookingCode(),
                booking.getShopId(),
                parsed.rating(),
                tagsJson,
                parsed.note(),
                parsed.doNotRecommend()
        );

        Shop shop = booking.getShopId() == null ? null : shopService.getById(booking.getShopId());
        Map<String, Object> payload = memoryPayload(
                booking.getBookingCode(),
                booking.getShopId(),
                shop != null ? shop.getName() : null,
                parsed.rating(),
                parsed.tags(),
                parsed.note(),
                parsed.doNotRecommend()
        );
        return Result.ok(payload);
    }

    public Result myMemory() {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先登入後再讀取私人偏好");

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                """
                SELECT m.booking_code AS bookingCode,
                       m.shop_id AS shopId,
                       s.name AS shopName,
                       m.rating,
                       m.tags_json AS tagsJson,
                       m.note,
                       m.do_not_recommend AS doNotRecommend,
                       m.created_at AS createdAt,
                       m.updated_at AS updatedAt
                FROM tb_dining_memory m
                JOIN tb_shop s ON s.id = m.shop_id
                WHERE m.user_id = ?
                ORDER BY m.updated_at DESC
                LIMIT 100
                """,
                userId
        );

        List<Map<String, Object>> memories = rows.stream().map(this::normalizeRow).toList();
        Map<String, Integer> tagCounts = new LinkedHashMap<>();
        List<Long> avoidShopIds = new ArrayList<>();
        for (Map<String, Object> memory : memories) {
            @SuppressWarnings("unchecked")
            List<String> tags = (List<String>) memory.getOrDefault("tags", List.of());
            for (String tag : tags) {
                tagCounts.put(tag, tagCounts.getOrDefault(tag, 0) + 1);
            }
            if (Boolean.TRUE.equals(memory.get("doNotRecommend"))) {
                Object shopId = memory.get("shopId");
                if (shopId instanceof Number number) {
                    avoidShopIds.add(number.longValue());
                }
            }
        }

        return Result.ok(Map.of(
                "memories", memories,
                "tagCounts", tagCounts,
                "avoidShopIds", avoidShopIds
        ));
    }

    private ParsedMemory parseMemory(Map<String, Object> body) {
        Map<String, Object> safeBody = body != null ? body : Map.of();
        int rating;
        try {
            rating = Integer.parseInt(String.valueOf(safeBody.getOrDefault("rating", 2)));
        } catch (NumberFormatException ex) {
            return ParsedMemory.fail("rating 需為 1-3");
        }
        if (rating < 1 || rating > 3) {
            return ParsedMemory.fail("rating 需為 1-3");
        }

        List<String> tags = parseTags(safeBody.get("tags"));
        boolean doNotRecommend = truthy(safeBody.get("doNotRecommend")) || tags.contains("不再推薦");
        if (doNotRecommend && !tags.contains("不再推薦")) {
            tags = new ArrayList<>(tags);
            tags.add("不再推薦");
        }
        if (tags.isEmpty()) {
            return ParsedMemory.fail("至少選擇 1 個用餐標籤");
        }
        if (tags.size() > MAX_TAGS) {
            return ParsedMemory.fail("用餐標籤最多 6 個");
        }

        String note = safeBody.get("note") != null ? safeBody.get("note").toString().trim() : "";
        if (note.length() > MAX_NOTE_LENGTH) {
            return ParsedMemory.fail("note 長度不可超過 500 字");
        }
        return ParsedMemory.ok(rating, tags, note, doNotRecommend);
    }

    private List<String> parseTags(Object raw) {
        LinkedHashSet<String> out = new LinkedHashSet<>();
        if (raw instanceof Iterable<?> iterable) {
            for (Object item : iterable) {
                addTag(out, item);
            }
        } else if (raw instanceof String text) {
            for (String item : text.split("[,，、]")) {
                addTag(out, item);
            }
        }
        return new ArrayList<>(out);
    }

    private void addTag(LinkedHashSet<String> out, Object raw) {
        if (raw == null) return;
        String tag = raw.toString().trim();
        if (tag.isBlank() || tag.length() > 20) return;
        out.add(tag);
    }

    private Map<String, Object> normalizeRow(Map<String, Object> row) {
        List<String> tags = parseTagsJson(row.get("tagsJson"));
        return memoryPayload(
                String.valueOf(row.get("bookingCode")),
                toLong(row.get("shopId")),
                row.get("shopName") != null ? String.valueOf(row.get("shopName")) : null,
                toInt(row.get("rating")),
                tags,
                row.get("note") != null ? String.valueOf(row.get("note")) : "",
                truthy(row.get("doNotRecommend")),
                row.get("createdAt"),
                row.get("updatedAt")
        );
    }

    private Map<String, Object> memoryPayload(
            String bookingCode,
            Long shopId,
            String shopName,
            int rating,
            List<String> tags,
            String note,
            boolean doNotRecommend
    ) {
        return memoryPayload(bookingCode, shopId, shopName, rating, tags, note, doNotRecommend, null, null);
    }

    private Map<String, Object> memoryPayload(
            String bookingCode,
            Long shopId,
            String shopName,
            int rating,
            List<String> tags,
            String note,
            boolean doNotRecommend,
            Object createdAt,
            Object updatedAt
    ) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("bookingCode", bookingCode);
        out.put("shopId", shopId);
        out.put("shopName", shopName != null ? shopName : "店家 " + shopId);
        out.put("rating", rating);
        out.put("tags", tags);
        out.put("note", note != null ? note : "");
        out.put("doNotRecommend", doNotRecommend);
        if (createdAt != null) out.put("createdAt", createdAt.toString());
        if (updatedAt != null) out.put("updatedAt", updatedAt.toString());
        return out;
    }

    private List<String> parseTagsJson(Object raw) {
        if (raw == null) return List.of();
        try {
            return objectMapper.readValue(raw.toString(), STRING_LIST);
        } catch (Exception ignored) {
            return parseTags(raw);
        }
    }

    private Long toLong(Object raw) {
        if (raw instanceof Number number) return number.longValue();
        if (raw == null) return null;
        try {
            return Long.parseLong(raw.toString());
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private int toInt(Object raw) {
        if (raw instanceof Number number) return number.intValue();
        if (raw == null) return 0;
        try {
            return Integer.parseInt(raw.toString());
        } catch (NumberFormatException ex) {
            return 0;
        }
    }

    private boolean truthy(Object value) {
        if (value == null) return false;
        if (value instanceof Boolean bool) return bool;
        if (value instanceof Number number) return number.intValue() != 0;
        String text = value.toString().trim();
        return text.equalsIgnoreCase("true") || text.equals("1") || text.equals("是");
    }

    private Long currentUserIdOrNull() {
        UserDTO user = UserHolder.getUser();
        return user != null ? user.getId() : null;
    }

    private record ParsedMemory(
            boolean valid,
            String error,
            int rating,
            List<String> tags,
            String note,
            boolean doNotRecommend
    ) {
        static ParsedMemory ok(int rating, List<String> tags, String note, boolean doNotRecommend) {
            return new ParsedMemory(true, null, rating, tags, note, doNotRecommend);
        }

        static ParsedMemory fail(String error) {
            return new ParsedMemory(false, error, 0, List.of(), "", false);
        }
    }
}
