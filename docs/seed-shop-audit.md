# Legacy Seed Shop Audit

## Status
- Source: `backend-java/src/main/resources/db/migration/V5__seed_taipei_shops.sql`
- Count: `25`
- Nature: early demo / manual seed data
- Quality: lower confidence than Google re-scraped `10099+` shop set

## Recommendation
- `P0`: do not feature on homepage station sections unless they have strong real photos and still fit the station story
- `P1`: replace with real Google-scraped equivalents where possible
- `P2`: if no reliable replacement, keep only as low-priority fallback in `/shops`

## Seed Shops
| ID | Name | Area | Recommendation |
| --- | --- | --- | --- |
| 10001 | 林東芳牛肉麵 信義店 | 信義 | replace / verify |
| 10002 | 老天祿滷味 信義店 | 信義 | replace / verify |
| 10003 | 春水堂 信義A8店 | 信義 | replace / verify |
| 10004 | 通化街胡椒餅 信義店 | 信義 | replace / verify |
| 10005 | Simple Kaffa 101 信義店 | 信義 | keep fallback only |
| 10006 | 金子半之助 微風信義店 | 信義 | replace / verify |
| 10007 | 涓豆腐 信義ATT店 | 信義 | replace / verify |
| 10008 | 吳留手 信義店 | 信義 | replace / verify |
| 10009 | 橘色涮涮屋 信義館 | 信義 | replace / verify |
| 10010 | 秦小姐豆漿 信義店 | 信義 | replace / verify |
| 10011 | 梁社漢排骨 松仁店 | 信義 | replace / verify |
| 10012 | 花藏雪 手作雪氷 信義店 | 信義 | replace / verify |
| 10013 | 麻古茶坊 市府店 | 信義 | replace / verify |
| 10014 | 劉山東小牛肉麵 中山店 | 中山 | replace / verify |
| 10015 | 阿國滷味 雙連店 | 中山 | replace / verify |
| 10016 | 五桐號 中山南西店 | 中山 | replace / verify |
| 10017 | 寧夏蚵仔煎 中山店 | 中山 | replace / verify |
| 10018 | 二會咖啡 中山店 | 中山 | replace / verify |
| 10019 | 藏壽司 中山站前店 | 中山 | replace / verify |
| 10020 | 起家雞 中山店 | 中山 | replace / verify |
| 10021 | 柒息地串燒居酒屋 中山店 | 中山 | replace / verify |
| 10022 | 青花驕 中山北店 | 中山 | keep fallback only |
| 10023 | 可蜜達炭烤吐司 中山店 | 中山 | replace / verify |
| 10024 | 鬍鬚張魯肉飯 中山店 | 中山 | replace / verify |
| 10025 | 雙連圓仔湯 | 中山 | keep fallback only |

## Next Action
1. build a `replacement target list` for top 10 seed shops still leaking into user-facing pages
2. scrape real Google entities for those shops
3. remove or hide unreplaced seed records from homepage and AI recommendations
