-- Rename demo seckill vouchers from the old HotSeat wording to user-facing flash deals.
-- Targeted by fixed demo IDs only; no stock, order, or user data is modified.
UPDATE tb_voucher
SET title = CASE id
        WHEN 30101 THEN '旭集限時雙人餐券'
        WHEN 30102 THEN '夏慕尼限時雙人餐券'
        WHEN 30103 THEN '橘色涮涮屋限時餐券'
        WHEN 30104 THEN '一幻拉麵限時餐券'
        WHEN 30105 THEN '二本松限時雙人餐券'
        ELSE title
    END,
    sub_title = CASE id
        WHEN 30101 THEN '雙人 5 折秒殺'
        WHEN 30102 THEN '雙人 7 折限量'
        WHEN 30103 THEN '午間套餐限量'
        WHEN 30104 THEN '晚餐拉麵組合'
        WHEN 30105 THEN '雙人 7 折限量'
        ELSE sub_title
    END,
    rules = CASE id
        WHEN 30101 THEN '限量 50 張；每人限搶 1 張'
        WHEN 30102 THEN '需 2 小時前使用；每人限搶 1 張'
        WHEN 30103 THEN '限內用；每人限搶 1 張'
        WHEN 30104 THEN '平日晚餐使用；每人限搶 1 張'
        WHEN 30105 THEN '熱門時段限量；每人限搶 1 張'
        ELSE rules
    END
WHERE id IN (30101, 30102, 30103, 30104, 30105);
