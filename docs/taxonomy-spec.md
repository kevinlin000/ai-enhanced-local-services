# Taxonomy Spec

Status: active. V37 completes the manual taxonomy audit and removes misleading Korean tags.

Data baseline: 600 active shops in MySQL taxonomy audit on 2026-06-09.

## 1. Main Categories

Decision:
- Use 12 main categories.
- `高級` leaves main taxonomy and becomes badge.
- `牛排` stays as a tag.
- `韓式料理` is a primary category for clearly Korean restaurants; `#韓式` remains as compatibility / mixed-format tag.
- `異國料理` is a primary category for Indian, Thai, Middle Eastern, Vietnamese, Mexican, and similar non-core cuisine groups.

### 1.1 Category Table

| type_id | 主分類 | 店家數 | 說明 |
| --- | --- | ---: | --- |
| 2001 | 火鍋 | 88 | 火鍋、涮涮鍋、壽喜燒、鍋物吃到飽 |
| 2002 | 日式燒肉 | 57 | 日式燒肉為主 |
| 2003 | 居酒屋 | 68 | 日式酒場、小酌串燒 |
| 2004 | 日式料理 | 78 | 拉麵、鰻魚飯、純日料正餐 |
| 2005 | 素食 | 26 | 蔬食、vegan、素食百匯 |
| 2007 | 義法料理 | 78 | 義式、法式、西式餐酒館、鐵板套餐 |
| 2008 | 中式料理 | 79 | 台菜、粵菜、港點、熱炒、小籠包、中式宴席 |
| 2009 | 韓式料理 | 16 | 韓式烤肉、韓式鍋物、韓式正餐；保留 `#韓式` tag |
| 2010 | 美式料理 | 49 | 美式、澳式、brunch 主體、漢堡、煙燻肉 |
| 2011 | 自助餐 | 8 | buffet / cafeteria / 吃到飽主體 |
| 2012 | 咖啡/甜點 | 43 | 咖啡館、甜點店、下午茶 |
| 2013 | 異國料理 | 10 | 印度、泰式、中東、越南、墨西哥等；用 cuisine tags 區分細項 |

### 1.2 type_id Policy

Keep:
- `2001` 火鍋
- `2002` 日式燒肉
- `2003` 居酒屋
- `2004` 日式料理
- `2007` 義法料理
- `2008` 中式料理
- `2009` 韓式料理
- `2010` 美式料理
- `2013` 異國料理

Repurpose:
- `2005`: `無菜單料理` -> `素食`
- `2011`: `高級餐廳` -> `自助餐`
- `2012`: `特色咖啡` -> `咖啡/甜點`

Retire from main taxonomy:
- `2006` 牛排館

Note:
- `2006` stays reserved. Do not delete immediately in migration plan.
- `2009` was promoted back to primary category in V32.
- `2013` was added in V33 instead of reusing `2006`, so the retired steak id remains semantically clean.
- V34 applies the second manual audit batch, including 品田牧場 -> 日式料理, 泰滾 / 神燈搓一下 -> 異國料理, and 果然匯 retaining 素食 with `#吃到飽`.
- V35 applies the third manual audit batch, including 麥味登 -> 中式料理 + `#早午餐`, 大河牧場漢堡排洋食館 -> 日式料理, and 貓蕊 -> 咖啡/甜點.
- V36 applies the fourth manual audit batch, including MAJI MAJI / mama says yes -> 異國料理, 吉豚屋 / 勝魂丼飯 / 雲の咖哩屋 / 晴天廚房 / 巧主廚的咖哩 -> 日式料理, and Mr. 雪腐 / 女巫店 / 三角冰 -> 咖啡/甜點.
- V37 completes the manual audit, moving 花嶼輕食館 -> 咖啡/甜點 and removing misleading `#韓式` tags from non-Korean restaurants such as 燒肉眾, 大樹先生的家, 神來一爐, IKIGAI, and 蘋果肉桂.

## 2. Badge Rule

Decision:
- `[高級]` is badge, not main category.
- Home entry `高級餐廳` = filter all shops with `[高級]`.
- Shop must still live under its cuisine main category.

### 2.1 Badge Meaning

`[高級]` represents dining grade, not cuisine.

Examples:
- 鼎泰豐 = `中式料理 + [高級]`
- 夏慕尼 = `義法料理 + [高級]`
- 饗饗 = `自助餐 + [高級]`

