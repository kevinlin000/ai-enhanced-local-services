# Taxonomy Audit

- Unique shops scanned: 600
- Audit rows: 8
- Korean-tagged rows needing review: 5

## Category Distribution

- 2001 火鍋: 88
- 2002 日式燒肉: 57
- 2003 居酒屋: 68
- 2004 日式料理: 78
- 2005 素食: 26
- 2007 義法料理: 78
- 2008 中式料理: 79
- 2009 韓式料理: 16
- 2010 美式料理: 50
- 2011 自助餐: 8
- 2012 咖啡/甜點: 42
- 2013 異國料理: 10

## Tag Distribution

- 約會: 153
- 親子: 152
- 義式: 76
- 餐酒館: 35
- 牛排: 34
- 商務: 33
- 早午餐: 25
- 吃到飽: 23
- 韓式: 20
- 法式: 18
- 泰式: 12
- 景觀: 11
- Brunch: 11
- 中東: 8
- 鐵板燒: 7
- 印度: 6
- 包廂: 3

## Flag Distribution

- high_impact: 7
- korean_tag_review: 5
- keyword_conflict: 2
- defaulted_to_chinese: 1

## Recommendation

- Keep `日式料理` as a Japanese-only primary category.
- Use `韓式料理` as a dedicated primary category for clearly Korean restaurants.
- Use `異國料理` for Indian, Thai, Middle Eastern, Vietnamese, Mexican, and similar cuisines instead of forcing them into `中式料理` or `義法料理`.
- Keep the `韓式` tag for compatibility and mixed-format restaurants, but do not use `日韓料理` as a combined category.
- Review high-priority rows first, then add classifier overrides or DB migrations for confirmed fixes.

## Top 8 Review Rows

| priority | shop_id | name | category | tags | flags | suggestion | evidence |
| ---: | ---: | --- | --- | --- | --- | --- | --- |
| 45 | 10611 | 花嶼輕食館Flower Island Brunch-台北士林站輕食早午餐/下午茶/咖啡廳 異國料理/義大利麵/燉飯/創意料理 親子/寵物友善 聚餐/慶生/約會/網美 2026熱門訂位評價推薦 PTT Dcard threads | 美式料理 | Brunch、早午餐、義式、約會、親子 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利、燉飯 | 義法料理:義大利麵、義大利、燉飯; 咖啡/甜點:下午茶、蛋糕、甜點、咖啡、拿鐵 |
| 45 | 10709 | 知初植物系永續廚房（Last order time is 14:15 / 20:00） | 素食 |  | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：披薩 | 義法料理:披薩 |
| 30 | 10113 | KiKi餐廳（ATT 4 FUN信義店） | 中式料理 | 親子、景觀 | defaulted_to_chinese | 人工確認主分類 | 坐落於 ATT 4 FUN 的 KiKi 餐廳，擁有開闊的落地窗景觀，能將信義區繁華盡收眼底。餐廳空間設計寬敞舒適，步入其中便能感受到明亮且現代的用餐環境，十分適合朋友與家人聚餐。這裡的出餐節奏明快，服務人員在忙碌中仍能維持補水頻率，整體用餐節奏流暢。招牌老皮嫩肉炸得外酥內軟，吸滿醬汁後的口感層次分明；而蒼蠅頭則帶有鮮明的韭菜香氣與脆口碎肉，相當下飯。雖然部分菜色調味因師傅手法或個人口味差異，偶有濃淡不一的反饋，但整體餐點精緻且份... |
| 22 | 10579 | 燒肉眾精緻炭火燒肉 台北西門店 | 日式燒肉 | 韓式 | korean_tag_review;high_impact | 保留分類，確認 tags 是否完整 | 韓式 tag |
| 22 | 10158 | 大樹先生的家 | 義法料理 | 親子 | korean_tag_review;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 韓式 tag |
| 22 | 10382 | 神來一爐燒肉民生店 | 日式燒肉 | 韓式 | korean_tag_review;high_impact | 保留分類，確認 tags 是否完整 | 韓式 tag |
| 22 | 10648 | IKIGAI燒肉專門店-微風百貨店 | 日式燒肉 | 韓式、約會、親子 | korean_tag_review;high_impact | 保留分類，確認 tags 是否完整 | 韓式 tag |
| 22 | 10485 | 蘋果肉桂 Café & Bistro | 咖啡/甜點 | 早午餐、韓式、義式、餐酒館、約會 | korean_tag_review;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利 | 韓式 tag |
