# Taxonomy Audit

- Unique shops scanned: 600
- Audit rows: 166
- Korean-tagged rows needing review: 5

## Category Distribution

- 2001 火鍋: 88
- 2002 日式燒肉: 60
- 2003 居酒屋: 63
- 2004 日式料理: 74
- 2005 素食: 25
- 2007 義法料理: 79
- 2008 中式料理: 89
- 2009 韓式料理: 16
- 2010 美式料理: 55
- 2011 自助餐: 8
- 2012 咖啡/甜點: 35
- 2013 異國料理: 8

## Tag Distribution

- 約會: 153
- 親子: 152
- 義式: 76
- 餐酒館: 35
- 牛排: 34
- 商務: 33
- 早午餐: 24
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

- high_impact: 165
- keyword_conflict: 124
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
| 45 | 10236 | 辣椒多一點麻辣鍋物養生鍋 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕 | 咖啡/甜點:蛋糕 |
| 45 | 10572 | Chill嗨嗨酒場 Bar | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：酒場、串燒 | 居酒屋:酒場、串燒 |
| 45 | 10139 | 小小樹食 敦南店 | 素食 | 義式 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利 | 義法料理:義大利麵、義大利; 咖啡/甜點:蛋糕 |
| 45 | 10749 | 日本橋浜町食事处 微風北車店 | 日式料理 | 商務 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：居酒屋 | 居酒屋:居酒屋 |
| 45 | 10543 | BaganHood 蔬食餐酒館 | 素食 | 泰式、中東、義式、餐酒館、約會 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利、披薩 | 義法料理:義大利麵、義大利、披薩; 異國料理:墨西哥料理、鷹嘴豆泥 |
| 45 | 10544 | 茱莉金牛排餐酒館 | 美式料理 | 牛排、法式、餐酒館、約會 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式 | 義法料理:法式 |
| 45 | 10545 | 前鎮水產-海霸王 昆明店 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：生魚片 | 日式料理:生魚片 |
| 45 | 10599 | 士林串燒 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：串燒 | 居酒屋:串燒 |
| 45 | 10385 | CURA PIZZA 窯火熾心.古道樂嚐 （店休日、一、二） | 義法料理 |  | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：麵食 | 中式料理:麵食; 咖啡/甜點:甜點 |
| 45 | 10386 | Last Order | 義法料理 | 牛排、餐酒館、約會 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：牛舌 | 日式燒肉:牛舌; 美式料理:牛排 |
| 45 | 10547 | 陶膳日式料理 | 日式料理 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：居酒屋 | 居酒屋:居酒屋 |
| 45 | 10548 | 東京串燒酒場 | 居酒屋 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 日式料理:烏龍麵 |
| 45 | 10166 | 潮肉壽喜燒-永吉店 | 火鍋 | 吃到飽 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 45 | 10549 | Fa Burger | 美式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：烤肉 | 日式燒肉:烤肉 |
| 45 | 10464 | PRESERVE LaLaport 南港店 | 美式料理 | 早午餐、義式、約會、親子 | keyword_conflict;high_impact | 檢查是否應改為 素食 (2005)；命中：蔬食 | 素食:蔬食; 義法料理:義大利麵、義大利 |
| 45 | 10550 | Extension 1 by 橘色 | 日式料理 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：壽喜燒、鍋物 | 火鍋:壽喜燒、鍋物 |
| 45 | 10465 | 無口小廚 Mukuchi Kitchen & Bar | 素食 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：拉麵 | 日式料理:拉麵 |
| 45 | 10552 | 這一小鍋 台北北護店(最後收客20:00)【呷Bar店】 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：台式、麵食 | 中式料理:台式、麵食 |
| 45 | 10553 | 草根早午餐 TOUCH WOOD | 美式料理 | 早午餐、法式、餐酒館 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式 | 義法料理:法式; 咖啡/甜點:咖啡 |
| 45 | 10637 | 燒究食寓 萬華店 – 居酒屋｜宵夜｜串燒 | 居酒屋 | 牛排、親子 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排 |
| 45 | 10638 | Takeout Burger&Cafe 延吉店 （最後點餐21：30）/美式漢堡/寵物友善/大安區美食/貓咪餐廳 | 美式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：cafe | 咖啡/甜點:cafe |
| 45 | 10467 | PEPPINO 培皮諾小館 | 義法料理 | 義式、約會 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 45 | 10556 | 德朗火鍋 (信義店) | 火鍋 | 法式、商務 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式 | 義法料理:法式; 咖啡/甜點:甜點 |
| 45 | 10691 | Eatfoodie udon 好好吃餐房(烏龍麵 鍋燒意麵) | 火鍋 | 義式 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 日式料理:烏龍麵; 義法料理:義大利麵、義大利 |
| 45 | 10557 | AN58西班牙創意料理 | 義法料理 | 牛排、約會 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排 |
| 45 | 10692 | 鹿境早午餐 Arrival Brunch & Cafe - 早午餐推薦 ｜ 餐廳 ｜小巨蛋早午餐 ｜ 包場 ｜ 法式吐司 ｜ 漢堡｜咖喱 ｜小巨蛋早午餐｜台北早午餐推薦 | 美式料理 | Brunch、早午餐、法式、約會 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式 | 義法料理:法式; 咖啡/甜點:cafe |
| 45 | 10468 | Creative Pasta 創義麵 東湖店 | 義法料理 | 義式、親子 | keyword_conflict;high_impact | 檢查是否應改為 素食 (2005)；命中：素食 | 素食:素食 |
| 45 | 10558 | 根來阿財鐵板燒 | 日式料理 | 鐵板燒 | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：熱炒、台式 | 中式料理:熱炒、台式 |
| 45 | 10693 | 捌千代居酒屋 松山店 | 居酒屋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 日式料理:烏龍麵 |
| 45 | 10694 | 嚐居 | 居酒屋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：壽司 | 日式料理:壽司 |
| 45 | 10757 | 爍場居酒屋復興店 | 日式燒肉 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：居酒屋、下酒、串燒、暢飲 | 居酒屋:居酒屋、下酒、串燒、暢飲 |
| 45 | 10303 | 好吧 | 美式料理 | 早午餐、義式、親子 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義式 | 義法料理:義式 |
| 45 | 10560 | GumGum Not Only Beer & Wings 雞翅啤酒吧-內科店 | 居酒屋 | 義式、餐酒館、約會 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利、燉飯、披薩 | 義法料理:義大利麵、義大利、燉飯、披薩; 咖啡/甜點:蛋糕 |
| 45 | 10390 | 子女居酒屋 | 居酒屋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：天婦羅、烏龍麵 | 日式料理:天婦羅、烏龍麵 |
| 45 | 10640 | 七転八起-中山必吃串燒\|人氣串燒\|串燒專門店\|串燒烤肉\|熱門居酒屋\|居酒屋推薦\|喝酒聚餐推薦\|隱藏居酒屋 | 居酒屋 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：烤肉 | 日式燒肉:烤肉 |
| 45 | 10641 | 東京家庭義大利麵 堺人餐飲 天母 | 中式料理 | 義式、親子 | keyword_conflict;high_impact | 檢查是否應改為 素食 (2005)；命中：素食 | 素食:素食; 義法料理:義大利麵、義大利 |
| 45 | 10603 | 極簡鍋物｜萬華199和牛火鍋｜西門町火鍋推薦｜小龍蝦專賣店｜萬華美食 | 火鍋 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 45 | 10758 | Niconico Yakiniku 冠軍燒肉-西門 | 日式燒肉 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 日式料理:烏龍麵 |
| 45 | 10307 | 謀魚蝦也蠔南港直營店 | 火鍋 |  | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：熱炒 | 中式料理:熱炒 |
| 45 | 10643 | 八和和牛燒肉專門店-安和本店 | 日式燒肉 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕 | 咖啡/甜點:蛋糕 |
| 45 | 10695 | 試試工作室 | 日式燒肉 | 義式、約會 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利、燉飯、義式 | 義法料理:義大利麵、義大利、燉飯、義式; 咖啡/甜點:蛋糕 |
| 45 | 10562 | HANNA Pasta Café パスタ カフェ | 義法料理 | 義式、約會 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕 | 咖啡/甜點:蛋糕 |
| 45 | 10696 | Agusto奧古斯托 牛排龍蝦餐酒館 大安店｜新北美食義式餐廳 生日聚餐約會推薦 | 義法料理 | 牛排、法式、義式、餐酒館、約會 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排 |
| 45 | 10697 | 大河屋 燒肉丼 串燒-中信南港店 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉; 居酒屋:串燒 |
| 45 | 10698 | 樂氣串燒居酒屋 | 居酒屋 | 義式 | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：烏龍麵 | 日式料理:烏龍麵; 義法料理:義式 |
| 45 | 10391 | 孫太太嚴選超市火鍋台北民族店 | 火鍋 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：甜點 | 咖啡/甜點:甜點 |
| 45 | 10473 | Lazy Pasta 慵懶義式廚房文山萬芳店 | 義法料理 | 義式、親子 | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：麵食 | 中式料理:麵食 |
| 45 | 10564 | Plants | 素食 | 中東 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：燉飯 | 義法料理:燉飯 |
| 45 | 10474 | 朝鑫壽司（Asashi sushi) | 日式料理 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：串燒 | 居酒屋:串燒 |
| 45 | 10202 | 嗯哼咖啡食堂(Uh huh cafe) | 咖啡/甜點 |  | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：漢堡 | 美式料理:漢堡 |
| 45 | 10393 | 加分昆布鍋物-食べ放題-新生店 | 火鍋 | 吃到飽、親子 | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：麵食 | 中式料理:麵食 |
| 45 | 10566 | 鍋董日式涮涮鍋劍潭旗艦店 | 日式料理 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：涮涮鍋、涮涮 | 火鍋:涮涮鍋、涮涮 |
| 45 | 10605 | 肉你好燒肉-延吉店 | 日式燒肉 | 約會 | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：啤酒 | 居酒屋:啤酒 |
| 45 | 10573 | 豆町村燒肉 | 日式燒肉 | 牛排、約會 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排 |
| 45 | 10475 | The Slice Shop 信義安和 | 義法料理 |  | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：美式 | 美式料理:美式 |
| 45 | 10763 | 源本家燒肉火鍋 | 日式燒肉 |  | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：火鍋 | 火鍋:火鍋 |
| 45 | 10607 | 大河屋 燒肉丼 串燒-微風南京店 | 日式燒肉 |  | keyword_conflict;high_impact | 檢查是否應改為 居酒屋 (2003)；命中：串燒 | 居酒屋:串燒 |
| 45 | 10764 | CHIT CHAT Cafe 南京店 | 咖啡/甜點 | 早午餐 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：早午餐 | 美式料理:早午餐 |
| 45 | 10765 | AW Cafe Wine Bistro | 義法料理 | 早午餐、牛排、餐酒館、約會 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：早午餐、牛排 | 美式料理:早午餐、牛排; 咖啡/甜點:cafe |
| 45 | 10608 | 深深 永康制作所（建議先打電話問一下） | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 45 | 10477 | 無尽蔵居酒屋Mujinzou Izakaya（週五僅接受電話訂位） | 居酒屋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：壽司 | 日式料理:壽司 |
| 45 | 10647 | Monday蔬食料理 錦州店 | 素食 | 義式 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利、義式 | 義法料理:義大利麵、義大利、義式; 美式料理:漢堡 |
| 45 | 10478 | 麥味登 文山饗食大亨店 | 美式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：咖啡 | 咖啡/甜點:咖啡 |
| 45 | 10398 | GiraPizza 旋轉披薩 | 義法料理 | 義式、餐酒館 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：咖啡 | 咖啡/甜點:咖啡 |
| 45 | 10701 | 原蔬生活 élémentlifes……………..……...（僅接受一週內電話預約 We accept phone reservations up to one week in advance.） | 素食 | 義式、約會 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利、燉飯、義式 | 義法料理:義大利麵、義大利、燉飯、義式; 異國料理:pho |
| 45 | 10702 | 鳥居町日料居酒屋（東湖店) | 居酒屋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式料理 (2004)；命中：生魚片、壽司 | 日式料理:生魚片、壽司; 咖啡/甜點:蛋糕 |
| 45 | 10399 | 曹料理 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：牛舌 | 日式燒肉:牛舌 |
| 45 | 10318 | 全養知 異國蔬食 莊敬店 | 素食 | 中東、義式、約會 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義式 | 義法料理:義式; 異國料理:摩洛哥 |
| 45 | 10768 | RKZ Caf'e | 義法料理 | 牛排、約會 | keyword_conflict;high_impact | 檢查是否應改為 美式料理 (2010)；命中：牛排 | 美式料理:牛排 |
| 45 | 10570 | 蘇草salvia | 咖啡/甜點 | 早午餐、義式 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義大利麵、義大利 | 義法料理:義大利麵、義大利; 美式料理:早午餐 |
| 45 | 10609 | 酒桃Sake momo | 居酒屋 | 義式、餐酒館 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義式 | 義法料理:義式 |
| 45 | 10571 | 穗月朝食（最後點餐為營業前30分鐘） | 美式料理 | 泰式 | keyword_conflict;high_impact | 檢查是否應改為 異國料理 (2013)；命中：打拋 | 異國料理:打拋 |
| 45 | 10481 | 中山區麻辣火鍋/麻辣火鍋推薦/滑嫩鴨血豆腐/麻凡麻辣火鍋/養生蔬果湯 | 火鍋 | 法式、商務 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式 | 義法料理:法式 |
| 45 | 10703 | 老菘田居酒屋(串燒‧酒場) 南京店 | 居酒屋 |  | keyword_conflict;high_impact | 檢查是否應改為 日式燒肉 (2002)；命中：燒肉 | 日式燒肉:燒肉 |
| 45 | 10482 | 豐橋火鍋 | 火鍋 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 素食 (2005)；命中：蔬食 | 素食:蔬食 |
| 45 | 10704 | PAI CAFÉ & BRUNCH 八德店 | 美式料理 | Brunch、早午餐、法式 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：法式 | 義法料理:法式; 咖啡/甜點:拿鐵 |
| 45 | 10649 | 大河牧場 漢堡排洋食館-內湖大全聯店 | 美式料理 | 親子 | keyword_conflict;high_impact | 檢查是否應改為 火鍋 (2001)；命中：壽喜燒 | 火鍋:壽喜燒 |
| 45 | 10705 | 波赫士領地精品咖啡館 提拉米蘇 千層蛋糕 BorgesPlace昌吉店 | 咖啡/甜點 | 早午餐、牛排、義式 | keyword_conflict;high_impact | 檢查是否應改為 義法料理 (2007)；命中：義式 | 義法料理:義式; 美式料理:早午餐、牛排 |
| 45 | 10241 | 貓蕊 貓咪餐廳 | 美式料理 | 早午餐、親子 | keyword_conflict;high_impact | 檢查是否應改為 咖啡/甜點 (2012)；命中：蛋糕 | 咖啡/甜點:蛋糕 |
| 45 | 10403 | 男子漢拉麵食堂-北投店 | 日式料理 |  | keyword_conflict;high_impact | 檢查是否應改為 中式料理 (2008)；命中：麵食 | 中式料理:麵食 |
