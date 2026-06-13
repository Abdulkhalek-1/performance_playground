# Finding: <short title>

**Date:** YYYY-MM-DD
**Endpoint(s):** <e.g. GET /api/products/>
**Throttle:** <on (1cpu/512mb) | off>  **Seed volume:** <products/customers/...>

## Hypothesis
<What I think is slow and why.>

## Baseline (before)
- Ramp: step shape (25 -> 400 users over 5m)
- Limit reached at: <N concurrent users>
- p50 / p95 / p99 latency: <ms / ms / ms>
- Throughput at limit: <RPS>
- Error rate: <%>
- Query evidence: <silk per-request query count, EXPLAIN ANALYZE excerpt, pg_stat_statements row>
- CSV: docs/findings/baselines/<file>_stats.csv

## The fix
<What I changed and the reasoning. Link the commit.>

## After
- p50 / p95 / p99 latency: <ms / ms / ms>
- Throughput: <RPS>  Error rate: <%>
- Query evidence: <new query count / plan>

## Lesson learned
<The transferable takeaway.>
