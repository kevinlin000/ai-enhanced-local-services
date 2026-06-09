-- Apply the 2026-06-09 manual taxonomy audit.
-- Keep cuisine identity in tb_shop.type_id, and use tags for secondary cuisine signals.

START TRANSACTION;

INSERT INTO tb_shop_type (id, name, slug, icon, sort, is_active, create_time, update_time)
VALUES (2013, '異國料理', 'international', '/icons/international.png', 5, 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  slug = VALUES(slug),
  icon = VALUES(icon),
  sort = VALUES(sort),
  is_active = VALUES(is_active),
  update_time = NOW();

UPDATE tb_shop_type
SET sort = CASE id
  WHEN 2008 THEN 1
  WHEN 2001 THEN 2
  WHEN 2010 THEN 3
  WHEN 2009 THEN 4
  WHEN 2013 THEN 5
  WHEN 2007 THEN 6
  WHEN 2012 THEN 7
  WHEN 2002 THEN 8
  WHEN 2011 THEN 9
  WHEN 2005 THEN 10
  WHEN 2003 THEN 11
  WHEN 2004 THEN 12
  ELSE sort
END,
is_active = CASE WHEN id = 2013 THEN 1 ELSE is_active END,
update_time = NOW()
WHERE id IN (2008, 2001, 2010, 2009, 2013, 2007, 2012, 2002, 2011, 2005, 2003, 2004);

INSERT INTO tb_tag_def (code, display_name, sort, is_active, create_time, update_time)
VALUES
  ('印度', '印度', 17, 1, NOW(), NOW()),
  ('泰式', '泰式', 18, 1, NOW(), NOW()),
  ('中東', '中東', 19, 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE
  display_name = VALUES(display_name),
  sort = VALUES(sort),
  is_active = VALUES(is_active),
  update_time = NOW();

UPDATE tb_shop
SET type_id = CASE id
  WHEN 10338 THEN 2007 -- 青青食尚花園會館
  WHEN 10342 THEN 2004 -- 溫咖哩 Wen Curry
  WHEN 10731 THEN 2010 -- 瀧厚炙燒熟成牛排 台北.北車店
  WHEN 10514 THEN 2007 -- 沾美西餐廳
  WHEN 10735 THEN 2007 -- SALT&STONE 台北101餐廳
  WHEN 10431 THEN 2007 -- 樂野食
  WHEN 10520 THEN 2004 -- 北投文物館
  WHEN 10740 THEN 2007 -- 大嗑西式餐館
  WHEN 10530 THEN 2007 -- 莎諾西餐
  WHEN 10291 THEN 2007 -- 士林放感情餐酒館
  WHEN 10457 THEN 2007 -- 頁小館
  WHEN 10377 THEN 2004 -- 築本屋公館店
  WHEN 10461 THEN 2011 -- 泰市場 大直英迪格店
  WHEN 10299 THEN 2004 -- Moni咖哩
  WHEN 10751 THEN 2012 -- KOBE SWEETS CAFE 神戶果実 微風南山
  WHEN 10752 THEN 2002 -- 蘭亭燒肉
  WHEN 10759 THEN 2012 -- 茶茶王國
  WHEN 10480 THEN 2007 -- 波 WAVE 鷹嘴豆泥屋 Hummus House
  WHEN 10654 THEN 2007 -- 夏綠沁私房義大利麵燉飯
  WHEN 10329 THEN 2004 -- 東京廚房
  WHEN 10717 THEN 2004 -- 詹咖李
  WHEN 10503 THEN 2007 -- Tierra Casa Restaurant
  WHEN 10158 THEN 2007 -- 大樹先生的家
  WHEN 10625 THEN 2004 -- 大河牧場 漢堡排專売-南港環球店
  WHEN 10559 THEN 2004 -- 大叔食事
  WHEN 10646 THEN 2004 -- ONE GOOD烤肉飯
  WHEN 10252 THEN 2002 -- 山上走走 日式燒肉台北華山店
  WHEN 10617 THEN 2004 -- 歐買尬日式海鮮串燒 市民一店
  WHEN 10669 THEN 2002 -- 熊一頂級燒肉-西門二店
  WHEN 10730 THEN 2002 -- 燒肉神保町信義館
  WHEN 10428 THEN 2001 -- 好食多涮涮鍋 雙城店
  WHEN 10490 THEN 2013 -- 亞瑟蘭印度餐廳
  WHEN 10308 THEN 2013 -- 馬友友印度廚房內湖店
  WHEN 10211 THEN 2013 -- 莎瓦迪卡海鮮.泰
  WHEN 10525 THEN 2013 -- 初泰Pikul
  WHEN 10352 THEN 2013 -- 塔吉摩洛哥料理
  WHEN 10546 THEN 2013 -- 非常泰
  ELSE type_id
END
WHERE id IN (
  10338, 10342, 10731, 10514, 10735, 10431, 10520, 10740, 10530, 10291,
  10457, 10377, 10461, 10299, 10751, 10752, 10759, 10480, 10654, 10329,
  10717, 10503, 10158, 10625, 10559, 10646, 10252, 10617, 10669, 10730,
  10428, 10490, 10308, 10211, 10525, 10352, 10546
);

INSERT IGNORE INTO tb_shop_tag (shop_id, tag_code)
VALUES
  (10490, '印度'),
  (10308, '印度'),
  (10211, '泰式'),
  (10525, '泰式'),
  (10546, '泰式'),
  (10352, '中東'),
  (10480, '中東');

DELETE FROM tb_shop_tag
WHERE tag_code = '韓式'
  AND shop_id IN (
    10347, -- TankQ cafe&Bar
    10671, -- 燒肉中山
    10622, -- 樂軒松阪亭
    10588, -- 發肉燒肉餐酒忠孝二店
    10625, -- 大河牧場 漢堡排專売-南港環球店
    10559, -- 大叔食事
    10646, -- ONE GOOD烤肉飯
    10177, -- 小尚品精制鍋物
    10726, -- 小蔬同手作蔬食
    10245, -- 和牛涮台北忠孝東店
    10616  -- 金洹苑
  );

COMMIT;
