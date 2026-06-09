-- Finish the 2026-06-09 manual taxonomy audit and remove misleading Korean tags.

START TRANSACTION;

UPDATE tb_shop
SET type_id = CASE id
  WHEN 10611 THEN 2012 -- 花嶼輕食館Flower Island Brunch
  WHEN 10709 THEN 2005 -- 知初植物系永續廚房
  WHEN 10113 THEN 2008 -- KiKi餐廳（ATT 4 FUN信義店）
  WHEN 10579 THEN 2002 -- 燒肉眾精緻炭火燒肉 台北西門店
  WHEN 10158 THEN 2007 -- 大樹先生的家
  WHEN 10382 THEN 2002 -- 神來一爐燒肉民生店
  WHEN 10648 THEN 2002 -- IKIGAI燒肉專門店-微風百貨店
  WHEN 10485 THEN 2012 -- 蘋果肉桂 Café & Bistro
  ELSE type_id
END
WHERE id IN (10611, 10709, 10113, 10579, 10158, 10382, 10648, 10485);

DELETE FROM tb_shop_tag
WHERE tag_code = '韓式'
  AND shop_id IN (
    10579, -- 燒肉眾精緻炭火燒肉 台北西門店
    10158, -- 大樹先生的家
    10382, -- 神來一爐燒肉民生店
    10648, -- IKIGAI燒肉專門店-微風百貨店
    10485  -- 蘋果肉桂 Café & Bistro
  );

COMMIT;
