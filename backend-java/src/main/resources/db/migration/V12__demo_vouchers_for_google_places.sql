-- Demo user for X-Demo-Mode header testing
INSERT INTO tb_user (id, phone, nick_name)
VALUES (1001, '00000001001', 'DemoUser')
ON DUPLICATE KEY UPDATE nick_name = 'DemoUser';

-- 普通 vouchers (type=0) for popular shops
INSERT IGNORE INTO tb_voucher (id, shop_id, title, sub_title, rules, pay_value, actual_value, type, status)
VALUES
(30001, 10102, '海底撈雙人鍋物',    '雙人套餐 9 折',  '限平日中午',       90000,  100000, 0, 1),
(30002, 10115, '辛殿麻辣鍋雙人',    '雙人吃到飽',      '需提前預約',      168000,  180000, 0, 1),
(30003, 10099, '一蘭拉麵套餐',      '拉麵+小菜+飲料',  '一人一份',         38000,   42000, 0, 1),
(30004, 10101, '鼎泰豐家庭套餐',    '四人份',          '限定平日晚餐',    280000,  320000, 0, 1),
(30005, 10104, '饗饗 INPARADISE',  '雙人吃到飽',      '高峰時段需排隊',   268000,  298000, 0, 1);

-- 秒殺 vouchers (type=1) — stock tracked in tb_seckill_voucher
INSERT IGNORE INTO tb_voucher (id, shop_id, title, sub_title, rules, pay_value, actual_value, type, status)
VALUES
(30101, 10103, '旭集熱座限定',       '雙人 5 折秒殺',   '僅限 50 名',       75000,  150000, 1, 1),
(30102, 10125, '夏慕尼鐵板燒',       '雙人 7 折熱座',   '需 2 小時前訂',   110000,  158000, 1, 1),
(30103, 10135, '榮榮園商務套餐',     '6 折特惠',        '限商務午餐',       60000,  100000, 1, 1),
(30104, 10119, '欣葉台菜秒殺',       '單人 5 折',       '限時優惠',         25000,   50000, 1, 1),
(30105, 10144, '二本松涮涮屋熱座',   '雙人 7 折',       '熱門時段秒殺',     84000,  120000, 1, 1);

-- Seckill inventory (begin/end time managed separately)
INSERT IGNORE INTO tb_seckill_voucher (voucher_id, stock, begin_time, end_time)
VALUES
(30101, 50, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30102, 30, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30103, 20, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30104, 80, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY)),
(30105, 40, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY));
