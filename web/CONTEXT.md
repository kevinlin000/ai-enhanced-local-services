# Web Context

## Scope

`web` owns the Next.js customer-facing interface for discovery, AI concierge, restaurant detail, booking, payment demo, notifications, and portfolio-ready demo flows.

## Technology

- Next.js
- React
- TypeScript
- Tailwind CSS

## Domain Terms

- `AI concierge`: interactive restaurant discovery assistant
- `Shop card`: restaurant summary UI
- `Booking flow`: date/time/party-size selection through confirmation
- `Deposit CTA`: UI path that moves a held booking to payment demo
- `Notification center`: user-visible booking and status updates

## Boundaries

- Web should present state returned by Java/Python rather than inventing business state.
- Visual changes should be checked in a real browser on mobile and desktop when they affect layout.
- Keep demo flows aligned with README and portfolio narrative.
