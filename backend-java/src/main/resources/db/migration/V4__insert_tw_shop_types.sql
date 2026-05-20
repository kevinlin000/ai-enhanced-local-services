-- V4: replace shop types with taiwan-localized categories
-- existing rows from V1 will be soft-deleted (is_active=0) to preserve referential integrity;
-- new taiwan categories inserted with explicit IDs starting from 1001

-- soft delete original heima dianping categories
UPDATE tb_shop_type SET is_active = 0 WHERE id < 1000;

-- insert taiwan-localized categories
-- 注意:icon path 暫時用 placeholder,B4 / 之後會放真實圖示
INSERT INTO tb_shop_type (id, name, icon, slug, sort, is_active, create_time, update_time) VALUES
    (1001, '牛肉麵',      '/icons/beef-noodle.png',     'beef-noodle',      1,  1, NOW(), NOW()),
    (1002, '滷味小吃',    '/icons/lu-wei.png',          'lu-wei',           2,  1, NOW(), NOW()),
    (1003, '手搖飲',      '/icons/bubble-tea.png',      'bubble-tea',       3,  1, NOW(), NOW()),
    (1004, '夜市小吃',    '/icons/night-market.png',    'night-market',     4,  1, NOW(), NOW()),
    (1005, '咖啡輕食',    '/icons/cafe.png',            'cafe',             5,  1, NOW(), NOW()),
    (1006, '日式料理',    '/icons/japanese.png',        'japanese',         6,  1, NOW(), NOW()),
    (1007, '韓式料理',    '/icons/korean.png',          'korean',           7,  1, NOW(), NOW()),
    (1008, '燒烤居酒屋',  '/icons/izakaya.png',         'izakaya',          8,  1, NOW(), NOW()),
    (1009, '火鍋',        '/icons/hotpot.png',          'hotpot',           9,  1, NOW(), NOW()),
    (1010, '早餐店',      '/icons/breakfast.png',       'breakfast',       10,  1, NOW(), NOW()),
    (1011, '便當自助餐',  '/icons/bento.png',           'bento',           11,  1, NOW(), NOW()),
    (1012, '甜點冰品',    '/icons/dessert.png',         'dessert',         12,  1, NOW(), NOW());
