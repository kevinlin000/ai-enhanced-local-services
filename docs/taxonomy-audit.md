# Taxonomy Audit

- Unique shops scanned: 600
- Audit rows: 247
- Korean-tagged rows needing review: 5

## Category Distribution

- 2001 火鍋: 88
- 2002 日式燒肉: 58
- 2003 居酒屋: 59
- 2004 日式料理: 79
- 2005 素食: 26
- 2007 義法料理: 82
- 2008 中式料理: 89
- 2009 韓式料理: 16
- 2010 美式料理: 55
- 2011 自助餐: 8
- 2012 咖啡/甜點: 34
- 2013 異國料理: 6

## Tag Distribution

- 約會: 154
- 親子: 153
- 義式: 76
- 餐酒館: 35
- 牛排: 34
- 商務: 33
- 早午餐: 24
- 吃到飽: 22
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

- high_impact: 246
- keyword_conflict: 205
- defaulted_to_chinese: 37
- korean_tag_review: 5

## Recommendation

- Keep `日式料理` as a Japanese-only primary category.
- Use `韓式料理` as a dedicated primary category for clearly Korean restaurants.
- Use `異國料理` for Indian, Thai, Middle Eastern, Vietnamese, Mexican, and similar cuisines instead of forcing them into `中式料理` or `義法料理`.
- Keep the `韓式` tag for compatibility and mixed-format restaurants, but do not use `日韓料理` as a combined category.
- Review high-priority rows first, then add classifier overrides or DB migrations for confirmed fixes.

## Top 80 Review Rows

