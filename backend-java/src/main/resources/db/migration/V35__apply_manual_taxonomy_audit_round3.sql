-- Apply the third 2026-06-09 manual taxonomy audit batch.

START TRANSACTION;

UPDATE tb_shop
SET type_id = CASE id
  WHEN 10572 THEN 2003 -- Chill嗨嗨酒場 Bar
  WHEN 10599 THEN 2003 -- 士林串燒
  WHEN 10464 THEN 2005 -- PRESERVE LaLaport 南港店
  WHEN 10550 THEN 2001 -- Extension 1 by 橘色
  WHEN 10691 THEN 2004 -- Eatfoodie udon 好好吃餐房
  WHEN 10558 THEN 2008 -- 根來阿財鐵板燒
  WHEN 10757 THEN 2003 -- 爍場居酒屋復興店
  WHEN 10641 THEN 2004 -- 東京家庭義大利麵 堺人餐飲 天母
  WHEN 10695 THEN 2007 -- 試試工作室
  WHEN 10562 THEN 2004 -- HANNA Pasta Cafe
  WHEN 10566 THEN 2001 -- 鍋董日式涮涮鍋劍潭旗艦店
  WHEN 10607 THEN 2003 -- 大河屋 燒肉丼 串燒-微風南京店
  WHEN 10478 THEN 2008 -- 麥味登 文山饗食大亨店
  WHEN 10649 THEN 2004 -- 大河牧場 漢堡排洋食館-內湖大全聯店
  WHEN 10241 THEN 2012 -- 貓蕊 貓咪餐廳
  ELSE type_id
END
WHERE id IN (
  10572, 10599, 10464, 10550, 10691, 10558, 10757, 10641,
  10695, 10562, 10566, 10607, 10478, 10649, 10241
);

INSERT IGNORE INTO tb_shop_tag (shop_id, tag_code)
VALUES
  (10478, '早午餐');

COMMIT;
