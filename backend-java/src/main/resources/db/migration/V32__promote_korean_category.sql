-- Promote Korean from cuisine tag to primary category.
-- Keep the 韓式 tag for compatibility and mixed-format search, but use 2009/korean
-- when the restaurant identity is clearly Korean.

START TRANSACTION;

INSERT INTO tb_shop_type (id, name, slug, icon, sort, is_active, create_time, update_time)
VALUES (2009, '韓式料理', 'korean', '/icons/korean.png', 4, 1, NOW(), NOW())
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
  WHEN 2007 THEN 5
  WHEN 2012 THEN 6
  WHEN 2002 THEN 7
  WHEN 2011 THEN 8
  WHEN 2005 THEN 9
  WHEN 2003 THEN 10
  WHEN 2004 THEN 11
  ELSE sort
END,
is_active = CASE WHEN id = 2009 THEN 1 ELSE is_active END,
update_time = NOW()
WHERE id IN (2008, 2001, 2010, 2009, 2007, 2012, 2002, 2011, 2005, 2003, 2004);

UPDATE tb_shop
SET type_id = 2009
WHERE id IN (
  10165, -- 梨谷韓式鐵板烤肉 忠孝總店
  10190, -- 弘大一號出口
  10209, -- 金咕친구 韓式原塊烤肉 台北西門店
  10218, -- 금하동(金河洞-韓式烤肉專門店)
  10259, -- 新山韓國烤肉
  10271, -- UNCLE-K 排骨火鍋店
  10349, -- 本家BORNGA韓式燒肉 敦南店
  10353, -- 金書西餐飲 韓國豬肉湯飯 돼지국밥
  10356, -- 金孫韓廚 義大利麵(士林店)
  10380, -- Uncle-K 火烤店 아저씨감자탕
  10435, -- 四米大石鍋拌飯專賣
  10438, -- 東大門韓國特色料理
  10443, -- 金孫韓廚 義大利麵 (中山店)
  10501, -- 恰恰韓式豬腳
  10513, -- 新村站著吃烤肉 台北市府店
  10568  -- 韓大佬
);

COMMIT;
