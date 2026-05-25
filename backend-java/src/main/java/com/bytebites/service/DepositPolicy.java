package com.bytebites.service;

import com.bytebites.entity.jpa.ShopAiMetadataJpa;
import com.bytebites.repository.ShopAiMetadataJpaRepository;
import lombok.RequiredArgsConstructor;
import lombok.Value;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 訂金政策。優先順序：
 *   1. tb_shop.avg_price（Google 資料、最可靠）
 *   2. ai_metadata.price_per_person（LLM 抽、雜訊多）
 *   3. type_id fallback（高級/無菜單類型）
 *
 * 價格階梯：
 *   price >= 2000 → 訂金 500/人
 *   price >= 1000 → 訂金 300/人
 *   price >= 500  → 訂金 100/人
 *   price <  500  → 免訂金
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DepositPolicy {

    private final ShopAiMetadataJpaRepository aiRepo;

    private static final Set<Integer> ALWAYS_DEPOSIT_FALLBACK = Set.of(2011, 2005);

    private static final Pattern NUMBER_PATTERN = Pattern.compile("\\d+");

    /**
     * 抽 price_per_person 字串中的最大數字（過濾雜訊 < 50 或 > 50000）。
     */
    public Integer extractMaxPrice(String pricePerPerson) {
        if (pricePerPerson == null || pricePerPerson.isBlank()
                || pricePerPerson.contains("未提及") || pricePerPerson.contains("未知")) {
            return null;
        }
        Matcher m = NUMBER_PATTERN.matcher(pricePerPerson);
        Integer max = null;
        while (m.find()) {
            try {
                int n = Integer.parseInt(m.group());
                if (n < 50 || n > 50000) continue;
                if (max == null || n > max) max = n;
            } catch (NumberFormatException ignore) {
            }
        }
        return max;
    }

    /**
     * 評估訂金政策。
     *
     * @param shopId   店家 ID（用於查 AI metadata）
     * @param typeId   商店類型 ID（fallback 用）
     * @param score    評分（保留、供未來規則擴充）
     * @param avgPrice tb_shop.avg_price（人均，可為 null）
     */
    public Result evaluate(Long shopId, Integer typeId, Integer score, Integer avgPrice) {
        // Priority 1: tb_shop.avg_price（Google 資料）
        if (avgPrice != null && avgPrice > 0) {
            log.debug("[DepositPolicy] shop={} using avg_price={}", shopId, avgPrice);
            return decideByPrice(avgPrice, "Google 顯示人均 NT$ " + avgPrice);
        }

        // Priority 2: ai_metadata.price_per_person（LLM 抽）
        ShopAiMetadataJpa ai = aiRepo.findById(shopId).orElse(null);
        String pricePerPerson = ai == null ? null : ai.getPricePerPerson();
        Integer maxPrice = extractMaxPrice(pricePerPerson);
        if (maxPrice != null) {
            log.debug("[DepositPolicy] shop={} using ai_price_per_person={} → maxPrice={}", shopId, pricePerPerson, maxPrice);
            return decideByPrice(maxPrice, "AI 從評論推估人均 NT$ " + maxPrice);
        }

        // Priority 3: type_id fallback
        log.debug("[DepositPolicy] shop={} fallback typeId={}", shopId, typeId);
        if (typeId != null && ALWAYS_DEPOSIT_FALLBACK.contains(typeId)) {
            return new Result(true, 500, "高級類型、收取訂金", null);
        }
        return new Result(false, 0, "免訂金", null);
    }

    private Result decideByPrice(int price, String reason) {
        if (price >= 2000) return new Result(true, 500,  reason + "、屬高價", price);
        if (price >= 1000) return new Result(true, 300,  reason + "、收取訂金", price);
        if (price >= 500)  return new Result(true, 100,  reason + "、小額訂金", price);
        return new Result(false, 0, reason + "、免訂金", price);
    }

    @Value
    public static class Result {
        boolean needsDeposit;
        int depositPerPerson;
        String reason;
        Integer extractedPrice; // debug 用
    }
}
