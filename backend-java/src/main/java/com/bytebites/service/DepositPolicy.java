package com.bytebites.service;

import org.springframework.stereotype.Service;
import java.util.Set;

/**
 * 訂金政策：依店家分類與評分決定是否需要預付訂金。
 *
 * 規則：
 * - ALWAYS_DEPOSIT：高級餐廳(2011)、無菜單料理(2005) → 一律收訂金
 * - CONDITIONAL_DEPOSIT：火鍋(2001)、日式燒肉(2002)、日式料理(2004)、牛排館(2006)
 *   → score >= 46（i.e. 4.6/5.0）才收訂金
 * - 其他分類 → 免訂金
 *
 * score 欄位以整數 ×10 儲存（DB: 46 = 4.6 星）。
 */
@Service
public class DepositPolicy {

    private static final Set<Integer> ALWAYS_DEPOSIT = Set.of(2011, 2005);
    private static final Set<Integer> CONDITIONAL_DEPOSIT = Set.of(2001, 2002, 2004, 2006);
    private static final int HIGH_SCORE_THRESHOLD = 46; // score 4.6+

    public boolean needsDeposit(Integer typeId, Integer score) {
        if (typeId == null) return false;
        if (ALWAYS_DEPOSIT.contains(typeId)) return true;
        if (CONDITIONAL_DEPOSIT.contains(typeId) && score != null && score >= HIGH_SCORE_THRESHOLD) {
            return true;
        }
        return false;
    }

    public int depositPerPerson(Integer typeId) {
        if (typeId == null) return 0;
        if (typeId == 2011) return 500;  // 高級餐廳
        if (typeId == 2005) return 1000; // 無菜單料理（Omakase）
        if (CONDITIONAL_DEPOSIT.contains(typeId)) return 300;
        return 0;
    }

    public String reason(Integer typeId, Integer score) {
        if (typeId == null) return "免訂金";
        if (typeId == 2011) return "高級餐廳一律收取訂金";
        if (typeId == 2005) return "無菜單料理一律收取訂金";
        if (CONDITIONAL_DEPOSIT.contains(typeId) && score != null && score >= HIGH_SCORE_THRESHOLD) {
            return "高評分熱門餐廳收取訂金";
        }
        return "免訂金";
    }
}
