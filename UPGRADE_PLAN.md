# Repository Upgrade Plan

Audit date: 2026-10-05

## Executive summary

This repository is a small Django REST Framework storefront with product, collection, cart, customer, order, review, and JWT authentication endpoints. It has a useful domain starting point, but it is not currently reproducible or production-ready: dependency versions and setup instructions are absent, development secrets and database credentials are committed in settings, the committed SQLite database and Python bytecode are mixed into source control, and the checked-in test modules are empty placeholders.

The highest-priority risks are customer/cart/order authorization, order creation integrity under concurrent requests, and production configuration. Address those before broad refactoring or a framework-version jump.

## Implementation update

The requested development/showcase upgrade has now been implemented. The first-pass findings below describe the original repository state; the core application changes in this pass address those findings where they fit the showcase scope.

- Added a Django 5.2 / DRF 3.16 dependency manifest, `.env` support, SQLite-first settings, environment-based database configuration, a fresh ignored `showcase.sqlite3` local database, and `.gitignore` rules.
- Added OpenAPI/Swagger docs, JWT refresh rotation and blacklist support, safe default API authentication, and public read-only catalog endpoints.
- Added user-owned carts and scoped cart/order access. Checkout now validates ownership and stock, decrements stock atomically, stores order-item price snapshots, and consumes the cart in one transaction.
- Added shipping-address endpoints, order history, consistent conflict responses, demo seed data, setup/API documentation, and CI checks.
- Added API tests covering catalog permissions, cross-user access, cart updates, checkout success/failure, stock integrity, profiles, shipping address, review nesting, JWT refresh, docs, and order history.
- Preserved the existing `db.sqlite3`. It has inconsistent legacy migration records and is no longer the default local database; the new showcase DB is separate.

Validation completed: `manage.py check`, `manage.py makemigrations --check`, all 16 API tests, OpenAPI schema validation, `migrate`, and `seed_demo`.

This remains a showcase application: payment integration, email verification, production monitoring, and deployment automation are intentionally outside the scope. Review the `README.md` scope notes before using the demo credentials or fallback development secret anywhere shared.

## Findings

### Critical / fix before exposing the API

1. **Hard-coded secrets and database credentials; unsafe defaults.** `Ecommerce_Store/settings.py` commits a Django `SECRET_KEY`, sets `DEBUG = True`, leaves `ALLOWED_HOSTS` empty, and embeds MySQL root credentials. Read secrets and database config from environment-backed settings, fail closed when production configuration is missing, and add separate development/production settings or a validated environment switch. Rotate credentials that were real or reused.
2. **Cart and order ownership are not enforced.** Carts have no owner, cart-item routes accept any cart UUID, and `CreateOrderSerializer` accepts any existing cart UUID for any authenticated customer, then deletes that cart. A user can add to, inspect, or consume another user's cart if its ID is known. Define cart ownership (or a signed guest-cart flow), scope every nested queryset to the owner, and verify cart ownership inside order creation.
3. **Order placement does not reserve inventory or guarantee single consumption.** The order flow snapshots price but does not check/decrement stock. Concurrent requests can create duplicate orders from one cart or sell beyond inventory. Lock the cart and relevant product rows in a transaction, validate stock, reserve/decrement inventory atomically, and make order placement idempotent or reject a previously consumed cart.
4. **No meaningful automated tests.** The app `tests.py` modules contain imports and placeholder comments. Add tests for authorization boundaries, cart/order behavior, stock and price snapshots, validation, and regressions before changing these behaviors.

### High priority