| priority | shop_id | name | category | tags | flags | suggestion | evidence |
| ---: | ---: | --- | --- | --- | --- | --- | --- |
| 45 | 10175 | 肉次方 燒肉放題 台北峨眉店 | 日式燒肉 | 泰式、吃到飽、約會 | keyword_conflict;high_impact | 檢查是否應改為 韓式料理 (2009)；命中：石鍋拌飯 | 韓式料理:石鍋拌飯 |
| 45 | 10176 | 島語 台北漢來店 | 自助餐 | 牛排、吃到飽、約會、商務 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：壽司 | 日式料理:壽司; 美式料理:牛排; 咖啡/甜點:甜點 |
| 45 | 10427 | 泰滾 Rolling Thai 泰式火鍋(南京店） | 火鍋 | 泰式、約會 | keyword_conflict;high_impact | 檢查是否應改為 異國料理 (2013)；命中：thai | 異國料理:thai |
| 45 | 10583 | 初樂燒肉 | 日式燒肉 | 約會、親子 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：漢堡 | 美式料理:漢堡 |
| 45 | 10584 | 洋城義大利餐廳-東森廣場北車店 | 義法料理 | 義式 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 45 | 10174 | 悠悠龍貓咖啡 | 咖啡/甜點 | 義式、約會、親子 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利 | 義法料理:義大利麵、義大利 |
| 45 | 10619 | 火燒鳥日式居酒屋 | 居酒屋 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 日式料理:烏龍麵 |
| 45 | 10585 | 發肉燒肉餐酒敦北一店 | 日式燒肉 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 45 | 10670 | 大河屋 燒肉丼 串燒-微風北車店 | 居酒屋 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 45 | 10128 | 唐宮蒙古烤肉酸菜白肉餐廳 | 火鍋 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：烤肉 | 日式燒肉:烤肉; 中式料理:熱炒 |
| 45 | 10620 | 胖肚肚燒肉 大安店 | 美式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：烤肉、燒肉、牛舌 | 日式燒肉:烤肉、燒肉、牛舌 |
| 45 | 10162 | 小紅莓石頭火鍋城 | 火鍋 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：台式 | 中式料理:台式 |
| 45 | 10220 | 蔦燒日式居酒屋-石牌店 | 居酒屋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：牛舌 | 日式燒肉:牛舌 |
| 45 | 10187 | 布納咖啡館 內湖館 | 咖啡/甜點 | 義式、親子 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利 | 義法料理:義大利麵、義大利 |
| 45 | 10110 | Woolloomooloo | 義法料理 | 景觀 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：漢堡 | 美式料理:漢堡; 咖啡/甜點:甜點 |
| 45 | 10136 | Second Floor 貳樓敦南店 | 美式料理 | Brunch | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式 | 義法料理:法式; 咖啡/甜點:咖啡 |
| 45 | 10129 | 紅翻天生猛海鮮 | 中式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：下酒 | 居酒屋:下酒; 日式料理:生魚片 |
| 45 | 10351 | NAGOYA 道地日式蛋包飯（開放電話及私訊訂位） | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：漢堡 | 美式料理:漢堡 |
| 45 | 10737 | WOWFFIZI cafe&Bistro 烏菲茲餐酒館 | 義法料理 | 餐酒館、約會 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：cafe、蛋糕、甜點 | 咖啡/甜點:cafe、蛋糕、甜點 |
| 45 | 10168 | 石二鍋 台北捷運後山埤店 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 素食 (2005)；命中：蔬食 | 素食:蔬食 |
| 45 | 10519 | 神燈搓一下 | 素食 | 印度、中東 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 45 | 10738 | 瀧厚炙燒熟成牛排 台北.南港店 | 美式料理 | 牛排、法式、親子 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式 | 義法料理:法式 |
| 45 | 10621 | 忠孝｜燒肉政宗 YAKINIKU MASAMUNE | 日式燒肉 |  | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：漢堡 | 美式料理:漢堡 |
| 45 | 10188 | 築間幸福鍋物 台北內湖店 | 火鍋 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 素食 (2005)；命中：蔬食 | 素食:蔬食; 義法料理:西班牙 |
| 45 | 10140 | 樂子the Diner 瑞安店 | 美式料理 | Brunch | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：燉飯 | 義法料理:燉飯; 咖啡/甜點:咖啡 |
| 45 | 10151 | 深夜裡的法國手工甜點 | 咖啡/甜點 | 法式 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式 | 義法料理:法式 |
| 45 | 10355 | GumGum Beer & Wings | 義法料理 | 約會、親子 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕 | 咖啡/甜點:蛋糕 |
| 45 | 10521 | 錢都日式涮涮鍋 台北師大店 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 素食 (2005)；命中：蔬食 | 素食:蔬食; 咖啡/甜點:甜點 |
| 45 | 10108 | 布納咖啡館 信義館 | 咖啡/甜點 | 牛排、義式、約會、親子 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：啤酒、精釀 | 居酒屋:啤酒、精釀; 義法料理:義大利麵、義大利、燉飯; 美式料理:牛排 |
| 45 | 10358 | 蝸牛義大利餐廳 天母店 | 義法料理 | 義式、親子 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕 | 咖啡/甜點:蛋糕 |
| 45 | 10226 | 酒米食堂chumi_canteen－北投店beitou | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：居酒屋、啤酒 | 居酒屋:居酒屋、啤酒 |
| 45 | 10674 | 樂軒和牛專門店 | 日式燒肉 | 約會、商務 | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：壽喜燒、涮涮鍋、涮涮 | 火鍋:壽喜燒、涮涮鍋、涮涮 |
| 45 | 10739 | 小紐約披薩 中山店 LNYPIZZA Little New York Pizzeria Zhongshan | 義法料理 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：酒吧 | 居酒屋:酒吧; 美式料理:美式 |
| 45 | 10156 | 一番地壽喜燒 古亭店 | 火鍋 | 吃到飽 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 45 | 10361 | 詩篇咖啡餐廳Psalms Cafe & Restaurant | 義法料理 | 義式 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：cafe、下午茶、咖啡 | 咖啡/甜點:cafe、下午茶、咖啡 |
| 45 | 10676 | 林居sushi日本料理 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：台式 | 中式料理:台式 |
| 45 | 10442 | At.First早寓 | 義法料理 | 早午餐、牛排、義式 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：早午餐、牛排 | 美式料理:早午餐、牛排 |
| 45 | 10278 | 蔦燒日式居酒屋-北投店 | 居酒屋 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：牛舌 | 日式燒肉:牛舌; 日式料理:烏龍麵 |
| 45 | 10523 | Remember Me_記得我．café -深夜咖啡館 寵物友善 | 咖啡/甜點 | 約會、親子 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：燉飯 | 義法料理:燉飯 |
| 45 | 10363 | 老朋友小酌熱炒 | 中式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：啤酒 | 居酒屋:啤酒; 義法料理:西班牙 |
| 45 | 10365 | 渣男 Taiwan Bistro 信義一渣 | 居酒屋 | 餐酒館 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 日式料理:烏龍麵; 中式料理:台式; 咖啡/甜點:咖啡 |
| 45 | 10280 | 蔬軾 | 素食 | 印度、義式、親子 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利、披薩 | 義法料理:義大利麵、義大利、披薩 |
| 45 | 10524 | gonnaEAT 內湖店 | 義法料理 | 約會、商務、親子 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕、咖啡 | 咖啡/甜點:蛋糕、咖啡 |
| 45 | 10627 | 肉你好燒肉-合江總舖 | 日式燒肉 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：居酒屋 | 居酒屋:居酒屋 |
| 45 | 10591 | 火人串燒 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：串燒 | 居酒屋:串燒 |
| 45 | 10678 | 渣男Taiwan Bistro古亭四渣 | 居酒屋 | 餐酒館、商務 | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：台式 | 中式料理:台式 |
| 45 | 10367 | 川邸鍋物 劍潭店 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕、甜點 | 咖啡/甜點:蛋糕、甜點 |
| 45 | 10526 | M One Cafe A11 | 美式料理 | 早午餐、約會 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：cafe | 咖啡/甜點:cafe |
| 45 | 10592 | 品司和食 | 日式料理 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：火鍋 | 火鍋:火鍋 |
| 45 | 10628 | 蔦燒日式居酒屋-士林店 | 居酒屋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：壽司 | 日式料理:壽司 |
| 45 | 10181 | Bogart's Smokehouse Taipei (美式木柴煙燻屋) OPEN til SOLDOUT | 美式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：烤肉 | 日式燒肉:烤肉 |
| 45 | 10528 | 紅屋牛排館民生店 | 美式料理 | 牛排、商務 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕、甜點 | 咖啡/甜點:蛋糕、甜點 |
| 45 | 10369 | i99 COFFEE 景美店 | 咖啡/甜點 | 吃到飽 | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：鍋物、火鍋 | 火鍋:鍋物、火鍋; 居酒屋:暢飲 |
| 45 | 10529 | 荖子鍋Plus 家樂福內湖店 | 火鍋 | 吃到飽 | keyword_conflict;high_impact | 檢查是否應改為 自助餐 (2011)；命中：自助餐 | 自助餐:自助餐 |
| 45 | 10680 | TakeOut Burger&Cafe 民權店 | 美式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：cafe | 咖啡/甜點:cafe |
| 45 | 10446 | PRESERVE 遠東GARDEN CITY 大巨蛋店 | 素食 | 義式、約會 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利 | 義法料理:義大利麵、義大利 |
| 45 | 10286 | 蔣老爹愛吃鍋 市民店｜台北東區｜麻辣火鍋 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：台式 | 中式料理:台式 |
| 45 | 10681 | 明水然・樂-遠百信義店(遠百A13店) | 日式料理 | 鐵板燒、約會 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：漢堡 | 美式料理:漢堡 |
| 45 | 10288 | 渣男TaiwanBistro 木柵二渣 | 居酒屋 | 餐酒館、約會 | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：台式 | 中式料理:台式 |
| 45 | 10231 | 三燔北投 Mihan Beitou | 日式料理 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：壽喜燒、涮涮鍋、鍋物、涮涮 | 火鍋:壽喜燒、涮涮鍋、鍋物、涮涮; 咖啡/甜點:甜點 |
| 45 | 10449 | 阿薄郎薄皮餃子－公館店 | 日式料理 | 餐酒館 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：下酒、啤酒、串燒 | 居酒屋:下酒、啤酒、串燒; 中式料理:台式 |
| 45 | 10531 | 野草居食屋 | 居酒屋 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：牛舌 | 日式燒肉:牛舌 |
| 45 | 10171 | 肉執事台北松山門市 | 日式燒肉 |  | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：台式 | 中式料理:台式 |
| 45 | 10451 | — LAX 慵懶 — 貓空 ｜ | 義法料理 | 泰式、義式、約會、親子、景觀 | keyword_conflict;high_impact | 檢查是否應改為 異國料理 (2013)；命中：月亮蝦餅 | 異國料理:月亮蝦餅 |
| 45 | 10533 | A Beach 101&Pizza | 義法料理 | 約會、親子 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕、甜點 | 咖啡/甜點:蛋糕、甜點 |
| 45 | 10630 | 燒鳩 刺身•串燒•夜食 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：串燒、暢飲 | 居酒屋:串燒、暢飲 |
| 45 | 10631 | 哞屋Mon wo | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉; 美式料理:漢堡 |
| 45 | 10453 | 墨竹亭 燃麵本家 台北六張犁店 | 中式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：壽喜燒 | 火鍋:壽喜燒; 日式燒肉:燒肉 |
| 45 | 10455 | 品田牧場 台北松山車站店 | 美式料理 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 45 | 10182 | 花漾夯夯鍋-政大店 \| 火鍋259起 \| 木柵火鍋吃到飽\|木柵宵夜 | 火鍋 | 吃到飽 | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：麵食 | 中式料理:麵食 |
| 45 | 10183 | 呼嚕小酒館 Purrson Bistro | 義法料理 | 餐酒館 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：漢堡 | 美式料理:漢堡 |
| 45 | 10633 | 青杉燒肉 | 日式燒肉 | 約會、商務 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：燉飯 | 義法料理:燉飯 |
| 45 | 10538 | 果然匯 台北天母店 | 素食 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：披薩 | 義法料理:披薩; 咖啡/甜點:甜點 |
| 45 | 10634 | 三柒燒肉專門店-大安敦化店 | 日式燒肉 | 牛排 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排 |
| 45 | 10539 | Second Floor 貳樓微風南山店 | 美式料理 | 牛排、法式、約會、親子、景觀 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式 | 義法料理:法式; 中式料理:台式; 咖啡/甜點:蛋糕 |
| 45 | 10460 | 加分100%浜中特選昆布鍋物-八德店 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 日式料理:烏龍麵 |
| 45 | 10141 | 葉公館滬菜 | 中式料理 | 商務 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 45 | 10747 | 小小麥 信義新光A11 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 45 | 10378 | 波赫士領地精品咖啡館 明水店 提拉米蘇 千層蛋糕 | 咖啡/甜點 | 早午餐、牛排、義式、約會 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：披薩、義式 | 義法料理:披薩、義式; 美式料理:早午餐、牛排 |
| 45 | 10296 | overthink 餐飲小吃部 | 義法料理 | 義式、約會 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：啤酒、精釀 | 居酒屋:啤酒、精釀; 中式料理:台式 |
