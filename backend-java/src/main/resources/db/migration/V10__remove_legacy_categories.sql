-- 把舊分類 1001-1012 + 1-10（黑馬點評殘留）整批清掉
-- 因為已無 active shop 引用、可安全刪除
DELETE FROM tb_shop_type WHERE id BETWEEN 1 AND 10;
DELETE FROM tb_shop_type WHERE id BETWEEN 1001 AND 1012;
