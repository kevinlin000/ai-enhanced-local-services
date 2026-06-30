# Flash Deal Implementation Plan

## Overview

Replace the public-facing `Hot Seat` wording with `Flash Deal / 限時餐券`, and turn the existing Heima-style seckill skeleton into a portfolio-ready flow: discover deal, claim deal, receive order id, block duplicate claims, and expose enough evidence for reviewers.

## Product Positioning

`限時餐券` is not just a generic coupon module. In ByteBites it should represent a restaurant yield-management tool:

- For consumers: a visible reason to open the app now, compare restaurants, and book or claim before the deal ends.
- For merchants: a way to fill empty capacity, promote new menu items, and turn low-demand windows into measurable traffic.
- For the AI concierge: an extra ranking signal when a user asks for value, nearby options, or flexible dining.
- For the portfolio: a concrete high-concurrency story with Redis Lua, idempotency, async order creation, duplicate-claim protection, and merchant inventory evidence.

This is why the UI should expose deals at multiple decision points:

- Explore page badge and filter.
- AI recommendation cards.
- Shop detail claim card.
- Merchant inventory/orders view.

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
- [x] Show active flash-deal badges on discovery cards.
- [x] Add a flash-deal filter on the discovery page.
- [x] Seed enough demo campaigns to make the module visible across multiple restaurants.

### Phase 3: AI / LINE Language

- [x] Rename AI tool labels and prompts to `限時餐券`.
- [x] Keep internal tool name stable unless a full API migration is needed.
- [x] Return claim success text without `Hot Seat`.
- [x] Expose flash-deal availability on AI search result cards.

### Phase 4: Verification

- [x] Add Java controller contract tests for flash deal alias and payload.
- [x] Run focused Java/Web/AI checks.
- [x] Capture Flash Deal screenshots for explore badges, filtered explore, AI card, detail card, claim success, and merchant stock/orders.
- [x] Verify the claim path creates a demo voucher order and decrements stock.

## Recommended V2

### RabbitMQ

Use RabbitMQ for post-claim events: LINE confirmation, merchant notification, reconciliation, and retry/DLQ evidence. Keep Redis Lua/Stream as the hot-path queue unless there is a measured need to replace it.

Good portfolio V2 scope:

- Publish `voucher.claimed` after the Redis Stream order is confirmed.
- Consumer: LINE/web notification that the voucher is ready.
- Merchant: inventory dashboard event and daily claim digest.
- Ops: DLQ/retry panel for failed notifications.

### Bloom Filter

Add Bloom filter only when the demo includes high-volume invalid voucher-id traffic. It should protect the query/claim validation layer, not replace Redis Lua stock protection.

Good portfolio V2 scope:

- Initialize a Bloom filter with active voucher ids.
- Reject invalid voucher ids before DB/cache lookup.
- Add a benchmark showing invalid-id traffic reduction.

### Campaign Design

The next business-level improvement is campaign creation, not another claim button:

- Merchant chooses window, quantity, discount, minimum spend, and target intent (`約會`, `家庭`, `午餐`, `離峰`).
- Consumer sees urgency and fit: time remaining, remaining stock, and why the AI surfaced the deal.
- AI can say "這間有限時餐券，適合你想控制預算又可接受 20:00 用餐。"

## Acceptance Criteria

- User-facing product no longer says `Hot Seat`.
- Shop detail page exposes active limited-time meal vouchers.
- User can claim a flash deal and see an order id.
- Duplicate claims and sold-out states return clear messages.
- AI can recommend and claim a flash deal without using stale `Hot Seat` wording.
- Portfolio evidence includes one Flash Deal UI screenshot plus API verification.
- Reviewer can explain the module as both a business feature and a concurrency/system-design feature.
