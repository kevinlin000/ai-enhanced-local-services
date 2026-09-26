# ByteBites 全庫 Schema 說明

33 張表，由 55 個 Flyway migration 累積而成。這份文件說明它們怎麼分組，
以及哪些是核心、哪些是接手教學專案時留下來的。

- 線上 ER 圖：<https://dbdiagram.io/d/6ab73f570f25a52d01113ac2>（可縮放、可點選單張表）
- DBML 原始碼：[docs/dbml/bytebites-full-schema.dbml](dbml/bytebites-full-schema.dbml)
- 只想看訂位主線：[booking operations ER model](er-model-booking-operations.md)（9 張表）

---

## 分組總覽

| 分組 | 張數 | 內容 | 狀態 |
|---|---:|---|---|
| 身分與授權 | 4 | 使用者、個人資料、LINE 綁定、商家授權 | 核心 |
| 店家與內容 | 9 | 店家、分類、AI metadata、面向分析、徽章標籤、捷運站 | 核心 |
| 訂位營運 | 9 | 訂位、時段庫存、冪等鎖、臨場事件、訂金調整、退款對帳、候補、通知 | 核心 |
| 使用者偏好 | 3 | 私人記憶、收藏、個人化優惠 | 核心 |
| 餐券與秒殺 | 3 | 優惠券、秒殺庫存、餐券訂單 | 教學專案的底，已改成限時餐券 |
| 系統基礎 | 1 | Outbox 訊息表 | 機制完成，未接業務 |
| 教學專案遺留 | 4 | 探店、留言、關注、簽到 | 未使用，也未清除 |

---

## 1. 身分與授權（4 張）

`tb_user` 是顧客與商家共用的帳號表。台灣化之後主要走 LINE Login，
所以 V3 加了 `line_user_id` 欄位存 id_token 的 sub。

`tb_line_identity_link` 跟上面那個欄位的差別是**它支援多來源**：
LINE bot 的使用者可能還沒有平台帳號，這張表負責把兩邊綁起來。

`tb_merchant_shop` 是**商家授權邊界**。複合主鍵 `(user_id, shop_id)`，
`role` 依賴完整的使用者與店家組合，只看其中一邊沒有意義。
所有商家 API 一律先查這張表，查不到就回 403，不允許任何路徑繞過。

`tb_user_info` 是教學專案帶來的，本專案沒用到。

## 2. 店家與內容（9 張）

`tb_shop` 的 599 筆 active 資料是 ETL 抓回來的，經過兩輪篩選
（1545 → 779 → 599）。`x` / `y` 座標有兩個用途：回填最近捷運站、
計算到停車場的距離。

`tb_shop_ai_metadata` 與 `tb_shop_absa` 都是與店家一對一，但產生方式不同：

- **ai_metadata** 靠 prompt 約束。14 條規則要求招牌菜必須在評論中出現、
  禁止分析口吻、禁用套語清單、至少寫出一個具體菜色細節。
- **absa** 有程式驗證。雙層可信度檢查的結果直接存成欄位
  （`char_hit_rate`、`semantic_hit_rate`、`synonym_recovered`、`unverified_count`），
  UI 上顯示的準確度就是這幾個值。586 / 599 家有資料，缺的 13 家中有 12 家
  沒通過品質檢查、1 家可用評論不足 5 則。

`tb_badge_def` 與 `tb_tag_def` 用 `code` 當主鍵而不是流水號，
因為程式裡會直接引用這些 key。

## 3. 訂位營運（9 張）── 核心

這一組已經單獨畫成 [ER 圖](er-model-booking-operations.md)，這裡只補充幾個設計決定。

**對外用 `booking_code` 而不是 `id`。** 訂位流程橫跨網頁、LINE、商家後台、
付款回呼、退款對帳。如果對外都用資料庫主鍵，內部 row id 會流到 LINE 訊息
與 URL 上，別人看得出總量也猜得到相鄰的單。

**`tb_booking_slot_inventory` 的 `booked_count` 不開放手動改。**
它是扣容量那句條件式 UPDATE 累加出來的：

