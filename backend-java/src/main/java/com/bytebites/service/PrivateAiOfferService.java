package com.bytebites.service;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.Shop;
import com.bytebites.utils.UserHolder;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class PrivateAiOfferService {
    private static final ZoneId BUSINESS_ZONE = ZoneId.of("Asia/Taipei");
    private static final LocalTime OFF_PEAK_CUTOFF = LocalTime.of(17, 30);
    private static final int MAX_MATCH_SHOPS = 8;

    private final JdbcTemplate jdbcTemplate;
    private final IShopService shopService;

    public Result myOffers() {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先登入後再讀取 AI 私密優惠");

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                """
                SELECT o.id, o.shop_id AS shopId, s.name AS shopName, o.offer_code AS offerCode,
                       o.title, o.description, o.trigger_reason AS triggerReason,
                       o.offer_type AS offerType, o.discount_percent AS discountPercent,
                       o.min_people AS minPeople, o.valid_until AS validUntil, o.status,
                       o.source, o.created_at AS createdAt, o.updated_at AS updatedAt,
                       o.claimed_at AS claimedAt
                FROM tb_private_ai_offer o
                JOIN tb_shop s ON s.id = o.shop_id
                WHERE o.user_id = ?
                  AND o.status IN ('ACTIVE', 'CLAIMED')
                  AND o.valid_until > CURRENT_TIMESTAMP
                ORDER BY CASE WHEN o.status = 'ACTIVE' THEN 0 ELSE 1 END, o.valid_until ASC
                LIMIT 50
                """,
                userId
        );
        return Result.ok(Map.of("offers", rows.stream().map(this::offerPayload).toList()));
    }

    public Result matchOffers(Map<String, Object> body) {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先登入後再配對 AI 私密優惠");

        List<Long> shopIds = parseShopIds(body);
        if (shopIds.isEmpty()) return Result.fail("shopIds 必填");

        String triggerReason = normalizeTrigger(body.get("trigger"));
        String targetTime = textOrBlank(body.get("targetTime"));
        Integer people = toIntOrNull(body.get("people"));

        List<Map<String, Object>> existing = new ArrayList<>();
        for (Long shopId : shopIds) {
            findActiveOffer(userId, shopId).stream().map(this::offerPayload).forEach(existing::add);
        }
        if (!existing.isEmpty()) {
            return Result.ok(Map.of(
                    "offers", existing,
                    "created", false,
                    "triggerReason", triggerReason
            ));
        }

        if (!eligibleForNewOffer(triggerReason, targetTime)) {
            return Result.ok(Map.of(
                    "offers", List.of(),
                    "created", false,
                    "triggerReason", triggerReason,
                    "reason", "目前未符合私密優惠觸發條件"
            ));
        }

        for (Long shopId : shopIds) {
            Shop shop = shopService.getById(shopId);
            if (shop == null || Integer.valueOf(0).equals(shop.getIsActive())) {
                continue;
            }
            OfferDraft draft = draftFor(shop, triggerReason, people, targetTime);
            String offerCode = newOfferCode();
            jdbcTemplate.update(
                    """
                    INSERT INTO tb_private_ai_offer
                        (user_id, shop_id, offer_code, title, description, trigger_reason,
                         offer_type, discount_percent, min_people, valid_until, status, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 'AI_MATCHED')
                    """,
                    userId,
                    shopId,
                    offerCode,
                    draft.title(),
                    draft.description(),
                    triggerReason,
                    draft.offerType(),
                    draft.discountPercent(),
                    draft.minPeople(),
                    draft.validUntil()
            );
            return Result.ok(Map.of(
                    "offers", List.of(offerPayload(
                            shopId,
                            shop.getName(),
                            offerCode,
                            draft.title(),
                            draft.description(),
                            triggerReason,
                            draft.offerType(),
                            draft.discountPercent(),
                            draft.minPeople(),
                            draft.validUntil(),
                            "ACTIVE"
                    )),
                    "created", true,
                    "triggerReason", triggerReason
            ));
        }

        return Result.ok(Map.of(
                "offers", List.of(),
                "created", false,
                "triggerReason", triggerReason,
                "reason", "推薦店家目前不可建立私密優惠"
        ));
    }

    public Result claimOffer(String offerCode) {
        Long userId = currentUserIdOrNull();
        if (userId == null) return Result.fail("請先登入後再領用 AI 私密優惠");
        String code = offerCode != null ? offerCode.trim() : "";
        if (code.isBlank()) return Result.fail("offerCode 必填");

        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                """
                SELECT o.id, o.shop_id AS shopId, s.name AS shopName, o.offer_code AS offerCode,
                       o.title, o.description, o.trigger_reason AS triggerReason,
                       o.offer_type AS offerType, o.discount_percent AS discountPercent,
                       o.min_people AS minPeople, o.valid_until AS validUntil, o.status,
                       o.source, o.created_at AS createdAt, o.updated_at AS updatedAt,
                       o.claimed_at AS claimedAt
                FROM tb_private_ai_offer o
                JOIN tb_shop s ON s.id = o.shop_id
                WHERE o.user_id = ?
                  AND o.offer_code = ?
                  AND o.valid_until > CURRENT_TIMESTAMP
                LIMIT 1
                """,
                userId,
                code
        );
        if (rows.isEmpty()) return Result.fail("找不到可用的 AI 私密優惠");

        Map<String, Object> offer = new LinkedHashMap<>(offerPayload(rows.get(0)));
        String status = textOrBlank(offer.get("status"));
        if (!"ACTIVE".equals(status) && !"CLAIMED".equals(status)) {
            return Result.fail("此 AI 私密優惠已不可使用");
        }
        if ("ACTIVE".equals(status)) {
            jdbcTemplate.update(
                    """
                    UPDATE tb_private_ai_offer
                    SET status = 'CLAIMED', claimed_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND offer_code = ? AND status = 'ACTIVE'
                    """,
                    userId,
                    code
            );
            offer.put("status", "CLAIMED");
        }
        return Result.ok(offer);
    }

    private List<Map<String, Object>> findActiveOffer(Long userId, Long shopId) {
        return jdbcTemplate.queryForList(
                """
                SELECT o.id, o.shop_id AS shopId, s.name AS shopName, o.offer_code AS offerCode,
                       o.title, o.description, o.trigger_reason AS triggerReason,
                       o.offer_type AS offerType, o.discount_percent AS discountPercent,
                       o.min_people AS minPeople, o.valid_until AS validUntil, o.status,
                       o.source, o.created_at AS createdAt, o.updated_at AS updatedAt,
                       o.claimed_at AS claimedAt
                FROM tb_private_ai_offer o
                JOIN tb_shop s ON s.id = o.shop_id
                WHERE o.user_id = ?
                  AND o.shop_id = ?
                  AND o.status = 'ACTIVE'
                  AND o.valid_until > CURRENT_TIMESTAMP
                ORDER BY o.valid_until DESC
                LIMIT 1
                """,
                userId,
                shopId
        );
    }

    private OfferDraft draftFor(Shop shop, String triggerReason, Integer people, String targetTime) {
        int minPeople = people != null && people > 1 ? Math.min(people, 6) : 1;
        LocalDateTime validUntil = LocalDateTime.now(BUSINESS_ZONE).plusDays(2);
        String shopName = shop.getName() != null ? shop.getName() : "店家";
        if ("REPEATED_SEARCH_NO_BOOKING".equals(triggerReason)) {
            return new OfferDraft(
                    "AI 私密回訪 9 折",
                    "你近期多次查看但尚未訂位，AI 已替你保留 " + shopName + " 的限時專屬優惠。",
                    "RETENTION_SAVE",
                    10,
                    minPeople,
                    validUntil
            );
        }
        if ("SAVE_MONEY_INTENT".equals(triggerReason)) {
            return new OfferDraft(
                    "AI 私密省錢 9 折",
                    "只在此帳號顯示，訂位前由 AI 自動配對，不會出現在公開店家頁。",
                    "PRIVATE_MATCH",
                    10,
                    minPeople,
                    validUntil
            );
        }
        String timeHint = targetTime.isBlank() ? "17:30 前入座或店家空檔時段" : targetTime + " 附近空檔";
        return new OfferDraft(
                "AI 私密離峰 9 折",
                "只在此帳號顯示，適用 " + timeHint + "。",
                "OFF_PEAK_FILL",
                10,
                minPeople,
                validUntil
        );
    }

    private boolean eligibleForNewOffer(String triggerReason, String targetTime) {
        return "OFF_PEAK_FILL".equals(triggerReason)
                || "REPEATED_SEARCH_NO_BOOKING".equals(triggerReason)
                || "SAVE_MONEY_INTENT".equals(triggerReason)
                || isOffPeakTime(targetTime);
    }

    private boolean isOffPeakTime(String targetTime) {
        String text = targetTime != null ? targetTime.trim() : "";
        if (text.isBlank()) return false;
        String timePart = text.length() >= 5 ? text.substring(Math.max(0, text.length() - 5)) : text;
        try {
            return !LocalTime.parse(timePart).isAfter(OFF_PEAK_CUTOFF);
        } catch (Exception ignored) {
            return false;
        }
    }

    private String normalizeTrigger(Object raw) {
        String trigger = textOrBlank(raw).toUpperCase(Locale.ROOT).replace('-', '_').replace(' ', '_');
        return switch (trigger) {
            case "OFF_PEAK", "OFF_PEAK_FILL" -> "OFF_PEAK_FILL";
            case "REPEATED_SEARCH", "REPEATED_SEARCH_NO_BOOKING", "NO_BOOKING_RETENTION" -> "REPEATED_SEARCH_NO_BOOKING";
            case "SAVE_MONEY", "SAVE_MONEY_INTENT", "DISCOUNT_INTENT" -> "SAVE_MONEY_INTENT";
            default -> "AI_RECOMMENDATION";
        };
    }

    private List<Long> parseShopIds(Map<String, Object> body) {
        Object raw = body.get("shopIds");
        if (raw == null) raw = body.get("shop_ids");
        LinkedHashSet<Long> ids = new LinkedHashSet<>();
        if (raw instanceof Iterable<?> iterable) {
            for (Object item : iterable) addShopId(ids, item);
        } else if (raw instanceof String text) {
            for (String item : text.split("[,，、]")) addShopId(ids, item);
        } else {
            addShopId(ids, raw);
        }
        return ids.stream().limit(MAX_MATCH_SHOPS).toList();
    }

    private void addShopId(LinkedHashSet<Long> ids, Object raw) {
        Long shopId = toLong(raw);
        if (shopId != null && shopId > 0) ids.add(shopId);
    }

    private Map<String, Object> offerPayload(Map<String, Object> row) {
        return offerPayload(
                toLong(row.get("shopId")),
                textOrBlank(row.get("shopName")),
                textOrBlank(row.get("offerCode")),
                textOrBlank(row.get("title")),
                textOrBlank(row.get("description")),
                textOrBlank(row.get("triggerReason")),
                textOrBlank(row.get("offerType")),
                toInt(row.get("discountPercent")),
                toInt(row.get("minPeople")),
                row.get("validUntil"),
                textOrBlank(row.get("status")),
                row
        );
    }

    private Map<String, Object> offerPayload(
            Long shopId,
            String shopName,
            String offerCode,
            String title,
            String description,
            String triggerReason,
            String offerType,
            int discountPercent,
            int minPeople,
            Object validUntil,
            String status
    ) {
        return offerPayload(shopId, shopName, offerCode, title, description, triggerReason, offerType,
                discountPercent, minPeople, validUntil, status, Map.of());
    }

    private Map<String, Object> offerPayload(
            Long shopId,
            String shopName,
            String offerCode,
            String title,
            String description,
            String triggerReason,
            String offerType,
            int discountPercent,
            int minPeople,
            Object validUntil,
            String status,
            Map<String, Object> row
    ) {
        Map<String, Object> out = new LinkedHashMap<>();
        Object id = row.get("id");
        if (id != null) out.put("id", id);
        out.put("shopId", shopId);
        out.put("shopName", !shopName.isBlank() ? shopName : "店家 " + shopId);
        out.put("offerCode", offerCode);
        out.put("title", title);
        out.put("description", description);
        out.put("triggerReason", triggerReason);
        out.put("offerType", offerType);
        out.put("discountPercent", discountPercent);
        out.put("minPeople", minPeople);
        out.put("validUntil", validUntil != null ? validUntil.toString() : "");
        out.put("status", !status.isBlank() ? status : "ACTIVE");
        Object createdAt = row.get("createdAt");
        Object updatedAt = row.get("updatedAt");
        Object claimedAt = row.get("claimedAt");
        if (createdAt != null) out.put("createdAt", createdAt.toString());
        if (updatedAt != null) out.put("updatedAt", updatedAt.toString());
        if (claimedAt != null) out.put("claimedAt", claimedAt.toString());
        return out;
    }

    private String newOfferCode() {
        return "PO-" + UUID.randomUUID().toString()
                .replace("-", "")
                .substring(0, 12)
                .toUpperCase(Locale.ROOT);
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

    private Integer toIntOrNull(Object raw) {
        if (raw instanceof Number number) return number.intValue();
        if (raw == null) return null;
        try {
            return Integer.parseInt(raw.toString().trim());
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private int toInt(Object raw) {
        Integer value = toIntOrNull(raw);
        return value != null ? value : 0;
    }

    private String textOrBlank(Object raw) {
        return raw != null ? raw.toString().trim() : "";
    }

    private Long currentUserIdOrNull() {
        UserDTO user = UserHolder.getUser();
        return user != null ? user.getId() : null;
    }

    private record OfferDraft(
            String title,
            String description,
            String offerType,
            int discountPercent,
            int minPeople,
            LocalDateTime validUntil
    ) {}
}
