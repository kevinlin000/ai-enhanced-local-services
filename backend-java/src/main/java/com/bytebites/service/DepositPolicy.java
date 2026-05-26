package com.bytebites.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bytebites.entity.Shop;
import com.bytebites.entity.jpa.ShopAiMetadataJpa;
import com.bytebites.repository.ShopAiMetadataJpaRepository;
import lombok.RequiredArgsConstructor;
import lombok.Value;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 訂金政策。優先順序：
 *   1. 同品牌 max avg_price（同連鎖不同分店統一定價）
 *   2. 本店 tb_shop.avg_price（Google 資料）
 *   3. ai_metadata.price_per_person（LLM 抽）
 *   4. type_id ∈ {2001,2002,2004,2006} + score >= 46 → 熱門高評分收訂金
 *   5. type_id fallback（高級/無菜單類型）
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
    private final IShopService shopService;

    private static final Set<Integer> ALWAYS_DEPOSIT_FALLBACK = Set.of(2011, 2005);
    /** 連鎖熱門類型：高評分時收訂金 */
    private static final Set<Integer> CONDITIONAL_DEPOSIT = Set.of(2001, 2002, 2004, 2006);
    private static final int HIGH_SCORE_THRESHOLD = 46; // score 儲存值 = 評分 × 10

    private static final Pattern NUMBER_PATTERN = Pattern.compile("\\d+");

    /** 店別後綴：行政區、商圈、百貨、編號、通用詞 */
    private static final Pattern BRANCH_SUFFIX = Pattern.compile(
        "[ ·\\-]*(信義|大安|中山|中正|松山|內湖|士林|北投|文山|南港|萬華|大同|" +
        "敦南|敦化|忠孝|復興|永康|公館|西門|東門|南西|微風|誠品|京站|" +
        "A4|A8|A11|A13|101|世貿|永吉|南昌|古亭|台北|" +
        "本店|別館|別店|本館|總店|分店|二店|店|館)+$"
    );

    /**
     * 把「品牌 + 店別」縮成「品牌名稱」。
     * 例：「鼎泰豐 A4店」→「鼎泰豐」、「一蘭 台灣台北別館」→「一蘭」
     */
    public String normalizeBrand(String name) {
        if (name == null) return "";
        String n = name.trim();
        Matcher m = BRANCH_SUFFIX.matcher(n);
        // 反覆砍尾巴，避免「A4店」這種多層後綴
        while (m.find() && m.start() > 0) {
            n = n.substring(0, m.start()).trim();
            m = BRANCH_SUFFIX.matcher(n);
        }
        return n.trim();
    }

    /**
     * 查同品牌（同連鎖）所有分店，取 avg_price 最大值。
     * 解決：A4店有 avg_price、101店沒有 → 101店跟 A4店收一樣訂金。
     */
    public Integer brandMaxAvgPrice(String shopName) {
        String brand = normalizeBrand(shopName);
        if (brand == null || brand.isBlank()) return null;

        LambdaQueryWrapper<Shop> w = new LambdaQueryWrapper<>();
        w.eq(Shop::getIsActive, 1);
        w.eq(Shop::getSource, "google_places");
        w.like(Shop::getName, brand);
        w.isNotNull(Shop::getAvgPrice);
        w.gt(Shop::getAvgPrice, 0);

        List<Shop> siblings = shopService.list(w);
        return siblings.stream()
                .map(s -> s.getAvgPrice() != null ? s.getAvgPrice().intValue() : null)
                .filter(java.util.Objects::nonNull)
                .max(Integer::compareTo)
                .orElse(null);
    }

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
     * @param shopId   店家 ID（查 AI metadata）
     * @param shopName 店家名稱（品牌正規化用）
     * @param typeId   商店類型 ID（fallback）
     * @param score    評分（保留供未來規則擴充）
     * @param avgPrice tb_shop.avg_price（可為 null）
     */
    public Result evaluate(Long shopId, String shopName, Integer typeId, Integer score, Integer avgPrice) {
        // Priority 1: 同品牌 max avg_price（連鎖統一定價）
        Integer brandPrice = brandMaxAvgPrice(shopName);
        if (brandPrice != null && brandPrice > 0) {
            log.debug("[DepositPolicy] shop={} brand='{}' brandMaxPrice={}", shopId, normalizeBrand(shopName), brandPrice);
            return decideByPrice(brandPrice, "品牌統一人均 NT$ " + brandPrice);
        }

        // Priority 2: 本店 avg_price
        if (avgPrice != null && avgPrice > 0) {
            log.debug("[DepositPolicy] shop={} using own avg_price={}", shopId, avgPrice);
            return decideByPrice(avgPrice, "Google 顯示人均 NT$ " + avgPrice);
        }

        // Priority 3: ai_metadata.price_per_person
        ShopAiMetadataJpa ai = aiRepo.findById(shopId).orElse(null);
        String pricePerPerson = ai == null ? null : ai.getPricePerPerson();
        Integer maxPrice = extractMaxPrice(pricePerPerson);
        if (maxPrice != null) {
            log.debug("[DepositPolicy] shop={} using ai_price={}", shopId, maxPrice);
            return decideByPrice(maxPrice, "AI 推估人均 NT$ " + maxPrice);
        }

        // Priority 4: type_id + score 熱門高評分（連鎖常見類型）
        if (typeId != null && CONDITIONAL_DEPOSIT.contains(typeId)
                && score != null && score >= HIGH_SCORE_THRESHOLD) {
            double displayScore = score / 10.0;
            log.debug("[DepositPolicy] shop={} score-based deposit typeId={} score={}", shopId, typeId, score);
            return new Result(true, 300,
                    "熱門高評分餐廳（" + displayScore + " 分）、收取訂金", null);
        }

        // Priority 5: 高級類型 fallback
        log.debug("[DepositPolicy] shop={} fallback typeId={}", shopId, typeId);
        if (typeId != null && ALWAYS_DEPOSIT_FALLBACK.contains(typeId)) {
            return new Result(true, 500, "高級類型", null);
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
        Integer extractedPrice;
    }
}
