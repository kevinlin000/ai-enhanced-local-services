# ByteBites Booking Operations ER Model

This ER model focuses on the portfolio-critical workflow: recommendation becomes booking, booking can create incidents, incidents can create proposals, and paid booking changes can create deposit/refund operations.

It intentionally does not show every crawler, taxonomy, review, ABSA, or cache table. For interviews, the useful model is the Java-owned operational state model.

## Core Tables

| Table | Role |
|---|---|
| `tb_user` | Customer or merchant account. |
| `tb_shop` | Restaurant profile and merchant-owned operational unit. |
| `tb_merchant_shop` | Merchant-to-shop authorization mapping. |
| `tb_booking_slot_inventory` | Java-owned availability snapshot used for booking and proposal validation. |
| `tb_booking` | Source-of-truth booking record, including booking code, party size, time, payment state, and deposit totals. |
| `tb_booking_incident` | Real-time rescue incident and single pending proposal state. |
| `tb_booking_deposit_adjustment` | Manual or PSP-tracked top-up/refund adjustment created when paid booking changes affect deposits. |
| `tb_booking_refund_reconciliation_event` | Idempotent audit log for refund request/reconciliation callbacks. |
| `tb_merchant_notification_dispatch` | Cooldown and audit state for merchant operations notifications. |

## Diagram

```mermaid
erDiagram
    TB_USER ||--o{ TB_BOOKING : places
    TB_USER ||--o{ TB_MERCHANT_SHOP : manages
    TB_SHOP ||--o{ TB_MERCHANT_SHOP : authorized_by
    TB_SHOP ||--o{ TB_BOOKING : receives
    TB_SHOP ||--o{ TB_BOOKING_SLOT_INVENTORY : owns
    TB_SHOP ||--o{ TB_BOOKING_INCIDENT : scopes
    TB_SHOP ||--o{ TB_MERCHANT_NOTIFICATION_DISPATCH : sends
    TB_BOOKING ||--o{ TB_BOOKING_INCIDENT : raises
    TB_BOOKING ||--o{ TB_BOOKING_DEPOSIT_ADJUSTMENT : creates
    TB_BOOKING_INCIDENT ||--o{ TB_BOOKING_DEPOSIT_ADJUSTMENT : may_create
    TB_BOOKING_DEPOSIT_ADJUSTMENT ||--o{ TB_BOOKING_REFUND_RECONCILIATION_EVENT : audits

    TB_USER {
      bigint id PK
      varchar phone
      varchar nick_name
      varchar line_user_id
    }

    TB_SHOP {
      bigint id PK
      varchar name
      bigint type_id
      tinyint is_active
    }

    TB_MERCHANT_SHOP {
      bigint user_id PK
      bigint shop_id PK
      varchar role
    }

    TB_BOOKING_SLOT_INVENTORY {
      bigint id PK
      bigint shop_id
      date booking_date
      varchar booking_time
      varchar table_type
      int capacity
      int booked_count
    }

    TB_BOOKING {
      bigint id PK
      varchar booking_code UK
      bigint shop_id
      int people
      date booking_date
      varchar booking_time
      tinyint status
      int deposit_total
      varchar payment_trans_id
    }

    TB_BOOKING_INCIDENT {
      bigint id PK
      varchar booking_code
      bigint user_id
      bigint shop_id
      varchar incident_type
      varchar status
      varchar proposal_status
      date proposed_date
      varchar proposed_time
      datetime proposal_expires_at
    }

    TB_BOOKING_DEPOSIT_ADJUSTMENT {
      bigint id PK
      varchar booking_code
      bigint incident_id
      bigint shop_id
      varchar adjustment_type
      int delta_amount
      varchar settlement_status
      varchar settlement_trans_id
      datetime refund_escalated_at
    }

    TB_BOOKING_REFUND_RECONCILIATION_EVENT {
      bigint id PK
      varchar event_key UK
      bigint adjustment_id
      varchar booking_code
      varchar result_status
      int amount
    }

    TB_MERCHANT_NOTIFICATION_DISPATCH {
      bigint id PK
      bigint shop_id
      varchar notification_type
      varchar status
      int attention_count
      datetime sent_at
    }
```

## Interview Talking Points

- `tb_booking.booking_code` is the stable workflow key used across Web, LINE, incident, and payment operations.
- `tb_booking_incident` keeps the current proposal on the incident for the portfolio version: one incident, one pending proposal. If this became a multi-round negotiation product, proposal history should move to a separate table.
- `tb_booking_deposit_adjustment` separates booking mutation from money movement. Paid booking changes that alter deposit obligations create an adjustment instead of silently changing booking state.
- `tb_booking_refund_reconciliation_event` is append-only audit state for PSP callbacks and idempotent replay handling.
- `tb_merchant_shop` is the authorization boundary for merchant APIs; merchant screens should not query shops directly without this mapping.
- `tb_booking_slot_inventory` is intentionally Java-owned demo availability, so incident proposals and booking changes are deterministic during review.
