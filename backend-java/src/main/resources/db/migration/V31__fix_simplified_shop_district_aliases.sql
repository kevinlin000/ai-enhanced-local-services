-- Extend V30 for addresses that simplify the district name itself, not only "區" -> "区".
UPDATE tb_shop
SET
    district = CASE
        WHEN address LIKE '%万华区%' THEN '萬華'
        WHEN address LIKE '%信義区%' OR address LIKE '%信义区%' THEN '信義'
        WHEN address LIKE '%內湖区%' OR address LIKE '%内湖区%' THEN '內湖'
        ELSE district
    END,
    area = CASE
        WHEN address LIKE '%万华区%' THEN '萬華'
        WHEN address LIKE '%信義区%' OR address LIKE '%信义区%' THEN '信義'
        WHEN address LIKE '%內湖区%' OR address LIKE '%内湖区%' THEN '內湖'
        ELSE area
    END,
    update_time = NOW()
WHERE address IS NOT NULL
  AND (
    address LIKE '%万华区%'
    OR address LIKE '%信義区%' OR address LIKE '%信义区%'
    OR address LIKE '%內湖区%' OR address LIKE '%内湖区%'
  );
