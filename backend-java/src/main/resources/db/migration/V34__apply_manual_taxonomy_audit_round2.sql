-- Apply the second 2026-06-09 manual taxonomy audit batch.

START TRANSACTION;

UPDATE tb_shop
SET type_id = CASE id
  WHEN 10427 THEN 2013 -- 泰滾 Rolling Thai 泰式火鍋(南京店）
  WHEN 10620 THEN 2002 -- 胖肚肚燒肉 大安店
  WHEN 10519 THEN 2013 -- 神燈搓一下
  WHEN 10226 THEN 2003 -- 酒米食堂chumi_canteen－北投店
  WHEN 10739 THEN 2010 -- 小紐約披薩 中山店
  WHEN 10361 THEN 2012 -- 詩篇咖啡餐廳Psalms Cafe & Restaurant
  WHEN 10442 THEN 2010 -- At.First早寓
  WHEN 10591 THEN 2003 -- 火人串燒
  WHEN 10231 THEN 2001 -- 三燔北投 Mihan Beitou
  WHEN 10449 THEN 2003 -- 阿薄郎薄皮餃子－公館店
  WHEN 10630 THEN 2003 -- 燒鳩 刺身•串燒•夜食
  WHEN 10631 THEN 2002 -- 哞屋Mon wo
  WHEN 10455 THEN 2004 -- 品田牧場 台北松山車站店
  ELSE type_id
END
WHERE id IN (
  10427, 10620, 10519, 10226, 10739, 10361, 10442,
  10591, 10231, 10449, 10630, 10631, 10455
);

INSERT IGNORE INTO tb_shop_tag (shop_id, tag_code)
VALUES
  (10427, '泰式'),
  (10519, '印度'),
  (10519, '中東'),
  (10538, '吃到飽');

COMMIT;
