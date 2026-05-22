-- 加 tb_shop 軟刪除欄位
ALTER TABLE tb_shop
    ADD COLUMN is_active TINYINT NOT NULL DEFAULT 1 COMMENT '1=啟用、0=軟刪除';

-- 把舊種子 25 家 + 黑馬點評 14 家全部軟刪除
UPDATE tb_shop SET is_active = 0;

-- 新增 12 個 inline 對標分類
INSERT INTO tb_shop_type (id, name, slug, icon, sort) VALUES
(2001, '火鍋', 'hotpot', '/icons/hotpot.png', 1),
(2002, '日式燒肉', 'yakiniku', '/icons/yakiniku.png', 2),
(2003, '居酒屋', 'izakaya', '/icons/izakaya.png', 3),
(2004, '日式料理', 'japanese', '/icons/japanese.png', 4),
(2005, '無菜單料理', 'omakase', '/icons/omakase.png', 5),
(2006, '牛排館', 'steakhouse', '/icons/steakhouse.png', 6),
(2007, '義法料理', 'european', '/icons/european.png', 7),
(2008, '中式料理', 'chinese', '/icons/chinese.png', 8),
(2009, '韓式料理', 'korean', '/icons/korean.png', 9),
(2010, '美式 / Brunch', 'brunch', '/icons/brunch.png', 10),
(2011, '高級餐廳', 'fine-dining', '/icons/fine-dining.png', 11),
(2012, '特色咖啡', 'cafe-premium', '/icons/cafe-premium.png', 12);
