# Case Study 04: Taxonomy 從 0 到 production — V15-V19 五輪 migration

**TL;DR** ByteBites 早期店家分類把所有 tag 塞在一個 string 欄位，例如「火鍋,信義,平價」。這無法支撐語意搜尋與推薦。我重設成 3 軸 taxonomy (type / badge / tag)，用五輪 Flyway migration backfill 103 家店，並用 Google Places `primary_type` 抓出 spec 本身錯誤的盲點。

**Tech:** MySQL / Flyway / Spring Boot / Google Places API  
**Repo:** `backend-java/src/main/resources/db/migration/`

## 1. 起點：單一 tag string

早期 schema：

```sql
CREATE TABLE tb_shop (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255),
    tag VARCHAR(255) -- "火鍋,信義,平價,適合聚餐"
);
```

問題：

- query 只能 `LIKE '%火鍋%'`
- 地區、類型、價位混在同一欄
- Qdrant filter 沒有結構化欄位可用
- Agent 無法知道「火鍋」是 category，「信義」是 district

要做 AI 推薦，資料結構要先正確。

## 2. 設計：3 軸 taxonomy

| Axis | Property | Examples |
|---|---|---|
| type | 主類別，互斥 | hotpot, japanese, brunch |
| badge | 店家屬性，多選 | high-end, classic, newly-opened |
| tag | 場景特色，多選 | date-night, family, business |

type 一家店只能有一個；badge / tag 是 many-to-many。

```sql
CREATE TABLE tb_shop_type_dict (
    id BIGINT PRIMARY KEY,
    code VARCHAR(32) UNIQUE,
    label_zh VARCHAR(64)
);

ALTER TABLE tb_shop ADD COLUMN type_id BIGINT;

CREATE TABLE tb_shop_badge (
    shop_id BIGINT,
    badge_id BIGINT,
    PRIMARY KEY (shop_id, badge_id)
);
```

FK 策略：

- shop -> dictionary: `ON DELETE RESTRICT`
- shop -> junction table: `ON DELETE CASCADE`

字典表不能被刪掉，店刪掉時中介表應該自動清。

## 3. 五輪 migration

| Version | Purpose |
|---|---|
| V15 | 新增 taxonomy schema |
| V16 | backfill 舊 tag string 到新表 |
| V17 | 修 dictionary label |
| V18 | 修小品雅廚分類錯誤 |
| V19 | 新增 `tb_shop_absa` JSON storage |

拆細的原因：每個 migration 一個邏輯變更，出問題時 rollback 範圍小。

## 4. V16 backfill：atomic + idempotent

V16 最複雜，要把 103 家店舊 tag 解析成 type、badge、tag。

設計原則：

- migration 一次完成
- Flyway transaction 失敗 rollback
- idempotent guard 避免重複跑

```sql
-- guard
SELECT COUNT(*) INTO @already_backfilled
FROM tb_shop
WHERE type_id IS NOT NULL;

-- parse type
UPDATE tb_shop
SET type_id = (SELECT id FROM tb_shop_type_dict WHERE code = 'hotpot')
WHERE tag LIKE '%火鍋%';
```

跑完驗證：103 家都有 type，沒有 NULL，沒有重複 badge relation。

## 5. V18：spec 本身錯了

spot check 發現「小品雅廚」被歸為素食，但評論有「紅燒蹄髈必點」。

問題不是 classifier，而是 spec。我的 keyword rule 把「雅廚」誤判成素食關鍵字。LLM classifier 100% 符合 spec，但 spec 錯了。

這是「validator 不能跟 validated 來自同一份資料」的問題。

修法：用 Google Places `primary_type` 當第三方 anchor。

```python
def verify_shop(shop):
    google_primary = shop.google_places_primary_type
    my_type = shop.taxonomy_type.code

    if my_type == "vegetarian" and "vegetarian" not in google_primary:
        flag(shop, "POTENTIAL_MISCLASSIFICATION")
```

第三方 anchor 抓到 3 家可疑分類，手動 review 後修掉小品雅廚。

## 6. V19：ABSA JSON column trade-off

ABSA schema 還在迭代。選項：

| Option | Pros | Cons |
|---|---|---|
| normalized tables | queryable, clean schema | migrations frequent, joins heavy |
| JSON column | flexible, fast writes | harder cross-shop SQL aggregate |

我選 JSON，因為只有 103 家店，schema 還在演進，MySQL JSON functions 夠用。

```sql
CREATE TABLE tb_shop_absa (
    shop_id BIGINT PRIMARY KEY,
    aspects JSON NOT NULL,
    char_hit_rate DECIMAL(4,3),
    semantic_hit_rate DECIMAL(4,3),
    FOREIGN KEY (shop_id) REFERENCES tb_shop(id) ON DELETE CASCADE
);
```

trade-off 寫進 `docs/taxonomy-spec.md`，避免後人不知道為什麼這樣選。

## 7. 我學到的事

**validator 不能 validate 自己。** classifier 對 spec 一致，不代表 spec 正確。

**migration 要 atomic + idempotent。** 多花幾行 guard 可以避免重跑災難。

**FK 策略要按方向設計。** RESTRICT 與 CASCADE 不是習慣，是語意。

**JSON column 不是偷懶。** 在小規模且 schema 迭代期，它是合理 trade-off。

## English Version

# Case Study 04: Taxonomy From Zero to Production — V15-V19

ByteBites originally stored all shop tags in one string field. That made filtering, semantic search, and recommendation logic fragile. I redesigned taxonomy into three axes: type, badge, and tag.

The migration spanned five Flyway versions: schema creation, backfill, label fix, one data correction, and ABSA storage. V16 was the core backfill: it had to be atomic, guarded, and idempotent.

The most important lesson came from V18. A shop was classified as vegetarian because my spec had a bad keyword rule. The classifier matched the spec perfectly, but the spec was wrong. The fix was to add a third-party validation anchor from Google Places `primary_type`.

Good data systems need independent validation. A validator that only checks against the same flawed source cannot catch source-level bugs.