### 2.2 Launch Rule

Launch phase uses curated allowlist first. Avoid heuristic overfire.

Initial `[高級]` badge allowlist: 11 shops

| shop_id | 店名 | 主分類 |
| --- | --- | --- |
| 10101 | 鼎泰豐 101店 | 中式料理 |
| 10111 | 鼎泰豐 A4店 | 中式料理 |
| 10114 | 鼎泰豐 A13店 | 中式料理 |
| 10191 | 鼎泰豐 天母店 | 中式料理 |
| 10198 | 鼎泰豐 南西店 | 中式料理 |
| 10103 | 旭集 和食集錦 信義店 | 自助餐 |
| 10104 | INPARADISE 饗饗 微風信義店 | 自助餐 |
| 10107 | 老井極上燒肉 台北信義店 | 日式燒肉 |
| 10125 | 夏慕尼新香榭鐵板燒 台北中山北店 | 義法料理 |
| 10149 | 夏慕尼新香榭鐵板燒 台北南昌店 | 義法料理 |
| 10176 | 島語 台北漢來店 | 自助餐 |

### 2.3 Future Auto-Qualification Rule

Later, a shop may auto-qualify for `[高級]` only when both are true:

1. Hard threshold
- `avg_price >= 1200`

2. Plus at least one premium signal
- `booking_difficulty` indicates hot / hard to book
- tasting / set menu / omakase / teppanyaki / tableside service
- strong `商務` / `景觀` / `包廂` context
- curated brand override

### 2.4 Negative Rule

These do **not** create `[高級]` by themselves:
- `吃到飽`
- `牛排`
- `韓式`
- `鐵板燒`
- `套餐`

This prevents false positives:
- 西堤: keep `#牛排`, no `[高級]`
- 弘大一號出口: keep `#韓式`, no `[高級]`
- 饗食天堂: `自助餐`, no `[高級]`
- 蔬食百匯: `素食`, no `[高級]`

## 3. Tags And Promotion Rule

### 3.1 Tag List

Cuisine / format tags:
- `#Brunch`
- `#早午餐`
- `#牛排`
- `#韓式`
- `#法式`
- `#義式`
- `#餐酒館`
- `#鐵板燒`
- `#吃到飽`

Use-case tags:
- `#約會`
- `#商務`
- `#包廂`
- `#景觀`
- `#親子`
- `#免訂金`
- `#HotSeat`

### 3.2 Promotion Rule

Tag can be considered for promotion to main category only if all conditions pass:

1. Shop count threshold
- at least `>= 3`
- ideally `>= 5`

2. User mental model is primary, not secondary
- user searches it as first-layer intent
- not merely occasion or feature

3. Overlap with existing main categories is low enough
- not just a subset of one existing main category

4. Catalog quality is broad enough
- not single-brand inflation
- not one district only

### 3.3 Watchlist Tags

Watchlist now:
- `#牛排`

Current decision:
- `#牛排` remains a tag. It is useful as a cuisine/format facet, but it should not return as a primary category unless it becomes a clear first-layer user intent with enough non-chain coverage.
- `韓式料理` is already a primary category. `#韓式` remains only as a secondary compatibility tag for clearly Korean or mixed-format restaurants.

Important:
- `#Brunch` may exceed count threshold but still stays tag.
- Reason: brunch is meal occasion / format, not cuisine axis.

## 4. 103-Shop Remap Table

### 4.1 High-Impact Moves

Old `高級餐廳` mental bucket is split back into cuisine categories:

| shop_id | 店名 | 舊類 | 新類 | badge / tag |
| --- | --- | --- | --- | --- |
| 10101 | 鼎泰豐 101店 | 高級入口代表店 | 中式料理 | `[高級]` |
| 10111 | 鼎泰豐 A4店 | 高級入口代表店 | 中式料理 | `[高級]` |
| 10114 | 鼎泰豐 A13店 | 高級入口代表店 | 中式料理 | `[高級]` |
| 10191 | 鼎泰豐 天母店 | 高級入口代表店 | 中式料理 | `[高級]` |
| 10198 | 鼎泰豐 南西店 | 高級入口代表店 | 中式料理 | `[高級]` |
| 10103 | 旭集 和食集錦 信義店 | 高級餐廳 | 自助餐 | `[高級]` |
| 10104 | INPARADISE 饗饗 微風信義店 | 高級餐廳 | 自助餐 | `[高級]`, `#景觀` |
| 10107 | 老井極上燒肉 台北信義店 | 高級餐廳 | 日式燒肉 | `[高級]` |
| 10125 | 夏慕尼新香榭鐵板燒 台北中山北店 | 高級餐廳 | 義法料理 | `[高級]`, `#鐵板燒` |
| 10149 | 夏慕尼新香榭鐵板燒 台北南昌店 | 高級餐廳 | 義法料理 | `[高級]`, `#鐵板燒` |
| 10176 | 島語 台北漢來店 | 高級餐廳 | 自助餐 | `[高級]` |

