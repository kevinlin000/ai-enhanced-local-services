# Taxonomy Audit

- Unique shops scanned: 600
- Audit rows: 0
- Korean-tagged rows needing review: 0

## Category Distribution

- 2001 火鍋: 88
- 2002 日式燒肉: 57
- 2003 居酒屋: 68
- 2004 日式料理: 78
- 2005 素食: 26
- 2007 義法料理: 78
- 2008 中式料理: 79
- 2009 韓式料理: 16
- 2010 美式料理: 49
- 2011 自助餐: 8
- 2012 咖啡/甜點: 43
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
- 法式: 18
- 韓式: 16
- 泰式: 12
- 景觀: 11
- Brunch: 11
- 中東: 8
- 鐵板燒: 7
- 印度: 6
- 包廂: 3

## Flag Distribution


## Recommendation

- Keep `日式料理` as a Japanese-only primary category.
- Use `韓式料理` as a dedicated primary category for clearly Korean restaurants.
- Use `異國料理` for Indian, Thai, Middle Eastern, Vietnamese, Mexican, and similar cuisines instead of forcing them into `中式料理` or `義法料理`.
- Keep the `韓式` tag for compatibility and mixed-format restaurants, but do not use `日韓料理` as a combined category.
- Review high-priority rows first, then add classifier overrides or DB migrations for confirmed fixes.

## Top 0 Review Rows

| priority | shop_id | name | category | tags | flags | suggestion | evidence |
| ---: | ---: | --- | --- | --- | --- | --- | --- |
