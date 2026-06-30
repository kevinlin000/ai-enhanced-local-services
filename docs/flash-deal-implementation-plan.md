# Flash Deal Implementation Plan

## Overview

Replace the public-facing `Hot Seat` wording with `Flash Deal / 限時餐券`, and turn the existing Heima-style seckill skeleton into a portfolio-ready flow: discover deal, claim deal, receive order id, block duplicate claims, and expose enough evidence for reviewers.

## Architecture Decisions

- Keep existing database tables (`tb_voucher`, `tb_seckill_voucher`, `tb_voucher_order`) to avoid a risky schema rename.
- Keep the existing Redis Lua + Redis Stream path for the claim hot path. It already matches the Heima Dianping pattern: atomic stock check, one-user-one-order set, stream message, async DB write.
- Add external aliases and UI copy using `flash deal` language. Old `hot-seat` endpoints remain backward-compatible.
- Do not move the main claim path to RabbitMQ in V1. RabbitMQ remains useful for notification/outbox follow-up, but replacing Redis Stream now adds risk without improving the demo.
- Do not add Bloom filter in V1. Add it only when invalid voucher-id traffic is part of the benchmark story.

## Task List

### Phase 1: Product Contract

- [x] Add Java aliases:
  - `GET /api/shop/{id}/flash-deals`
  - `POST /api/flash-deals/{id}/claim`
- [x] Keep old endpoints working:
  - `GET /api/shop/{id}/hot-seat-vouchers`
  - `POST /voucher-order/seckill/{id}`
- [x] Return reviewer-friendly claim payload: order id, status, and message.

### Phase 2: Web Flow

- [x] Rename UI labels from `Hot Seat` to `限時餐券`.
- [x] Add a claim button to shop detail flash-deal cards.
- [x] Show success, duplicate, sold-out, and generic failure states inline.

### Phase 3: AI / LINE Language

- [x] Rename AI tool labels and prompts to `限時餐券`.
- [x] Keep internal tool name stable unless a full API migration is needed.
- [x] Return claim success text without `Hot Seat`.

### Phase 4: Verification

- [x] Add Java controller contract tests for flash deal alias and payload.
- [x] Run focused Java/Web/AI checks.
- [x] Capture one Flash Deal screenshot for the portfolio evidence set.

## Later, If Needed

### RabbitMQ

Use RabbitMQ for post-claim events: LINE confirmation, merchant notification, reconciliation, and retry/DLQ evidence. Keep Redis Lua/Stream as the hot-path queue unless there is a measured need to replace it.

### Bloom Filter

Add Bloom filter only when the demo includes high-volume invalid voucher-id traffic. It should protect the query/claim validation layer, not replace Redis Lua stock protection.

## Acceptance Criteria

- User-facing product no longer says `Hot Seat`.
- Shop detail page exposes active limited-time meal vouchers.
- User can claim a flash deal and see an order id.
- Duplicate claims and sold-out states return clear messages.
- AI can recommend and claim a flash deal without using stale `Hot Seat` wording.
- Portfolio evidence includes one Flash Deal UI screenshot plus API verification.