Required callouts:
- `10104 饗饗`: `高級餐廳 -> 自助餐 + [高級]`
- `10159 西堤`: `高級餐廳 -> 義法料理 + #牛排`
- `10190 弘大一號出口`: `日式燒肉 + #韓式 -> 韓式料理 + #韓式`

### 4.2 Full 103-Shop Remap

| shop_id | 店名 | 舊類 | 新類 | badge | tags | 備註 |
| --- | --- | --- | --- | --- | --- | --- |
| 10099 | 一蘭拉麵台灣台北本店 | 日式料理 | 2004 日式料理 | - | - | 不變 |
| 10100 | 一蘭 台灣台北別館 | 日式料理 | 2004 日式料理 | - | - | 不變 |
| 10101 | 鼎泰豐 101店 | 中式料理 | 2008 中式料理 | [高級] | - | 不變 |
| 10102 | 海底撈火鍋 信義微風南山店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10103 | 旭集 和食集錦 信義店 | 高級餐廳 | 2011 自助餐 | [高級] | - | 高級餐廳 -> 自助餐 |
| 10104 | INPARADISE 饗饗 微風信義店 | 高級餐廳 | 2011 自助餐 | [高級] | 景觀 | 高級主類取消；改自助餐 + [高級] |
| 10105 | 竹村居酒屋 | 居酒屋 | 2003 居酒屋 | - | - | 不變 |
| 10106 | 饗食天堂 台北信義店 | 高級餐廳 | 2011 自助餐 | - | 親子 | 高級餐廳 -> 自助餐 |
| 10107 | 老井極上燒肉 台北信義店 | 高級餐廳 | 2002 日式燒肉 | [高級] | - | 高級餐廳 -> 日式燒肉 |
| 10108 | 布納咖啡館 信義館 | 義法料理 | 2012 咖啡/甜點 | - | - | 義法料理 -> 咖啡/甜點 |
| 10109 | 刁民-酸菜魚 信義店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10110 | Woolloomooloo | 美式 / Brunch | 2007 義法料理 | - | 景觀 | 美式 / Brunch -> 義法料理 |
| 10111 | 鼎泰豐 A4店 | 中式料理 | 2008 中式料理 | [高級] | - | 不變 |
| 10112 | HOOTERS美式餐廳 信義店 | 義法料理 | 2010 美式料理 | - | - | 義法料理 -> 美式料理 |
| 10113 | KiKi餐廳（ATT 4 FUN信義店） | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10114 | 鼎泰豐 A13店 | 中式料理 | 2008 中式料理 | [高級] | - | 不變 |
| 10115 | 辛殿麻辣鍋｜信義店 | 高級餐廳 | 2001 火鍋 | - | 吃到飽 | 高級餐廳 -> 火鍋 |
| 10116 | 刁民-酸菜魚 信義松仁店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10117 | 【設備整修暫停營業】心潮飯店｜台北微風信義店 SINCHAO RICE SHOPPE | 中式料理 | 2008 中式料理 | - | 餐酒館 | 不變 |
| 10118 | 阿城鵝肉 吉林總店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10119 | 欣葉台菜創始店 | 中式料理 | 2008 中式料理 | - | 商務 | 不變 |
| 10120 | 雞家莊本店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10121 | 港都熱炒 民生東旗艦店Gandou restaurant(Minsheng East Road store) | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10122 | 軟食力 行天宮店 | 美式 / Brunch | 2010 美式料理 | - | Brunch,早午餐 | 美式 / Brunch -> 美式料理 |
| 10123 | 海霸王 中山店 HaiPaWang Zhongshan Store | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10124 | 小品雅廚 | 中式料理 | 2005 素食 | - | - | 中式料理 -> 素食 |
| 10125 | 夏慕尼新香榭鐵板燒 台北中山北店 | 高級餐廳 | 2007 義法料理 | [高級] | 鐵板燒 | 高級餐廳 -> 義法料理 |
| 10126 | 阿城鵝肉 吉林二店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10127 | 下港吔羊肉專賣店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10128 | 唐宮蒙古烤肉酸菜白肉餐廳 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10129 | 紅翻天生猛海鮮 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10130 | MAJI MAJI集食行樂 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10131 | 詹記麻辣火鍋 敦南店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10132 | 雙月食品社 森林公園店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10133 | 2J CAFE | 特色咖啡 | 2012 咖啡/甜點 | - | - | 特色咖啡 -> 咖啡/甜點 |
| 10134 | 湘八老 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10135 | 榮榮園浙寧餐廳 | 中式料理 | 2008 中式料理 | - | 商務 | 不變 |
| 10136 | Second Floor 貳樓敦南店 | 美式 / Brunch | 2010 美式料理 | - | Brunch | 美式 / Brunch -> 美式料理 |
| 10137 | 這一鍋 台北信義殿 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10138 | The Public House | 義法料理 | 2007 義法料理 | - | 餐酒館 | 不變 |
| 10139 | 小小樹食 敦南店 | 義法料理 | 2005 素食 | - | - | 義法料理 -> 素食 |
| 10140 | 樂子the Diner 瑞安店 | 美式 / Brunch | 2010 美式料理 | - | Brunch | 美式 / Brunch -> 美式料理 |
| 10141 | 葉公館滬菜 | 中式料理 | 2008 中式料理 | - | 商務 | 不變 |
| 10142 | BRUN不然-信義店(捷運大安站) | 美式 / Brunch | 2010 美式料理 | - | Brunch,早午餐 | 美式 / Brunch -> 美式料理 |
| 10143 | 大安站那邊 精緻熱炒 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10144 | 二本松涮涮屋 本館 | 火鍋 | 2001 火鍋 | - | 約會 | 不變 |
| 10145 | 杭州小籠湯包 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10146 | 享鴨 台北金山南店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10147 | 泰和樓 | 火鍋 | 2008 中式料理 | - | - | 火鍋 -> 中式料理 |
| 10148 | 孫立人將軍官邸（陸軍聯誼廳） | 高級餐廳 | 2008 中式料理 | - | 商務,包廂 | 高級餐廳 -> 中式料理 |
| 10149 | 夏慕尼新香榭鐵板燒 台北南昌店 | 高級餐廳 | 2007 義法料理 | [高級] | 鐵板燒 | 高級餐廳 -> 義法料理 |
| 10150 | 疍宅Egghost三元店 | 特色咖啡 | 2012 咖啡/甜點 | - | - | 特色咖啡 -> 咖啡/甜點 |
| 10151 | 深夜裡的法國手工甜點 | 義法料理 | 2012 咖啡/甜點 | - | 法式 | 義法料理 -> 咖啡/甜點 |
| 10152 | 和牛涮 台北羅斯福店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10153 | 黃龍莊 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10154 | 龍門客棧餃子館 (林森店) | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10155 | 盛園絲瓜小籠湯包 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10156 | 一番地壽喜燒 古亭店 | 火鍋 | 2001 火鍋 | - | 吃到飽 | 不變 |
| 10157 | 春水堂 中正店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10158 | 大樹先生的家 | 美式 / Brunch | 2010 美式料理 | - | 親子 | 美式 / Brunch -> 美式料理 |
| 10159 | 西堤牛排台北羅斯福店 | 高級餐廳 | 2007 義法料理 | - | 牛排 | 牛排主類取消；改義法 + #牛排 |
| 10160 | 新東南海鮮餐廳 松山店 | 中式料理 | 2008 中式料理 | - | 商務,包廂 | 不變 |
| 10161 | 龍都酒樓 內湖店 | 中式料理 | 2008 中式料理 | - | 商務,包廂 | 不變 |
| 10162 | 小紅莓石頭火鍋城 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10163 | 一千零一夜廚房 | 高級餐廳 | 2011 自助餐 | - | - | 高級餐廳 -> 自助餐 |
| 10164 | 青樓中式餐酒館 | 中式料理 | 2008 中式料理 | - | 餐酒館 | 不變 |
| 10165 | 梨谷韓式鐵板烤肉 忠孝總店 | 日式燒肉 | 2009 韓式料理 | - | 韓式 | 韓式主打店，歸入韓式料理 + #韓式 |
| 10166 | 潮肉壽喜燒-永吉店 | 高級餐廳 | 2001 火鍋 | - | 吃到飽 | 高級餐廳 -> 火鍋 |
| 10167 | 磚窯古早料理南港創始店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10168 | 石二鍋 台北捷運後山埤店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10169 | 蔬食百匯（首都松山店） | 高級餐廳 | 2005 素食 | - | - | 高級餐廳 -> 素食 |
| 10170 | 旭穗蔬食VEGANala | 特色咖啡 | 2005 素食 | - | - | 特色咖啡 -> 素食 |
| 10171 | 肉執事台北松山門市 | 中式料理 | 2002 日式燒肉 | - | - | 中式料理 -> 日式燒肉 |
| 10172 | 聚 日式鍋物 台北士林中正店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10173 | 燒肉Smile 台北內湖店 | 高級餐廳 | 2002 日式燒肉 | - | - | 高級餐廳 -> 日式燒肉 |
| 10174 | 悠悠龍貓咖啡 | 義法料理 | 2012 咖啡/甜點 | - | - | 義法料理 -> 咖啡/甜點 |
| 10175 | 肉次方 燒肉放題 台北峨眉店 | 日式燒肉 | 2002 日式燒肉 | - | - | 不變 |
| 10176 | 島語 台北漢來店 | 高級餐廳 | 2011 自助餐 | [高級] | - | 高級餐廳 -> 自助餐 |
| 10177 | 小尚品精制鍋物-木柵店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10178 | 雞老闆 桶仔雞 士林店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10179 | 青花驕麻辣鍋 台北中山北店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10180 | 小倉庫食研所 | 高級餐廳 | 2010 美式料理 | - | Brunch | 高級餐廳 -> 美式料理 |
| 10181 | Bogart's Smokehouse Taipei (美式木柴煙燻屋) OPEN til SOLDOUT | 日式燒肉 | 2010 美式料理 | - | - | 日式燒肉 -> 美式料理 |
| 10182 | 花漾夯夯鍋-政大店 / 火鍋259起 / 木柵火鍋吃到飽/木柵宵夜 | 高級餐廳 | 2001 火鍋 | - | 吃到飽 | 高級餐廳 -> 火鍋 |
| 10183 | 呼嚕小酒館 Purrson Bistro | 居酒屋 | 2007 義法料理 | - | 餐酒館 | 居酒屋 -> 義法料理 |
| 10184 | 村民食堂廚窗港點 士林官邸店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10185 | 海底撈火鍋 京站店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10186 | 海底撈火鍋 西門店하이디라오 훠궈 서문점ハイディラオ火鍋 HaiDiLaoHotPot | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10187 | 布納咖啡館 內湖館 | 義法料理 | 2012 咖啡/甜點 | - | - | 義法料理 -> 咖啡/甜點 |
| 10188 | 築間幸福鍋物 台北內湖店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10189 | 刁民-酸菜魚 西門中華店 | 中式料理 | 2008 中式料理 | - | - | 不變 |
| 10190 | 弘大一號出口 | 火鍋 | 2009 韓式料理 | - | 韓式 | 韓式主打店，歸入韓式料理 + #韓式 |
| 10191 | 鼎泰豐 天母店 | 中式料理 | 2008 中式料理 | [高級] | - | 不變 |
| 10192 | 武侍酒 日式居酒屋 | 居酒屋 | 2003 居酒屋 | - | - | 不變 |
| 10193 | Lazy Pasta 慵懶義式廚房文山政大店 | 義法料理 | 2007 義法料理 | - | 義式 | 不變 |
| 10194 | 小廢墟咖啡 | 特色咖啡 | 2012 咖啡/甜點 | - | - | 特色咖啡 -> 咖啡/甜點 |
| 10195 | HI MATE ！(供餐至15:30） | 美式 / Brunch | 2010 美式料理 | - | Brunch,早午餐 | 美式 / Brunch -> 美式料理 |
| 10196 | 徙巷小餐酒x徙巷早午餐 | 美式 / Brunch | 2007 義法料理 | - | 餐酒館,Brunch | 美式 / Brunch -> 義法料理 |
| 10197 | 一番地 內湖宏匯店 | 火鍋 | 2001 火鍋 | - | - | 不變 |
| 10198 | 鼎泰豐 南西店 | 中式料理 | 2008 中式料理 | [高級] | - | 不變 |
| 10199 | 板前屋炭烤鰻魚飯(22:00最後出餐) | 居酒屋 | 2003 居酒屋 | - | - | 不變 |
| 10200 | 隱家拉麵 士林店 | 日式料理 | 2004 日式料理 | - | - | 不變 |
| 10201 | Juicy Bun Burger 就是棒 美式餐廳 政大店 | 美式 / Brunch | 2010 美式料理 | - | - | 美式 / Brunch -> 美式料理 |

## 5. smart_type_id Rewrite Logic

Decision:
- Keep `smart_type_id(shop)` as compatibility shim if needed.
- Real logic should move to richer classifier output.

Target shape:

```python
{
  "primary_type_id": 2008,
  "badges": ["高級"],
  "tags": ["商務", "包廂"]
}
```

Recommended implementation:

### Step 1. Base category by `primary_type`

Map Google `primary_type` to only 12 main categories.

Examples:
- `hot_pot_restaurant` -> `2001`
- `yakiniku_restaurant` -> `2002`
- `korean_barbecue_restaurant` / `korean_restaurant` -> `2009`
- `indian_restaurant` / `thai_restaurant` / `vietnamese_restaurant` / `middle_eastern_restaurant` / `mexican_restaurant` -> `2013`
- `japanese_izakaya_restaurant` -> `2003`
- `ramen_restaurant` / `japanese_restaurant` -> `2004`
- `vegetarian_restaurant` / `vegan_restaurant` -> `2005`
- `italian_restaurant` / `french_restaurant` / `bistro` -> `2007`
- `taiwanese_restaurant` / `chinese_restaurant` / `dim_sum_restaurant` -> `2008`
- `american_restaurant` / `brunch_restaurant` / `australian_restaurant` -> `2010`
- `buffet_restaurant` / `cafeteria` -> `2011`
- `cafe` / `coffee_shop` / `dessert_shop` / `pastry_shop` -> `2012`

### Step 2. Deterministic name overrides

Do this before fuzzy keyword rules.

Examples:
- `鼎泰豐` -> `2008` + maybe `[高級]`
- `旭集` / `饗饗` / `饗食天堂` / `島語` -> `2011`
- `夏慕尼` -> `2007` + `#鐵板燒`
- `西堤` -> `2007` + `#牛排`
- `弘大一號出口` / `梨谷韓式鐵板烤肉` -> `2009` + `#韓式`
- `小小樹食` / `旭穗蔬食` / `蔬食百匯` / `小品雅廚` -> `2005`

### Step 3. Keyword correction

Run only when Step 1 and Step 2 are weak or conflicting.

Priority:
1. buffet / cafeteria
2. hotpot / sukiyaki / shabu
3. vegetarian / vegan
4. korean primary cuisine
5. international cuisine
6. yakiniku / barbecue
7. izakaya / pub
8. western / euro
9. brunch / american
10. cafe / dessert
11. japanese
12. chinese

Reason:
- Current code lets `高級`, `吃到飽`, `鐵板燒` over-influence `type_id`.
- New logic must classify cuisine first, then badge/tag second.
- Side dishes such as kimchi must not create `韓式料理` or `#韓式`; verified exceptions live in `manual_overrides.json` `suppress_tags`.

### Step 4. Badge extraction

Do not let badge rewrite primary category.

```python
primary = infer_primary_type(shop)
badges = infer_badges(shop)
tags = infer_tags(shop)
return primary
```

### Step 5. Tag extraction

Tags should be independent from main category.

Examples:
- `Brunch`, `早午餐`
- `牛排`
- `韓式` only for clearly Korean or mixed Korean-format restaurants, not side dishes
- `法式`, `義式`
- `餐酒館`
- `約會`, `商務`, `包廂`, `景觀`, `親子`
- `吃到飽`, `鐵板燒`

### Step 6. Compatibility rule

Short term:

```python
def smart_type_id(shop):
    return classify_shop(shop)["primary_type_id"]
```

Long term:
- store `primary_type_id`
- store badge relation separately
- store tags separately

## 6. Operating Principle

Final rule:

- 主分類 = 使用者第一層心智
- badge = 等級 / 榮譽 / premium signal
- tag = 情境 / 需求 / 搜尋輔助

Do not collapse these three axes into one `type_id`.
