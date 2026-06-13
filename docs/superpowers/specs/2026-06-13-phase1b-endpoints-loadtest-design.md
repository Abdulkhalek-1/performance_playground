# Phase 1B — Endpoints + Load-Testing Harness — Design

**Date:** 2026-06-13
**Status:** Approved (design); plan to be written next
**Builds on:** Phase 1A foundation (Dockerized Postgres 18 + Django + e-commerce schema + seed). See
`docs/superpowers/specs/2026-06-13-postgres-performance-playground-design.md`.

## Goal

Add six deliberately naive DRF endpoints to the e-commerce app, plus a Locust load-testing
harness, per-request SQL profiling (django-silk), a DB-throttle override, and a lab-notebook
structure — so we can drive realistic load, find the limits, and record baselines. Phase 1B
records baselines only; the optimizations happen in Phase 1C.

## Key decisions (from brainstorming)

- **Backend: built from scratch with Django REST Framework.** Hand-written views + serializers
  give full control over the naive query patterns, so each bottleneck is authored and understood
  (not hidden behind auto-CRUD or a pre-built platform).
- **Endpoints are deliberately naive.** Nested serializers without `select_related`/
  `prefetch_related` (N+1), `LimitOffsetPagination` (deep-OFFSET cost), `icontains`/`ILIKE`
  search (sequential scan), lock-free checkout (write contention). Phase 1C fixes these.
- **Observability: django-silk**, gated behind `DJANGO_SILK=1` (off by default) because it
  instruments every request and would pollute baseline numbers. `pg_stat_statements` +
  `auto_explain` + slow-query log (from 1A) cover the DB-aggregate side. No django-debug-toolbar
  (silk supersedes it for this workflow).
- **No auth.** Checkout takes `customer_id` in the request body. Auth is out of scope.

## The six endpoints

All under `/api/`, implemented in a focused `ecommerce/api/` package
(`serializers.py`, `views.py`, `urls.py`) so each file has one responsibility.

| Endpoint | Method & route | Behaviour | Naive bottleneck exposed |
|---|---|---|---|
| Product listing | `GET /api/products/` | filter by `category`, `min_price`, `max_price`; `ordering`; `LimitOffsetPagination` | unindexed filter/sort columns; deep-`OFFSET` cost |
| Product detail | `GET /api/products/{id}/` | product + its reviews (nested) + related products (same category) | N+1 from nested review serializer (no prefetch) |
| Search | `GET /api/products/search/?q=` | `name__icontains` OR `description__icontains` | sequential scan; no full-text index |
| Checkout | `POST /api/checkout/` | body `{customer_id, items:[{product_id, quantity}]}`; create Order, create OrderItems, decrement Inventory, compute total — **no row locking** | write contention / lost inventory updates under concurrency |
| Order history | `GET /api/customers/{id}/orders/` | customer's orders, each with items + computed totals (nested) | N+1 + per-order aggregation |
| Top-products dashboard | `GET /api/dashboard/top-products/` | top N products by total quantity sold (`GROUP BY` + `SUM` over order items) | heavy aggregation scan |

### Endpoint contracts (response shapes)

- **Listing:** `{count, next, previous, results: [{id, name, price, category: {id, name}}]}` (DRF
  LimitOffsetPagination envelope). `category` nested to make the join/N+1 visible.
- **Detail:** `{id, name, description, price, category: {id, name}, reviews: [{id, rating, body,
  customer_id, created_at}], related_products: [{id, name, price}]}`. `related_products` = up to
  5 other products in the same category.
- **Search:** same envelope/shape as listing; `q` is required (400 if missing).
- **Checkout:** `201` with `{order_id, total, items: [{product_id, quantity, unit_price}]}`.
  `400` if `customer_id`/`items` missing or a product doesn't exist; inventory is decremented
  without locking (intentional). Total = sum(unit_price × quantity), unit_price snapshotted from
  the product's current price.
