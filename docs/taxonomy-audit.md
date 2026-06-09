# Taxonomy Audit

- Unique shops scanned: 600
- Audit rows: 328
- Korean-tagged rows needing review: 14

## Category Distribution

- 2001 火鍋: 87
- 2002 日式燒肉: 54
- 2003 居酒屋: 59
- 2004 日式料理: 73
- 2005 素食: 26
- 2007 義法料理: 70
- 2008 中式料理: 117
- 2009 韓式料理: 16
- 2010 美式料理: 59
- 2011 自助餐: 7
- 2012 咖啡/甜點: 32

## Tag Distribution

- 約會: 156
- 親子: 155
- 義式: 76
- 餐酒館: 35
- 商務: 34
- 牛排: 34
- 韓式: 29
- 早午餐: 24
- 吃到飽: 22
- 法式: 18
- 景觀: 11
- Brunch: 11
- 鐵板燒: 7
- 包廂: 3

## Flag Distribution

- high_impact: 327
- keyword_conflict: 283
- defaulted_to_chinese: 69
- korean_tag_review: 14

## Recommendation

- Keep `日式料理` as a Japanese-only primary category.
- Use `韓式料理` as a dedicated primary category for clearly Korean restaurants.
- Keep the `韓式` tag for compatibility and mixed-format restaurants, but do not use `日韓料理` as a combined category.
- Review high-priority rows first, then add classifier overrides or DB migrations for confirmed fixes.

## Top 80 Review Rows