5. **No reproducible dependency/runtime contract.** There is no requirements/lock file, `pyproject.toml`, CI workflow, README, or deployment configuration. Establish supported Python/Django/DRF versions, lock dependencies, document local setup and migrations, and add CI for linting, migration checks, and tests. As of this audit, Django 5.2 is an LTS line and Django 6.0 is available; select the target only after verifying compatibility of Djoser, SimpleJWT, django-filter, debug-toolbar, and the database driver. DRF 3.16 supports modern Django releases, but this repository does not declare its installed versions. See [Django supported versions](https://www.djangoproject.com/download/#supported-versions) and [DRF 3.16 support notes](https://www.django-rest-framework.org/community/3.16-announcement/).
6. **Development tooling is enabled unconditionally.** `debug_toolbar` is installed, its middleware is active, and `/__debug__/` is routed regardless of environment. Keep it development-only and avoid exposing it in deployed environments.
7. **JWT/configuration hardening is incomplete.** Access tokens are configured for one day, and no throttling, API-wide permission defaults, schema/docs setup, or explicit refresh/rotation policy is visible. Choose token lifetimes and refresh/rotation behavior deliberately, add throttling for authentication and public write endpoints, and set safe default permissions so new endpoints do not accidentally become public.
8. **Business rules are not consistently enforced.** Product inventory is validated to a minimum of 1, but the admin `clear_inventory` action sets it to 0. Promotion discounts use `FloatField`; prices/discounts need explicit bounds and decimal semantics. Product deletion and collection deletion checks use application-level checks that can race with writes; prefer database constraints and/or transactional handling where appropriate.
9. **Model/API validation and response behavior need consistency.** Cart quantity increments use read-modify-save without locking; `ReviewViewSet` does not explicitly validate its parent product for writes; customer `me` assumes a Customer row exists; and status codes/response shapes are ad hoc. Centralize validation and use consistent 400/403/404/409 semantics.

### Maintainability and operations

10. **Generated/runtime artifacts are in source control.** `db.sqlite3`, tracked `__pycache__`/`.pyc` files, and local `.vscode` files appear in source control; there is no `.gitignore`. Remove generated files from version control where safe and add ignore rules. Preserve any needed database data before removing the database artifact.
11. **Migration history needs a clean review.** Review migration graph and deployed database state before squashing or rewriting anything. Never rewrite migrations already applied to shared data without a planned migration path.
12. **Code is difficult to audit.** `store/views.py` uses wildcard imports, duplicate imports, and broad viewsets; style is inconsistent, and `likes`, `tags`, and `playground` seem peripheral to the storefront. Define app boundaries and remove demo/dead code only after confirming intended use. Add formatting/linting/type checking incrementally.
13. **Query performance is not systematically controlled.** Some endpoints use `select_related`/`prefetch_related`, but order responses and collection/product routes need query-count review and pagination/ordering caps. Add indexes based on measured query plans and access patterns.
14. **No observable operational baseline.** Add structured logging, request/error correlation, health/readiness checks, and documented backup/restore and migration procedures. Add security headers, HTTPS/proxy settings, static/media handling, and production deployment checks for the actual host.

## Phased plan

### Phase 0 — establish the baseline

- Confirm deployment target, supported Python, database engine/version, and whether existing data must be preserved.
- Record current dependency versions from the actual deployment environment.
- Document current endpoint contract, migration state, and seed/test data needs.
- Add a README and `.gitignore`; stop tracking generated bytecode and local-only artifacts after checking data preservation.

**Exit criteria:** a new developer can install pinned dependencies, configure a local database, migrate, and start the app from documented steps.

### Phase 1 — security and access control

- Move secret key, database credentials, allowed hosts, debug flag, and environment-specific options out of source code.
- Separate development-only debug toolbar configuration from deployment configuration.
- Decide whether carts are authenticated-only or guest carts; enforce ownership consistently through cart, item, and checkout paths.
- Add authorization tests for customer profile, order list/detail, carts, nested items, and checkout.
- Set safe DRF defaults, explicit authentication behavior, token lifetime/refresh policy, and targeted throttles.

**Exit criteria:** production settings pass Django deployment checks; a user cannot read, mutate, or check out another user's cart/order.

### Phase 2 — transactional commerce invariants

- Define inventory semantics (available, reserved, backorder) and enforce them in a transactional checkout service.
- Lock rows or use conditional updates to prevent overselling and duplicate checkout; define idempotency behavior.
- Keep immutable order-item price/title snapshots as required for history.
- Make cart quantity updates concurrency-safe and enforce positive quantity and maximum limits.
- Add database constraints for uniqueness, nonnegative stock, bounded discounts/prices, and other domain invariants, using data migrations where needed.

**Exit criteria:** tests show invalid/parallel checkouts cannot oversell, duplicate orders, or change historical totals.

### Phase 3 — supported platform and delivery pipeline

- Choose supported Python and Django versions; prefer supported Django 5.2 LTS for the first modernization unless the dependency matrix and deployment environment are ready for Django 6.0.
- Upgrade dependencies in controlled increments and resolve deprecation/security warnings before the next version step.
- Add locked dependencies, CI, formatting/linting, `manage.py check --deploy`, `makemigrations --check`, and tests against the production database engine.
- Add API schema/documentation, pagination limits, consistent exception handling, and backward-compatible API versioning before changing public responses.

**Exit criteria:** clean CI on the supported runtime/database matrix and repeatable staged deployment/rollback.

### Phase 4 — operations and performance

- Add structured logs, health/readiness checks, metrics/error reporting, and alerting appropriate to the host.
- Document backups, restore drills, migration execution, secret rotation, and incident response.
- Measure query counts and latency with representative data; optimize querysets/serializers and add indexes based on evidence.
- Add caching only for measured read-heavy endpoints, with explicit invalidation rules.

**Exit criteria:** operators can detect failures, restore data, and verify performance against defined service targets.

## Recommended first implementation slice

1. Add a dependency manifest and setup documentation.
2. Externalize secrets/database configuration and disable debug toolbar outside development.
3. Model cart ownership and enforce it end-to-end.
4. Add focused API tests for cross-user access and checkout.
5. Implement stock-safe, transactional, idempotent checkout.

This ordering reduces immediate security and data-integrity risk while creating enough reproducibility to safely modernize dependencies afterward.

## Audit limits

This is a static repository review. No tests or runtime checks were executed. There is no dependency manifest, so exact installed versions and upgrade compatibility cannot be established from the repository alone. Deployment infrastructure and the intended status of the committed SQLite database were not available for review.
