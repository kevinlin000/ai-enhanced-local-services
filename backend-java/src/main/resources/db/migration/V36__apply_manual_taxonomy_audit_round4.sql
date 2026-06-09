-- Apply the fourth 2026-06-09 manual taxonomy audit batch.

START TRANSACTION;

UPDATE tb_shop
SET type_id = CASE id
  WHEN 10612 THEN 2012 -- JODA CAFE 松山八德店
  WHEN 10491 THEN 2004 -- 九井自慢料理
  WHEN 10334 THEN 2012 -- 三亞米
  WHEN 10721 THEN 2012 -- 糧田
  WHEN 10725 THEN 2003 -- 一肚子火 串燒
  WHEN 10130 THEN 2013 -- MAJI MAJI集食行樂
  WHEN 10262 THEN 2004 -- 吉豚屋 石牌店
  WHEN 10441 THEN 2012 -- Mr. 雪腐 公館店
  WHEN 10279 THEN 2012 -- 女巫店
  WHEN 10444 THEN 2012 -- 三角冰冰品專賣店
  WHEN 10686 THEN 2004 -- 勝魂丼飯專門店（丼飯.咖哩）
  WHEN 10602 THEN 2004 -- 雲の咖哩屋
  WHEN 10699 THEN 2004 -- 晴天廚房
  WHEN 10400 THEN 2013 -- mama says yes 大馬人 | 內湖本店
  WHEN 10324 THEN 2004 -- 巧主廚的咖哩-萬芳總站
  WHEN 10667 THEN 2010 -- Haooyun Station 好運站
  ELSE type_id
END
WHERE id IN (
  10612, 10491, 10334, 10721, 10725, 10130, 10262, 10441,
  10279, 10444, 10686, 10602, 10699, 10400, 10324, 10667
);

COMMIT;
