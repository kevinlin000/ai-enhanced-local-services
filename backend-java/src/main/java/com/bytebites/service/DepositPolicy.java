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
 * 訂金政策：從 price_per_person 用 regex 抽最大金額，依階梯決定訂金。
 * 抽不到時 fallback 到 type_id（高級/無菜單一律收）。
 *
 * 價格階梯：
 *   maxPrice >= 2000 → 訂金 500/人
 *   maxPrice >= 1000 → 訂金 300/人
 *   maxPrice >= 500  → 訂金 100/人
 *   maxPrice <  500  → 免訂金
 *
 * Fallback（price 抽不到）：
 *   type_id 2011(高級餐廳) / 2005(無菜單) → 訂金 500/人
 *   其他 → 免訂金
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DepositPolicy {

    private final ShopAiMetadataJpaRepository aiRepo;

    private static final Set<Integer> ALWAYS_DEPOSIT_FALLBACK = Set.of(2011, 2005);

    /**
     * 抽 price_per_person 字串中的「最大數字」作為人均上限。
     * 範例：
     *   "$800-1200"   → 1200
     *   "$1000-$1500" → 1500
     *   "$768-868+"   → 868
     *   "$310"        → 310
     *   "1200元以上"   → 1200
     *   "$400起"      → 400
     *   "未提及"       → null
     */
    private static final Pattern NUMBER_PATTERN = Pattern.compile("\\d+");

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
                if (n < 50 || n > 50000) continue; // 過濾雜訊
                if (max == null || n > max) max = n;
            } catch (NumberFormatException ignore) {
            }
        }
        return max;
    }

    public Result evaluate(Long shopId, Integer typeId, Integer score) {
        ShopAiMetadataJpa ai = aiRepo.findById(shopId).orElse(null);
        String pricePerPerson = ai == null ? null : ai.getPricePerPerson();
        Integer maxPrice = extractMaxPrice(pricePerPerson);

        log.debug("[DepositPolicy] shop={} pricePerPerson={} maxPrice={}", shopId, pricePerPerson, maxPrice);

        if (maxPrice != null) {
            if (maxPrice >= 2000) {
                return new Result(true, 500, "人均 NT$ " + maxPrice + "、屬高價餐廳", maxPrice);
            }
            if (maxPrice >= 1000) {
                return new Result(true, 300, "人均 NT$ " + maxPrice + "、收取訂金", maxPrice);
            }
            if (maxPrice >= 500) {
                return new Result(true, 100, "人均 NT$ " + maxPrice + "、收取小額訂金", maxPrice);
            }
            return new Result(false, 0, "人均 NT$ " + maxPrice + "、免訂金", maxPrice);
        }

        // fallback: 抽不到價格時依 type_id
        if (typeId != null && ALWAYS_DEPOSIT_FALLBACK.contains(typeId)) {
            return new Result(true, 500, "高級類型、收取訂金", null);
        }
        return new Result(false, 0, "免訂金", null);
    }

    @Value
    public static class Result {
        boolean needsDeposit;
        int depositPerPerson;
        String reason;
        Integer extractedPrice; // debug 用
    }
}