- **Order history:** `{customer_id, orders: [{id, status, total, created_at, items: [{product_id,
  quantity, unit_price}]}]}`.
- **Dashboard:** `{top_products: [{product_id, name, total_quantity}]}`, default top 10.

## Observability

- **django-silk** added to `INSTALLED_APPS` + middleware, mounted at `/silk/`, **only when
  `DJANGO_SILK=1`**. Used at low concurrency to inspect per-request SQL (counts, timing, the
  actual statements). Disabled for baseline load runs.
- `pg_stat_statements`, `auto_explain`, `log_min_duration_statement` — already enabled in 1A;
  no change.

## Throttle override

`docker-compose.throttle.yml` caps the `db` service to **~1 CPU / 512MB** (via `cpus` + `mem_limit`,
or `deploy.resources.limits`). Throttled run:
`docker compose -f docker-compose.yml -f docker-compose.throttle.yml up -d`. Baselines and early
optimization cycles run throttled so bottlenecks appear at low data/load.

## Load testing (Locust)

- A `loadgen` Locust service in Compose (web UI on `:8089`), targeting `web:8000`. Phase 1 keeps it
  on Machine 1; Phase 2 relocates it to Machine 2.
- `loadtest/` holds one `HttpUser`/`TaskSet` per scenario (listing, detail, search, checkout,
  order-history, dashboard) plus a combined "browse" mix. A scenario is selectable so each endpoint
  can be ramped in isolation.
- **Defining "the limit":** a headless ramp of rising concurrent users until **p95 latency exceeds a
  per-endpoint threshold OR error rate exceeds 1%**. That crossover is the recorded limit.
- A `make baseline` target runs the headless ramp and writes Locust CSV stats into
  `docs/findings/baselines/`.

## Lab notebook

- `docs/findings/TEMPLATE.md` — one experiment per entry: **hypothesis → baseline numbers → the fix
  → after numbers → lesson learned.**
- `docs/findings/baselines/` — raw Locust CSV output per endpoint.
- Phase 1B produces the baseline entries (naive numbers). Phase 1C fills in fixes + after-numbers.

## Testing

- DRF `APITestCase` correctness tests per endpoint: correct status, response shape, and data
  (e.g. checkout actually decrements inventory and snapshots price; listing filters/paginates;
  search matches; dashboard ranks correctly). These guard correctness so a later optimization
  cannot silently change behaviour.
- Load tests are the *performance* proof; unit tests are the *correctness* guard.

## File structure (new/changed)

```
performance_playground/
  app/
    requirements.txt              # + djangorestframework, django-silk, locust(optional in app)
    config/
      settings.py                 # + rest_framework, conditional silk, DRF pagination config
      urls.py                     # include ecommerce.api.urls under /api/, conditional /silk/
    ecommerce/
      api/
        __init__.py
        serializers.py            # naive nested serializers
        views.py                  # 6 endpoints
        urls.py                   # /api/ routes
      tests/
        test_api_listing.py
        test_api_detail.py
        test_api_search.py
        test_api_checkout.py
        test_api_orders.py
        test_api_dashboard.py
  docker-compose.throttle.yml     # db CPU/RAM caps
  docker-compose.yml              # + loadgen (Locust) service
  loadtest/
    locustfile.py                 # scenarios + combined mix
  docs/findings/
    TEMPLATE.md
    baselines/.gitkeep
  Makefile                        # + baseline target, + throttle helper
```

## Scope boundary (YAGNI)

- **In scope:** the six naive endpoints, DRF wiring, silk (gated), throttle override, Locust
  harness, baseline recording, lab-notebook scaffolding, correctness tests.
- **Out of scope (Phase 1C):** all optimizations — N+1 fixes, indexes, keyset pagination, checkout
  locking, caching. Checkout ships intentionally lock-free.
- **Out of scope (Phase 2+):** Locust on Machine 2, Prometheus/Grafana dashboards, realistic scale.