| priority | shop_id | name | category | tags | flags | suggestion | evidence |
| ---: | ---: | --- | --- | --- | --- | --- | --- |
| 75 | 10338 | 青青食尚花園會館 | 中式料理 | 約會、景觀 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉; 咖啡/甜點:下午茶 |
| 75 | 10342 | 溫咖哩 Wen Curry | 中式料理 | 牛排、約會 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排 |
| 75 | 10731 | 瀧厚炙燒熟成牛排 台北.北車店 | 中式料理 | 牛排、親子 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排 |
| 75 | 10514 | 沾美西餐廳 | 中式料理 | 牛排、吃到飽、約會 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排; 自助餐:buffet、自助餐; 咖啡/甜點:蛋糕 |
| 75 | 10735 | SALT&STONE 台北101餐廳 | 中式料理 | 約會 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 義法料理 (2007)；命中：披薩、燉飯 | 義法料理:披薩、燉飯 |
| 75 | 10431 | 樂野食 | 中式料理 | 約會、親子 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 義法料理 (2007)；命中：燉飯 | 義法料理:燉飯 |
| 75 | 10520 | 北投文物館 | 中式料理 | 約會 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：下午茶 | 咖啡/甜點:下午茶 |
| 75 | 10436 | 秦味館 Qin Wei Guan | 中式料理 |  | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 75 | 10148 | 孫立人將軍官邸（陸軍聯誼廳） | 中式料理 | 包廂、商務 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 75 | 10740 | 大嗑西式餐館 | 中式料理 | 牛排、法式、約會 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式、燉飯 | 義法料理:法式、燉飯; 美式料理:牛排 |
| 75 | 10530 | 莎諾西餐 | 中式料理 | 約會、親子 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 75 | 10291 | 士林放感情餐酒館 士林區餐廳 台北餐酒館 酒吧 活動派對 生日包場 企業包場 | 中式料理 | 餐酒館、約會 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：酒吧 | 居酒屋:酒吧 |
| 75 | 10147 | 泰和樓 | 中式料理 | 親子 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 火鍋 (2001)；命中：酸菜白肉鍋、酸菜白肉 | 火鍋:酸菜白肉鍋、酸菜白肉; 咖啡/甜點:甜點 |
| 75 | 10457 | 頁小館 | 中式料理 | 約會 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 義法料理 (2007)；命中：燉飯 | 義法料理:燉飯 |
| 75 | 10377 | 築本屋公館店 | 中式料理 |  | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：烤肉 | 日式燒肉:烤肉 |
| 75 | 10461 | 泰市場 大直英迪格店 | 中式料理 | 約會 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 義法料理 (2007)；命中：披薩 | 義法料理:披薩; 咖啡/甜點:甜點 |
| 75 | 10597 | 漢來上海湯包 台北LaLaport南港店 | 中式料理 | 親子 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 75 | 10299 | Moni咖哩 | 中式料理 | 約會 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 美式料理 (2010)；命中：漢堡 | 美式料理:漢堡 |
| 75 | 10751 | KOBE SWEETS CAFE 神戶果実 微風南山 | 中式料理 | 商務 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：cafe、下午茶、蛋糕、甜點 | 咖啡/甜點:cafe、下午茶、蛋糕、甜點 |
| 75 | 10752 | 蘭亭燒肉 | 中式料理 | 約會、親子 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 75 | 10759 | 茶茶王國[士林店]-Matcha Prince茶茶王国のおうじちゃま | 中式料理 |  | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕 | 咖啡/甜點:蛋糕 |
| 75 | 10480 | 波 WAVE 鷹嘴豆泥屋 Hummus House | 中式料理 | 約會 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：牛舌 | 日式燒肉:牛舌 |
| 75 | 10490 | 亞瑟蘭印度餐廳(士林店)Asrah Indian Cuisines 清真認證Halal | 中式料理 | 親子 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 75 | 10654 | 夏綠沁私房義大利麵燉飯 | 中式料理 | 義式 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利、燉飯 | 義法料理:義大利麵、義大利、燉飯 |
| 75 | 10329 | 東京廚房 | 中式料理 | 親子 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 美式料理 (2010)；命中：漢堡 | 美式料理:漢堡 |
| 75 | 10717 | 詹咖李 | 中式料理 | 義式 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義式 | 義法料理:義式 |
| 75 | 10503 | Tierra Casa Restaurant-台北內湖西餐廳 在地食材創意料理 價格訂位推薦 義式法式料理 2026人氣必吃美食 精品茶葉咖啡 聚餐親子餐廳 PTT Dcard | 中式料理 | 法式、義式、親子 | keyword_conflict;defaulted_to_chinese;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利、法式、燉飯、義式 | 義法料理:義大利麵、義大利、法式、燉飯、義式; 咖啡/甜點:咖啡 |
| 57 | 10347 | TankQ cafe&Bar忠孝敦化店 | 美式料理 | 韓式、義式、親子 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利 | 義法料理:義大利麵、義大利; 韓式料理:韓式; 咖啡/甜點:cafe; 韓式 tag |
| 57 | 10671 | 燒肉中山｜台北信義 | 日式燒肉 | 韓式、約會 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 日式料理 (2004)；命中：壽司 | 日式料理:壽司; 韓式料理:韓式; 韓式 tag |
| 57 | 10622 | 樂軒松阪亭 | 日式燒肉 | 牛排、韓式、約會、商務 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 火鍋 (2001)；命中：壽喜燒 | 火鍋:壽喜燒; 韓式料理:韓式; 美式料理:牛排; 韓式 tag |
| 57 | 10158 | 大樹先生的家 | 美式料理 | 親子 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 日式料理:烏龍麵; 義法料理:義大利麵、義大利、燉飯; 韓式料理:韓式; 韓式 tag |
| 57 | 10588 | 發肉燒肉餐酒忠孝二店 | 日式燒肉 | 韓式、約會 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 日式料理:烏龍麵; 韓式料理:韓式; 韓式 tag |
| 57 | 10625 | 大河牧場 漢堡排專売-南港環球店 | 美式料理 | 韓式 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉; 咖啡/甜點:甜點; 韓式 tag |
| 57 | 10559 | 大叔食事unclefoodday | 美式料理 | 韓式 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 韓式料理 (2009)；命中：韓式 | 韓式料理:韓式; 韓式 tag |
| 57 | 10646 | ONE GOOD烤肉飯(大安店） | 日式料理 | 韓式 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：烤肉 | 日式燒肉:烤肉; 韓式料理:韓式; 韓式 tag |
| 57 | 10402 | 小尚品精制鍋物 師大分部店 | 火鍋 | 韓式 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 韓式料理 (2009)；命中：泡菜鍋 | 韓式料理:泡菜鍋; 韓式 tag |
| 57 | 10485 | 蘋果肉桂 Café & Bistro | 咖啡/甜點 | 早午餐、韓式、義式、餐酒館、約會 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利 | 義法料理:義大利麵、義大利; 韓式料理:韓式; 美式料理:早午餐; 韓式 tag |
| 57 | 10726 | 小蔬同手作蔬食 | 素食 | 韓式 | keyword_conflict;korean_tag_review;high_impact | 檢查是否應改為 韓式料理 (2009)；命中：部隊鍋、韓式 | 韓式料理:部隊鍋、韓式; 韓式 tag |
| 45 | 10245 | 和牛涮台北忠孝東店 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：壽司 | 日式料理:壽司 |
| 45 | 10615 | 狗一下居食酒堂-忠孝店 | 居酒屋 | 吃到飽 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：牛舌 | 日式燒肉:牛舌; 日式料理:生魚片、壽司 |
| 45 | 10508 | 豐 FOOD 海陸百匯 | 自助餐 | 吃到飽、親子 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：暢飲、啤酒 | 居酒屋:暢飲、啤酒; 日式料理:生魚片; 義法料理:披薩 |
| 45 | 10247 | 尬鍋 台式潮鍋 台北西門店 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：台式 | 中式料理:台式 |
| 45 | 10175 | 肉次方 燒肉放題 台北峨眉店 | 日式燒肉 | 吃到飽、約會 | keyword_conflict;high_impact | 檢查是否應改為 韓式料理 (2009)；命中：石鍋拌飯 | 韓式料理:石鍋拌飯 |
| 45 | 10152 | 和牛涮 台北羅斯福店 | 火鍋 | 吃到飽、親子 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：壽司 | 日式料理:壽司; 自助餐:自助餐; 咖啡/甜點:甜點 |
| 45 | 10616 | 金洹苑 KIN KAN EN-日式燒肉火鍋吃到飽 台北日本和牛海鮮吃到飽人氣推薦 | 日式燒肉 | 牛排、吃到飽、約會 | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：鍋底、火鍋 | 火鍋:鍋底、火鍋; 美式料理:牛排 |
| 45 | 10206 | 林美如 海鮮 熱炒 燒烤 酒場 | 中式料理 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：酒場 | 居酒屋:酒場 |
| 45 | 10252 | 山上走走 日式燒肉台北華山店 | 日式料理 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉; 美式料理:漢堡 |
| 45 | 10176 | 島語 台北漢來店 | 自助餐 | 牛排、吃到飽、約會、商務 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：壽司 | 日式料理:壽司; 美式料理:牛排; 咖啡/甜點:甜點 |
| 45 | 10159 | 西堤牛排台北羅斯福店 | 義法料理 | 牛排 | keyword_conflict;high_impact | 檢查是否應改為 素食 (2005)；命中：素食 | 素食:素食; 美式料理:牛排; 咖啡/甜點:甜點 |
| 45 | 10509 | solo pasta | 義法料理 | 義式、約會 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 45 | 10419 | 麵屋 千雲 林森店 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 45 | 10578 | 大阪燒肉 燒魂Yakikon林森本店 | 日式燒肉 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：酒場 | 居酒屋:酒場 |
| 45 | 10341 | 艾朋牛排餐酒館 | 義法料理 | 牛排、義式、餐酒館、約會 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排 |
| 45 | 10107 | 老井極上燒肉 台北信義店 | 日式燒肉 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：壽司 | 日式料理:壽司 |
| 45 | 10510 | Meat Up 覓晌 台北西門店 | 美式料理 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕、甜點 | 咖啡/甜點:蛋糕、甜點 |
| 45 | 10668 | 藝奇 | 日式料理 | 牛排、約會 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排 |
| 45 | 10420 | 新馬辣經典麻辣鍋-公館店 | 火鍋 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：暢飲、啤酒 | 居酒屋:暢飲、啤酒 |
| 45 | 10254 | 大村武串燒居酒屋-西門店（本店） | 居酒屋 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 45 | 10617 | 歐買尬日式海鮮串燒 市民一店 | 美式料理 | 吃到飽、約會、親子 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：居酒屋、串燒 | 居酒屋:居酒屋、串燒; 日式料理:生魚片 |
| 45 | 10669 | 熊一頂級燒肉-西門二店 | 日式料理 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉、烤肉 | 日式燒肉:燒肉、烤肉; 居酒屋:啤酒 |
| 45 | 10125 | 夏慕尼新香榭鐵板燒 台北中山北店 | 義法料理 | 鐵板燒 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排; 咖啡/甜點:甜點 |
| 45 | 10103 | 旭集 和食集錦 信義店 | 自助餐 | 商務、親子 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：生魚片、天婦羅 | 日式料理:生魚片、天婦羅 |
| 45 | 10180 | 小倉庫食研所 | 美式料理 | Brunch | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利 | 義法料理:義大利麵、義大利 |
| 45 | 10423 | GYUU NIKU ステーキ專門店 | 日式料理 | 牛排 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：牛舌 | 日式燒肉:牛舌; 美式料理:牛排 |
| 45 | 10100 | 一蘭 台灣台北別館 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 45 | 10106 | 饗食天堂 台北信義店 | 自助餐 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：生魚片 | 日式料理:生魚片; 中式料理:熱炒、港點 |
| 45 | 10730 | 燒肉神保町信義館 | 美式料理 | 牛排 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 45 | 10149 | 夏慕尼新香榭鐵板燒 台北南昌店 | 義法料理 | 鐵板燒 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕、甜點 | 咖啡/甜點:蛋糕、甜點 |
| 45 | 10214 | 赤富士日式燒肉鍋物-西門店-萬華/西門町人氣燒肉\|熱門燒肉\|必吃燒肉\|推薦燒肉\|聚餐推薦\|燒肉餐廳\|燒肉吃到飽\|在地推薦餐廳 | 日式燒肉 | 吃到飽、親子 | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：火鍋、鍋物 | 火鍋:火鍋、鍋物 |
| 45 | 10618 | TakeOut Burger&Cafe 忠孝新生店（last order 21:40) | 美式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：cafe | 咖啡/甜點:cafe |
| 45 | 10426 | 老倉庫 | 美式料理 | 義式 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：暢飲 | 居酒屋:暢飲; 義法料理:義大利麵、義大利 |
| 45 | 10348 | 錢都日式涮涮鍋 台北延平店 | 火鍋 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：牛舌 | 日式燒肉:牛舌; 素食:蔬食 |
| 45 | 10264 | 大村武串燒居酒屋-士林店 | 居酒屋 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：壽喜燒 | 火鍋:壽喜燒 |
| 45 | 10428 | 好食多涮涮鍋 雙城店 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：涮涮鍋、鍋底、涮涮 | 火鍋:涮涮鍋、鍋底、涮涮 |
| 45 | 10115 | 辛殿麻辣鍋｜信義店 | 火鍋 | 吃到飽 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：西班牙 | 義法料理:西班牙; 咖啡/甜點:甜點 |
| 45 | 10429 | 陶板屋 台北復興北店 | 日式料理 | 牛排、約會、親子 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：串燒 | 居酒屋:串燒; 美式料理:漢堡、牛排 |
| 45 | 10112 | HOOTERS美式餐廳 信義店 | 美式料理 | 義式、景觀 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：酒吧、暢飲 | 居酒屋:酒吧、暢飲; 義法料理:義大利麵、義大利 |
| 45 | 10732 | 狗一下居食酒屋-西門店 | 居酒屋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：生魚片、壽司 | 日式料理:生魚片、壽司 |
| 45 | 10733 | WOW Bistro旺.慢食餐酒館 -中山店 | 義法料理 | 牛排、義式、餐酒館、約會 | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：麵食 | 中式料理:麵食; 美式料理:牛排; 咖啡/甜點:甜點 |
| 45 | 10127 | 下港吔羊肉專賣店 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：熱炒 | 中式料理:熱炒 |
