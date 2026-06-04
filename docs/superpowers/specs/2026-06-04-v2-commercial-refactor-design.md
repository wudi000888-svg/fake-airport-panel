# v2.0.0 Commercial Refactor Design

## Scope

v2.0.0 is a high-risk full-system refactor for the Singapore test environment. It may reset or migrate test data on Singapore, but it must not touch Hong Kong production. The release goal is to move fake-ui from a functional single-file panel into a commercial-grade, mobile-first, modular system while keeping the core product positioning: one VPS as a stable entry point that orchestrates multiple independently controlled proxy exits.

## Goals

| Area | Goal |
|---|---|
| Mobile UX | Make the user panel comfortable on 375px phones, with bottom navigation, card-based order/payment/subscription flows, and no horizontal table scrolling for primary user tasks. |
| Admin UX | Keep desktop data density while adding mobile-friendly admin task flows for users, orders, payments, nodes, and settings. |
| Frontend architecture | Replace the single 880-line `app.js` with focused ES modules while staying frontend/backend separated. |
| Database | Add SQLite as the default v2 runtime store, with JSON import/export compatibility for upgrades and rollback. |
| Cache | Add explicit TTL caches for dashboard, subscription, node status, payment rates, and chain/RPC checks. |
| Commercial readiness | Improve plan purchase, payment status, subscription access, account safety, admin operations, and release/deploy flows. |

## Non-Goals

| Item | Reason |
|---|---|
| Multi-server control plane | Too large for this release and not required for the current single-VPS positioning. |
| PostgreSQL as mandatory dependency | SQLite is simpler for single VPS and keeps install friction low; repository boundaries should allow PostgreSQL later. |
| Wallet private key custody | v2 remains receive-only by default. Hot wallet/private-key automation stays out of this refactor unless explicitly approved later. |
| Touching Hong Kong production | Hong Kong runs real business and is excluded from all destructive v2 testing. |

## Architecture

v2 keeps the existing Python HTTP service and static frontend deployment model, but reorganizes both sides into modules:

| Layer | v2 Direction |
|---|---|
| Frontend | Native ES modules under `baseline/frontend/assets/js/`; CSS split into tokens, layout, components, pages, and utilities. |
| API | Keep `/api/*` endpoints but add resource-specific endpoints so the frontend does not depend on one giant dashboard payload. |
| Domain services | Preserve current service modules but move persistence behind repositories. |
| Persistence | Add `db.py`, schema migrations, repositories, and JSON import/export tools. |
| Cache | Add `cache_store.py` with named TTL caches and invalidation helpers. |
| Deployment | Docker image initializes/migrates SQLite on startup; install scripts can reset Singapore test data but must back up before doing so. |

## Frontend Design System

fake-ui is an operational SaaS/admin product, not a landing page. The visual style should be restrained, dense, and touch-friendly.

| Token | Direction |
|---|---|
| Layout | Mobile first at 375px, tablet at 768px, desktop at 1200px+. |
| Navigation | Mobile bottom nav for primary user views; admin gets bottom nav for top tasks plus overflow menu. Desktop keeps left/top navigation. |
| Surfaces | Use flat surfaces with 6-8px radius, clear borders, and limited shadows. No decorative gradient/orb backgrounds. |
| Typography | 16px body minimum on mobile, tabular numbers for quotas/prices/confirmations. |
| Color | Neutral work UI with semantic blue primary, green success, amber pending, red danger. Avoid one-note purple/blue gradients. |
| Touch targets | 44px minimum height, 8px minimum spacing between tappable controls. |
| Tables | Desktop tables remain; mobile converts important rows into cards with primary action buttons. |
| Feedback | Every async action has loading/disabled state and visible success/error result. |
| Accessibility | Visible labels, focus rings, color plus text for status, and no hover-only controls. |

## Frontend Modules

| Module | Responsibility |
|---|---|
| `js/main.js` | App boot, route dispatch, global state wiring. |
| `js/api.js` | Fetch wrapper, auth/session refresh, error normalization. |
| `js/state.js` | Client cache, current route, busy/error state, cache invalidation. |
| `js/router.js` | History navigation and route guards. |
| `js/components/` | Buttons, pills, cards, tables, sheets, forms, QR/payment blocks. |
| `js/pages/user/` | Dashboard, plans, orders, subscriptions, account. |
| `js/pages/admin/` | Overview, users, orders, payments, nodes, settings, audit, backups. |
| `js/utils/` | Escaping, formatting, dates, money, bytes, clipboard. |

## Database Design

SQLite is the default v2 database at `data/panel/fake-ui.db`.

| Table | Purpose |
|---|---|
| `users` | Account, quota, expiry, plan, subscription token, status. |
| `plans` | Plan catalog, price, days, traffic, enabled flag. |
| `orders` | Create/renew orders, payment status, lifecycle timestamps. |
| `payment_methods` | Receive-only wallet address and chain defaults. |
| `payments` | Payment intents, locked crypto amount, txid, status, confirmations. |
| `nodes` | VLESS/Hysteria2 node catalog and outbound settings. |
| `registrations` | User registration requests. |
| `password_resets` | Password reset requests. |
| `audit_logs` | Admin/user operation events. |
| `subscription_access` | Subscription access logs and rate-limit evidence. |
| `settings` | Small key/value settings, including app URLs and payment rates cache metadata. |
| `schema_migrations` | Applied migration versions. |

