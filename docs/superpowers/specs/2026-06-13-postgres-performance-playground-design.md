# PostgreSQL Performance Playground — Design

**Date:** 2026-06-13
**Status:** Approved (design); Phase 1 to be planned next

## Goal

Learn database optimization hands-on by building a deliberately naive Django +
PostgreSQL 18 e-commerce app, load-testing it until it breaks, then optimizing it
one bottleneck at a time and re-measuring to prove each fix. The app is a vehicle
for generating realistic database load — the learning is the product.

## Hardware

| Machine | CPU | RAM | Role |
|---|---|---|---|
| Machine 1 | i5-12400f (6c/12t) | 32 GB | System Under Test (Postgres + Django) |
| Machine 2 | i5-9400H (4c/8t) | 32 GB | Load generator (Locust) — Phase 2+ |

Both run Arch Linux with Docker Compose. Core methodology lesson: **never run the
load generator on the same box as the system under test**, or you can't tell
whether the app is slow or just CPU-starved by the load tool.

## Stack

- **App:** Django (ORM-first, with raw SQL where it teaches more), served by Gunicorn
- **Database:** PostgreSQL 18
- **Load testing:** Locust
- **Orchestration:** Docker Compose

## Phases

### Phase 1 — Throttled deep-dive (single machine) — *this spec's implementation scope*
Everything on Machine 1. Postgres container capped to ~1 CPU / 512 MB so bottlenecks
appear fast without huge data. Moderate data (~1–5M rows). Goal: build the diagnostic
muscle — find a slow query, read its plan, fix it, re-measure.

### Phase 2 — Clean measurement (two machines) — *future spec*
Locust moves to Machine 2, hammering Machine 1 over LAN. Latency numbers now reflect
the DB/app rather than load-tool contention. Add live dashboards (Prometheus + Grafana
+ postgres_exporter + cAdvisor).

### Phase 3 — Realistic scale — *future spec*
Remove throttles, scale data to 50M+ rows, apply volume-driven optimizations
(partitioning, materialized views, config tuning).

## Topology (Docker Compose, Machine 1)

- `db` — Postgres 18, with a toggleable CPU/RAM-throttle override (`docker-compose.throttle.yml`)
- `web` — Django app (Gunicorn)
- `loadgen` — Locust (Phase 1 only; relocates to Machine 2 in Phase 2)

`pg_stat_statements` and `auto_explain` enabled in Postgres config from day one.

## Domain & data model (e-commerce)

Core tables: `customers`, `categories`, `products`, `product_reviews`,
`carts` / `cart_items`, `orders` / `order_items`, `inventory`.

Seeded by a generator (Faker + bulk inserts) with a configurable volume knob so we
can dial data up/down per phase. These tables produce the full spread of workloads:
joins, filtered search, aggregation, and write contention.

## The Django app — deliberately naive first

We write the obvious, unoptimized version first so bottlenecks are real, not
contrived. Endpoints and the lesson each is designed to expose:

| Endpoint | Workload | Bottleneck it exposes |
|---|---|---|
| Product listing | filter by category/price, sort, paginate | missing indexes, `OFFSET` pagination pain |
| Product detail | product + reviews + related products | classic N+1 |
| Search | text search over name/description | full-text / GIN indexing |
| Checkout | create order, decrement inventory under concurrency | locking & contention |
| Order history | per-customer orders with totals | joins + aggregation |
| Top-products dashboard | heavy `GROUP BY` | aggregation, materialized views |

## Load testing — defining "the limit"

Per endpoint, a Locust scenario ramps concurrent users until **p95 latency crosses a
threshold or error rate climbs** — that crossover *is* the limit. We record throughput
(RPS), latency percentiles, and error rate as a **baseline**, optimize, then re-run the
identical test to prove the improvement.

## Observability — seeing the bottleneck

**Phase 1 (lean):**
- `pg_stat_statements` — which queries cost the most aggregate time
- `EXPLAIN (ANALYZE, BUFFERS)` — why a given query is slow
- `django-debug-toolbar` — per-request SQL count (catches N+1 instantly)
- `auto_explain` + slow-query log (`log_min_duration_statement`)
- Locust's built-in charts

**Phase 2+ (live dashboards):** Prometheus + Grafana + `postgres_exporter` + `cAdvisor`
to watch cache-hit ratio, connections, and CPU collapse in real time under load.

## Optimization curriculum (the learning loop)

Each item is a "find it → understand it → fix it → re-measure" cycle, roughly in order:

1. N+1 → `select_related` / `prefetch_related`
2. Missing & composite indexes; covering (`INCLUDE`) indexes
3. Full-text search with GIN
4. Keyset (cursor) pagination vs `OFFSET`
5. Counting strategies (exact vs estimated)
6. Connection pooling (PgBouncer / Django persistent connections)
7. Caching (Redis) for hot reads
8. Locking under checkout contention (`SELECT FOR UPDATE`, optimistic vs pessimistic)
9. Bulk writes
10. Autovacuum / bloat
11. Partitioning large tables *(Phase 3)*
12. Materialized views for dashboards *(Phase 3)*
13. Postgres config tuning (`shared_buffers`, `work_mem`, `effective_cache_size`) *(Phase 3)*

## The lab notebook

`docs/findings/` holds one entry per experiment:
**hypothesis → baseline numbers → the fix → after numbers → what I learned.**
This is what turns "I ran some tests" into retained knowledge.

## Repo structure

```
performance_playground/
  docker-compose.yml
  docker-compose.throttle.yml   # CPU/RAM caps for the db service
  Makefile                      # make seed / make loadtest / make throttle / make up
  app/                          # Django project + ecommerce app
  seed/                         # data generator
  loadtest/                     # Locust scenarios
  docs/findings/                # the lab notebook
  docs/superpowers/specs/       # design docs
```

## Testing approach

Each optimization is verified by **re-running its load test** and comparing against the
recorded baseline — the load test *is* the proof. Standard Django unit tests cover
correctness of the endpoints (so an "optimization" can't silently break behavior).

## Phase 1 implementation scope (for the next plan)

1. Docker Compose stack: Postgres 18 (with `pg_stat_statements`/`auto_explain`) + Django + Locust
2. Throttle override for the `db` service
3. E-commerce data model + seed generator (configurable volume)
4. Naive implementations of all six endpoints
5. Lean observability wired up (debug toolbar, slow-query logging, stat statements)
6. Locust scenarios + a baseline-recording workflow
7. The lab-notebook structure
8. First 2–3 optimization cycles (N+1, indexing, keyset pagination) fully documented

Phases 2 and 3 get their own specs later.

## Out of scope (YAGNI)

- Real authentication/payments (stub or skip)
- Frontend UI (endpoints return JSON; load tests hit them directly)
- Production deployment / TLS / multi-tenancy
- Phase 2/3 work (separate specs)
