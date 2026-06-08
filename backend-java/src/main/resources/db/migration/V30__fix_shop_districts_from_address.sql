-- Prefer the real address district over crawler target district.
-- Some Google addresses use simplified "区", e.g. "中山区", so handle both variants.
UPDATE tb_shop
SET
    district = CASE
        WHEN address LIKE '%中正區%' OR address LIKE '%中正区%' THEN '中正'
        WHEN address LIKE '%大同區%' OR address LIKE '%大同区%' THEN '大同'
        WHEN address LIKE '%中山區%' OR address LIKE '%中山区%' THEN '中山'
        WHEN address LIKE '%松山區%' OR address LIKE '%松山区%' THEN '松山'
        WHEN address LIKE '%大安區%' OR address LIKE '%大安区%' THEN '大安'
        WHEN address LIKE '%萬華區%' OR address LIKE '%萬华区%' THEN '萬華'
        WHEN address LIKE '%信義區%' OR address LIKE '%信义区%' THEN '信義'
        WHEN address LIKE '%士林區%' OR address LIKE '%士林区%' THEN '士林'
        WHEN address LIKE '%北投區%' OR address LIKE '%北投区%' THEN '北投'
        WHEN address LIKE '%內湖區%' OR address LIKE '%内湖区%' THEN '內湖'
        WHEN address LIKE '%南港區%' OR address LIKE '%南港区%' THEN '南港'
        WHEN address LIKE '%文山區%' OR address LIKE '%文山区%' THEN '文山'
        ELSE district
    END,
    area = CASE
        WHEN address LIKE '%中正區%' OR address LIKE '%中正区%' THEN '中正'
        WHEN address LIKE '%大同區%' OR address LIKE '%大同区%' THEN '大同'
        WHEN address LIKE '%中山區%' OR address LIKE '%中山区%' THEN '中山'
        WHEN address LIKE '%松山區%' OR address LIKE '%松山区%' THEN '松山'
        WHEN address LIKE '%大安區%' OR address LIKE '%大安区%' THEN '大安'
        WHEN address LIKE '%萬華區%' OR address LIKE '%萬华区%' THEN '萬華'
        WHEN address LIKE '%信義區%' OR address LIKE '%信义区%' THEN '信義'
        WHEN address LIKE '%士林區%' OR address LIKE '%士林区%' THEN '士林'
        WHEN address LIKE '%北投區%' OR address LIKE '%北投区%' THEN '北投'
        WHEN address LIKE '%內湖區%' OR address LIKE '%内湖区%' THEN '內湖'
        WHEN address LIKE '%南港區%' OR address LIKE '%南港区%' THEN '南港'
        WHEN address LIKE '%文山區%' OR address LIKE '%文山区%' THEN '文山'
        ELSE area
    END,
    update_time = NOW()
WHERE address IS NOT NULL
  AND (
    address LIKE '%中正區%' OR address LIKE '%中正区%'
    OR address LIKE '%大同區%' OR address LIKE '%大同区%'
    OR address LIKE '%中山區%' OR address LIKE '%中山区%'
    OR address LIKE '%松山區%' OR address LIKE '%松山区%'
    OR address LIKE '%大安區%' OR address LIKE '%大安区%'
    OR address LIKE '%萬華區%' OR address LIKE '%萬华区%'
    OR address LIKE '%信義區%' OR address LIKE '%信义区%'
    OR address LIKE '%士林區%' OR address LIKE '%士林区%'
    OR address LIKE '%北投區%' OR address LIKE '%北投区%'
    OR address LIKE '%內湖區%' OR address LIKE '%内湖区%'
    OR address LIKE '%南港區%' OR address LIKE '%南港区%'
    OR address LIKE '%文山區%' OR address LIKE '%文山区%'
  );
