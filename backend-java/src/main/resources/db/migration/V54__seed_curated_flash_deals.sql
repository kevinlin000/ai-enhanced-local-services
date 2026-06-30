-- Curated flash-deal demo set for portfolio screenshots.
-- Idempotent seed only: no deletes, no truncates, no updates to existing orders.

INSERT IGNORE INTO tb_voucher (id, shop_id, title, sub_title, rules, pay_value, actual_value, type, status)
VALUES
(30106, 10113, 'KiKi 信義雙人餐券', '限時 75 折', '限當月使用；需提前訂位；不可與其他優惠併用', 120000, 160000, 1, 1),
(30107, 10115, '辛殿信義火鍋餐券', '雙人套餐 8 折', '限晚餐離峰時段；需提前訂位', 150000, 188000, 1, 1),
(30108, 10116, '刁民酸菜魚分享券', '四人聚餐折抵', '限內用；熱門時段數量有限', 96000, 128000, 1, 1),
(30109, 10111, '鼎泰豐家庭餐券', '家庭聚餐折抵', '限內用；需依現場候位狀況入座', 200000, 240000, 1, 1),
(30110, 10598, '香旬日式料理餐券', '雙人晚餐 7 折', '限指定套餐；需提前訂位', 105000, 150000, 1, 1),
(30111, 10225, '吟鮮熱炒聚餐券', '多人聚餐折抵', '限內用；酒水另計', 72000, 100000, 1, 1),
(30112, 10610, 'Lazy Pasta 義式餐券', '雙人主餐折抵', '限平日；需提前訂位', 56000, 80000, 1, 1),
(30113, 10673, '光司DATE 約會餐券', '雙人義式套餐', '限晚餐；需提前訂位', 50000, 76000, 1, 1),
(30114, 10709, '蔬食約會餐券', '雙人套餐 8 折', '限內用；需提前訂位', 68000, 85000, 1, 1),
(30115, 10404, '大安候位測試餐券', '熱門時段折抵', '限 demo 測試；額滿可開空位通知', 45000, 70000, 1, 1),
(30116, 10108, '信義咖啡甜點券', '午後雙人組合', '限下午時段；每日數量有限', 42000, 60000, 1, 1),
(30117, 10102, '海底撈停車友善餐券', '家庭鍋物折抵', '適合開車用餐；需提前訂位', 160000, 200000, 1, 1),
(30118, 10573, '豆町村燒肉餐券', '雙人燒肉折抵', '限晚餐；需提前訂位', 118000, 160000, 1, 1),
(30119, 10205, '青花驕麻辣鍋餐券', '雙人鍋物 8 折', '限內用；熱門時段數量有限', 140000, 175000, 1, 1),
(30120, 10103, '旭集限時雙人餐券', '雙人 5 折秒殺', '限 50 名；需提前訂位', 75000, 150000, 1, 1);

INSERT IGNORE INTO tb_seckill_voucher (voucher_id, stock, begin_time, end_time)
VALUES
(30106, 36, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30107, 28, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30108, 32, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30109, 24, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30110, 20, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30111, 45, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30112, 40, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30113, 30, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30114, 26, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30115, 18, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30116, 50, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30117, 35, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30118, 30, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30119, 30, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30120, 50, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY));
