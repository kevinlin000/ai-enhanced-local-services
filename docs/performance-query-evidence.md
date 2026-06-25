# ByteBites 效能與查詢證據

這份文件說明 portfolio release 中的關鍵查詢路徑、支援索引與狀態轉移設計。

它不宣稱未量測的 benchmark 數字。這裡的目標更務實：讓 reviewer 可以看到哪些 runtime hot paths 已有索引與程式碼錨點保護，也能清楚知道目前尚未證明 production-scale throughput。

## 範圍

目前最重要的 runtime surfaces：

- 我的訂位：讀取近期訂位與 latest open incident。
- 訂位 / 改單：座位容量檢查與 reserve / release。
- 商家 incident queue：列出 open incidents 與同日替代時段建議。
- 訂金差額與退款營運：merchant adjustment queue、refund operations digest。
- Refund reconciliation：callback audit lookup 與 event-key idempotency。
- Refund operations notification：scheduler-ready cooldown policy。

目前資料規模是 portfolio release：599 家 active Taipei shops、demo dataset，以及聚焦的營運流程。這份證據證明的是 query shape 與 index coverage，不是正式 production 流量容量。

## 查詢路徑對照

| Runtime path | Query shape | 支援證據 |
|---|---|---|
| 我的訂位列表 | `user_id IN (...) ORDER BY created_at DESC`，再依 `booking_code` 找 latest open incident | `idx_booking_user_created`, `idx_booking_user_status`, `idx_booking_incident_booking_status` |
| 依公開訂位編號查詢 | `booking_code = ?` | `tb_booking.booking_code` unique key 與 `idx_booking_code` |
| Idempotent reserve | `idempotency_key = ?` 與 idempotency lock row | `uk_booking_idempotency_key`, `tb_booking_idempotency_lock` |
| 座位 reserve / release | `shop_id + booking_date + booking_time + table_type` update | `uk_booking_slot`, `idx_booking_slot_lookup` |
| Hold expiration | `status + hold_expires_at` | `idx_booking_hold_expiry` |
| 停車提醒候選 | `parking_reminder_enabled + sent_at + booking_date + booking_time + status` | `idx_booking_parking_reminder` |
| 商家 incident queue | `shop_id + status ORDER BY created_at DESC LIMIT 30` | `idx_booking_incident_shop_status` |
| 顧客 incident list | `booking_code ORDER BY created_at DESC LIMIT 20` | `idx_booking_incident_booking_status` |
| Pending proposal scan | `proposal_status + proposed_at` | `idx_booking_incident_proposal_status` |
| Deposit adjustment queue | `shop_id + status ORDER BY created_at DESC LIMIT 50` | `idx_deposit_adjustment_shop_status` |
| Settlement queue | `shop_id + settlement_status + created_at` | `idx_deposit_adjustment_settlement` |
| Refund SLA / escalation | `shop_id + adjustment_type + settlement_status + refund_escalated_at` | `idx_deposit_adjustment_refund_escalation` |
| Refund callback idempotency | `event_key = ?` | `uk_refund_reconciliation_event_key` |
| Refund audit by adjustment / booking | `adjustment_id + created_at`, `booking_code + created_at` | `idx_refund_reconciliation_adjustment`, `idx_refund_reconciliation_booking` |
| Refund digest cooldown | `shop_id + notification_type + status + sent_at` | `idx_merchant_notification_last_sent` |

## 狀態轉移設計

### 座位保留

`BookingSlotInventory.reserve` 使用單一 conditional update：

```sql
UPDATE tb_booking_slot_inventory
SET booked_count = booked_count + ?
WHERE shop_id = ?
  AND booking_date = ?
  AND booking_time = ?
  AND table_type = ?
  AND booked_count + ? <= capacity
```

容量檢查留在資料庫 update 裡完成，不先把 count 撈到 memory 再決定是否寫回，降低 race condition。

### 改單順序

`BookingRescheduleService` 先 reserve 新時段，再 release 舊時段。若新時段已滿，原訂位保持不變。

這首先是 correctness 設計，同時也避免失敗後再做補償修復。

### Incident proposal

商家 incident queue 以 owned shop 與 status scope 查詢。替代時段從同日 slot inventory 計算，候選時間固定且最多回傳三個。

這讓 demo 與審查路徑 deterministic，不把 incident handling 變成無邊界搜尋。

### Refund operations

退款營運拆成三層：

- 目前 adjustment 狀態在 `tb_booking_deposit_adjustment`。
- provider reconciliation audit 在 `tb_booking_refund_reconciliation_event`。
- 商家 digest cooldown 在 `tb_merchant_notification_dispatch`。

這樣商家後台回答「現在要處理哪些退款」時，不需要反覆掃整個 audit history。

## 已納入驗證

輕量 verifier：

```bash
python3 scripts/verify-performance-query-evidence.py
```

它會檢查：

- 文件中提到的 index migrations 仍存在。
- 對應 service / controller query paths 仍存在。
- reviewer-facing 文件段落沒有漂移。

這支 verifier 已接進 `scripts/release-readiness.sh --offline`，因此查詢證據會隨 release gate 一起檢查。

## 這份證據不代表什麼

這份證據不證明 production-scale throughput。

正式 production rollout 仍需要：

- production-like seed volume 的 load test。
- MySQL slow query log review。
- production-like MySQL 上的 EXPLAIN plan。
- latency SLO dashboard。
- cache hit-rate measurement。
- LINE 與 PSP callback 的 provider latency / retry budget。

可用的回答方式：

```text
目前 portfolio release 證明的是 hot-path query shape 與 index coverage。
我不會在沒有 production-like data、EXPLAIN plan 和 load test 前宣稱 production throughput。
```

## 下一步效能工作

下一個有價值的效能 artifact 是 seeded EXPLAIN runner：

1. 從 clean migrated schema 啟動。
2. seed 固定數量的 bookings、incidents、adjustments、refund audit events。
3. 對上方 hot queries 執行 EXPLAIN。
4. 如果 MySQL 不再使用預期索引，就讓 verifier 失敗。

這會是正式宣稱 production performance 前更正確的下一步。
