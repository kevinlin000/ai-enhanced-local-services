# ByteBites Performance And Query Evidence

This document is the reviewer-facing performance story for the portfolio release.

It does not claim synthetic benchmark numbers. The goal is narrower and more useful for interviews: identify the hot operational query paths, show the supporting indexes, and explain where the system relies on deterministic state transitions instead of expensive or ambiguous runtime work.

## Scope

The critical runtime surfaces are:

- My Bookings loading recent user bookings and latest open incidents.
- Booking reserve/reschedule capacity checks.
- Merchant incident queue and same-day alternative slot suggestions.
- Deposit adjustment and refund operations digest.
- Refund reconciliation audit lookup and idempotency.
- Scheduled refund operations notification policy.

The data scale for the current portfolio release is modest: 600 active Taipei shops, a reviewer demo dataset, and focused operational workflows. The proof here is query shape and index coverage, not production traffic capacity.

## Query Path Map

| Runtime Path | Query Shape | Supporting Evidence |
|---|---|---|
| My Bookings list | `user_id IN (...) ORDER BY created_at DESC`, then latest open incident by `booking_code` | `idx_booking_user_created`, `idx_booking_user_status`, `idx_booking_incident_booking_status` |
| Booking lookup by public code | `booking_code = ?` | `tb_booking.booking_code` unique key and `idx_booking_code` |
| Idempotent reserve | `idempotency_key = ?` plus idempotency lock row | `uk_booking_idempotency_key`, `tb_booking_idempotency_lock` |
| Slot reserve/release | `shop_id + booking_date + booking_time + table_type` update | `uk_booking_slot`, `idx_booking_slot_lookup` |
| Hold expiration | `status + hold_expires_at` | `idx_booking_hold_expiry` |
| Parking reminder candidates | `parking_reminder_enabled + sent_at + booking_date + booking_time + status` | `idx_booking_parking_reminder` |
| Merchant incident queue | `shop_id + status ORDER BY created_at DESC LIMIT 30` | `idx_booking_incident_shop_status` |
| Customer incident list | `booking_code ORDER BY created_at DESC LIMIT 20` | `idx_booking_incident_booking_status` |
| Pending proposal scan | `proposal_status + proposed_at` | `idx_booking_incident_proposal_status` |
| Deposit adjustment queue | `shop_id + status ORDER BY created_at DESC LIMIT 50` | `idx_deposit_adjustment_shop_status` |
| Settlement queue | `shop_id + settlement_status + created_at` | `idx_deposit_adjustment_settlement` |
| Refund SLA / escalation | `shop_id + adjustment_type + settlement_status + refund_escalated_at` | `idx_deposit_adjustment_refund_escalation` |
| Refund callback idempotency | `event_key = ?` | `uk_refund_reconciliation_event_key` |
| Refund audit by adjustment or booking | `adjustment_id + created_at`, `booking_code + created_at` | `idx_refund_reconciliation_adjustment`, `idx_refund_reconciliation_booking` |
| Refund digest cooldown | `shop_id + notification_type + status + sent_at` | `idx_merchant_notification_last_sent` |

## State Transition Performance Choices

### Slot Reservation

`BookingSlotInventory.reserve` uses one conditional update:

```sql
UPDATE tb_booking_slot_inventory
SET booked_count = booked_count + ?
WHERE shop_id = ?
  AND booking_date = ?
  AND booking_time = ?
  AND table_type = ?
  AND booked_count + ? <= capacity
```

This keeps the capacity check inside the database update. The service does not load a count, decide in memory, and write later.

### Reschedule Ordering

`BookingRescheduleService` reserves the target slot before releasing the old slot. If the target slot is full, the original booking remains unchanged.

This is a correctness choice first, but it also prevents compensating repair work after a failed reschedule.

### Incident Proposal

The merchant incident queue is scoped by owned shop and status. Alternative slots are computed from same-day slot inventory, bounded by a fixed time list, and capped at three suggestions.

This keeps the reviewer demo deterministic and avoids turning incident handling into a broad search query.

### Refund Operations

Refund operations are split into:

- Adjustment state on `tb_booking_deposit_adjustment`.
- Provider reconciliation audit on `tb_booking_refund_reconciliation_event`.
- Merchant digest cooldown on `tb_merchant_notification_dispatch`.

That split avoids repeatedly scanning audit history to answer the current merchant dashboard question.

## What Is Already Guarded

The repository has a lightweight verifier:

```bash
python3 scripts/verify-performance-query-evidence.py
```

It checks that the documented query evidence still has:

- the expected index migrations,
- the operational service/query code paths,
- the reviewer-facing documentation sections.

The verifier is part of `scripts/release-readiness.sh --offline`, so query evidence drift is caught with the release gate.

## What This Does Not Prove

This evidence does not prove production-scale throughput.

Production rollout would still need:

- representative load tests against cloud-sized data,
- slow query log review,
- EXPLAIN plans on production-like MySQL,
- dashboard latency SLOs,
- cache hit-rate measurements,
- provider latency and retry budgets for LINE and PSP callbacks.

Interview answer:

```text
For the portfolio release I focused on hot-path query shape and index coverage.
I would not claim production throughput until I run EXPLAIN plans and load tests against production-like data and traffic.
```

## Next Performance Work

The next useful performance artifact would be a seeded benchmark runner that:

1. Starts from a clean migrated schema.
2. Seeds bookings, incidents, adjustments, and refund audit events at known volumes.
3. Runs EXPLAIN for the hot queries above.
4. Fails when MySQL stops using the intended indexes.

That would be the correct step before claiming production performance.