```sql
UPDATE tb_booking_slot_inventory
SET booked_count = booked_count + ?
WHERE shop_id = ? AND booking_date = ? AND booking_time = ? AND table_type = ?
  AND booked_count + ? <= capacity
```

影響行數 1 表示扣成功、0 表示已滿。商家後台只能調 `capacity`。

**`tb_booking_idempotency_lock` 是冪等專用的鎖表。**
流程是 double-checked locking：先查 `tb_booking`，沒查到才 `INSERT IGNORE`
佔位、`SELECT ... FOR UPDATE` 鎖住，拿到鎖之後再查一次。

**`tb_booking_incident` 把提案欄位放在同一列。** 這一版只允許一個事件
有一個待回覆提案，狀態機比較單純，LINE 與網頁的接受／拒絕路徑也清楚。
要支援多輪協商，第一個要拆出來的就是 proposal history 表。

**`tb_booking_deposit_adjustment` 存了看起來冗餘的三個金額欄位。**
`delta_amount` 可以由前兩者算出來，但對帳要看的是當時談定的金額，
不是現在重算的結果。

**`tb_booking_refund_reconciliation_event` 是 append-only。**
`event_key` 唯一，金流商重播幾次都只會留下一筆有效紀錄。

**`tb_user_notification.watch_id` 的唯一鍵**是候補通知三道冪等防護的最後一道
（撈的時候 `FOR UPDATE`、改狀態時再確認一次 ACTIVE、寫通知時 `INSERT IGNORE`）。

## 4. 使用者偏好（3 張）

`tb_dining_memory` 的唯一鍵是 `(user_id, booking_code)`，同一筆訂位
重複送出會覆蓋而不是累積。`do_not_recommend` 為 true 的店家，
在 Python 產生推薦時會被排除並從候選補位。

## 5. 餐券與秒殺（3 張）

這條線的機制來自黑馬點評教學專案。我改的是持久化方式：
原本訂單放在 JVM 記憶體的佇列，服務重啟就遺失；改成寫進 Redis Stream
之後有落地、有消費者群組、有 pending list，消費端重啟可以把未處理完的撿回來。

`tb_seckill_voucher.stock` 是資料庫裡的庫存，實際搶購時庫存在 Redis，
由 Lua 腳本一次完成庫存檢查、一人一單檢查、扣庫存、投遞訊息四件事。

## 6. 系統基礎（1 張）

`outbox_message` 是 Outbox 模式的訊息表。想解決的是雙寫問題：
先寫資料庫再發訊息，佇列掛了事件就不見；先發訊息再寫資料庫，
交易回滾別人就收到一筆不存在的訂位。

**機制、三次重試、死信佇列都完成並驗證過，但目前只有一個示範端點會寫入。**
訂位付款還是直接處理。接之前得先決定哪些事件要發、消費端失敗怎麼補、
重複消費由誰去重，這幾個問題沒想清楚就接，只是把複雜度換個地方放。

## 7. 教學專案遺留（4 張）

`tb_blog`、`tb_blog_comments`、`tb_follow`、`tb_sign` 是黑馬點評的
達人探店、留言、關注、簽到功能。本專案沒用到，也沒有清除——
清掉要動 migration，風險大於收益。

---

## 正規化

核心交易模型符合 1NF / 2NF / 3NF，詳細判斷見
[booking operations ER model 的正規化檢查](er-model-booking-operations.md#正規化檢查)。

有三處刻意保留了可以計算得出的欄位，都是為了稽核：

1. `tb_booking_deposit_adjustment` 的三個金額欄位
2. `tb_booking_incident` 的提案欄位（未拆成獨立表）
3. `tb_merchant_notification_dispatch` 的統計快照

這些數值必須保留當下的狀態，事後重算會失去決策時的脈絡。

---

## 索引

40 條自訂索引，全部從實際查詢路徑反推，沒有對應查詢的索引不建立。
複合索引的欄位順序遵循「等值條件在前、範圍條件在後」。
查詢路徑與索引的對照見 [performance-query-evidence.md](performance-query-evidence.md)。

這些索引是依查詢路徑推導的，不是壓測調校的結果，
也尚未在高基數資料上驗證過選擇性。