Repositories should expose current store-like functions first (`list_users`, `get_order`, `save_payment`) so services can migrate incrementally.

## JSON Compatibility

| Flow | Requirement |
|---|---|
| Import | `scripts/migrate-json-to-sqlite.py --data-dir data/panel --db data/panel/fake-ui.db` imports existing JSON files. |
| Export | `scripts/export-sqlite-to-json.py` writes public-safe JSON backup format compatible with current backup flow. |
| Rollback | Deployment backs up both DB and JSON before migration. |
| Singapore reset | Add an explicit `--reset-test-data` option for Singapore only; no automatic data deletion by default. |

## Cache Design

| Cache | TTL | Invalidated By |
|---|---:|---|
| Dashboard summary | 10s | Any user/order/payment/node/plan write. |
| Public nodes/subscription payload | 15s | Node, user, quota, link settings changes. |
| Payment rates | Existing locked-order behavior plus 5m rate cache | Payment rate override changes. |
| Chain RPC health | 60s | Payment method change or manual refresh. |
| Subscription access summary | 30s | New access log events. |

The cache must never store secrets in public responses. Admin-only and user-only payloads use separate keys.

## API Changes

v2 keeps `/api/dashboard` for compatibility but introduces smaller endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/me` | Current user profile, quotas, subscription status. |
| `GET /api/app-shell` | Role, nav, app config, feature flags. |
| `GET /api/orders?bucket=pending|ambiguous|history` | Paginated orders. |
| `GET /api/payments?status=active|history` | Paginated payments. |
| `GET /api/admin/overview` | Admin summary cards and alerts. |
| `GET /api/admin/users` | Paginated users. |
| `GET /api/admin/nodes` | Node list and health summary. |
| `POST /api/cache/clear` | Admin-only cache clear for diagnostics. |

Existing POST action endpoints may remain initially, but the frontend should gradually use resource-specific APIs.

## Mobile UX Flows

| Flow | Mobile Behavior |
|---|---|
| Login/register | Full-width form, 44px controls, clear password and request states. |
| User dashboard | Top status card with expiry/quota, quick buttons for subscription, renew, orders. |
| Purchase | Plan cards, order confirmation sheet, payment method picker, QR/payment status screen. |
| Payment | Status timeline: created, waiting, detected, confirmed, ambiguous. TXID input appears only when needed. |
| Subscription | Copy links, QR view, node cards, reset subscription action with confirmation. |
| Admin orders | Search/filter, status buckets, row cards on mobile, confirm/cancel/refresh actions as bottom sheet. |
| Admin nodes | Node health cards, outbound mode editor, exit test result, batch refresh. |

## Testing Strategy

| Test Area | Required Coverage |
|---|---|
| Database | Migration, CRUD repositories, rollback/export, JSON compatibility. |
| Cache | TTL hit/miss, invalidation after writes, user/admin separation. |
| API | New resource endpoints, auth/role permissions, pagination. |
| Frontend | Source tests for module boundaries, role navigation, mobile labels/actions, no secret leakage. |
| Browser | Playwright/in-app browser checks at 375, 768, and 1440 widths for login, user order/payment, admin dashboard. |
| Deployment | Local tests, Docker build, Singapore reset/migration, health checks. |

## Rollout Plan

| Phase | Result |
|---|---|
| 1 | Create isolated v2 worktree and baseline tests. |
| 2 | Add SQLite schema/repositories while JSON stores still work. |
| 3 | Add import/export and switch services behind repository facade. |
| 4 | Add cache layer and resource APIs. |
| 5 | Split frontend modules and implement mobile shell. |
| 6 | Rebuild user flows: dashboard, plans, orders, payments, subscriptions. |
| 7 | Rebuild admin flows: overview, users, orders, payments, nodes, settings. |
| 8 | Run browser/mobile verification and deploy/reset Singapore test environment. |
| 9 | Tag `v2.0.0-beta` for Singapore testing before any production consideration. |

## Acceptance Criteria

| Requirement | Pass Criteria |
|---|---|
| Mobile usability | 375px viewport has no horizontal scroll in primary user flows; all touch targets are at least 44px. |
| Frontend modularity | No single frontend JS module exceeds 250 lines unless justified by generated/static data. |
| Database | New install uses SQLite; JSON import works; backup includes SQLite DB and export metadata. |
| Cache | Dashboard and subscription APIs use TTL cache with tests and invalidation. |
| Compatibility | Existing core features remain: users, plans, orders, subscriptions, VLESS/Hysteria2, payment verification. |
| Safety | No secrets committed; Singapore destructive reset requires explicit flag; Hong Kong is not touched. |
| Verification | Local tests pass; Singapore deployment passes remote tests and panel health; browser checks pass on mobile and desktop. |
