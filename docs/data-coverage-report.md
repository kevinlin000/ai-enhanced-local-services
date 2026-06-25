# ByteBites Data Coverage Report

- Generated: `2026-06-25T07:45:34Z`
- Source: recovered MySQL + media manifest snapshot after the 2026-06-24 catalog recovery.
- Total active Taipei shops: `599`

## Coverage

| Area | Shops | Percent |
|---|---:|---:|
| Cover image/media | 599 | 100.0% |
| Price signal | 517 | 86.3% |
| District | 599 | 100.0% |
| MRT station | 177 | 29.5% |
| AI summary | 599 | 100.0% |
| ABSA | 586 | 97.8% |
| SQL reviews (legacy) | 0 | 0.0% |
| Mongo reviews | 599 | 100.0% |
| Media manifest entry | 599 | 100.0% |
| Media manifest reviews | 599 | 100.0% |
| Media manifest photos | 599 | 100.0% |
| Media manifest overview | 572 | 95.5% |

## Category Distribution

| Label | Count |
|---|---:|
| 火鍋 | 88 |
| 中式料理 | 80 |
| 日式料理 | 78 |
| 義法料理 | 78 |
| 居酒屋 | 68 |
| 日式燒肉 | 57 |
| 美式料理 | 49 |
| 咖啡/甜點 | 43 |
| 素食 | 25 |
| 韓式料理 | 15 |
| 異國料理 | 10 |
| 自助餐 | 8 |

## District Distribution

| Label | Count |
|---|---:|
| 大安 | 102 |
| 中山 | 78 |
| 信義 | 75 |
| 士林 | 54 |
| 中正 | 50 |
| 松山 | 49 |
| 內湖 | 46 |
| 萬華 | 45 |
| 文山 | 39 |
| 北投 | 24 |
| 南港 | 24 |
| 大同 | 13 |

## MRT Distribution

| Label | Count |
|---|---:|
| 未填 | 422 |
| 信義安和 | 39 |
| 中山 | 33 |
| 市政府 | 32 |
| 台北101/世貿 | 22 |
| 中山國小 | 17 |
| 象山 | 13 |
| 雙連 | 11 |
| 行天宮 | 10 |

## ABSA Gaps

13 active shops do not have ABSA rows after the recovery. This is intentional: 12 failed the hallucination-quality gate and 1 had fewer than 5 usable reviews. They remain searchable and have restored metadata/media; ABSA can be recomputed per shop after review rescue.

| ID | Shop | District | MRT | Price | AI Summary | ABSA |
|---:|---|---|---|---:|---:|---:|
| 10130 | MAJI MAJI集食行樂 | 中山 |  | 1 | 1 | 0 |
| 10131 | 詹記麻辣火鍋 敦南店 | 大安 |  | 1 | 1 | 0 |
| 10158 | 大樹先生的家 | 大安 |  | 1 | 1 | 0 |
| 10194 | 小廢墟咖啡 | 文山 |  | 1 | 1 | 0 |
| 10357 | 長生塩人 天母 | 士林 |  | 0 | 1 | 0 |
| 10426 | 老倉庫 | 士林 |  | 1 | 1 | 0 |
| 10430 | 集客人間茶館-東興店 | 松山 | 市政府 | 1 | 1 | 0 |
| 10456 | 初心菓寮 | 內湖 |  | 0 | 1 | 0 |
| 10514 | 沾美西餐廳 | 大安 | 信義安和 | 1 | 1 | 0 |
| 10687 | 山上走走 日式鍋物台北華山店 | 中正 |  | 0 | 1 | 0 |
| 10698 | 樂氣串燒居酒屋 | 大安 | 信義安和 | 1 | 1 | 0 |
| 10704 | PAI CAFÉ & BRUNCH 八德店 | 松山 |  | 1 | 1 | 0 |
| 10741 | Oregano奧瑞岡義式餐廳 | 大安 | 信義安和 | 1 | 1 | 0 |
