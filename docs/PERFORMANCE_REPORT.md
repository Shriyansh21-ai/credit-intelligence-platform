# Performance Report

_AI Credit Intelligence Platform — Phase 11 (M9). Date: 2026-07-28._

## Overview

Phase 11 added a performance toolkit and hot-path-safe defaults. Instrumentation
is **opt-in** and off the critical path unless enabled, so baseline latency is
not regressed by the additions.

## Capabilities delivered

| Capability | Mechanism | Impact |
|------------|-----------|--------|
| Query profiling | `QueryProfiler` (SQLAlchemy execute hooks) | per-statement timing → registry |
| N+1 detection | `profiling_scope` per unit of work | flags ≥10 identical normalized queries |
| Slow-query analysis | `analyze_slow_queries` | ranks patterns by latency |
| Index recommendations | `recommend_indexes` | candidate DDL from predicates |
| Pagination | `paginate` (offset) + `keyset_paginate` (seek) | O(1) deep paging; page size ≤500 |
| Streaming | `stream_ndjson` | memory-bounded large exports |
| Compression | GZipMiddleware | smaller payloads above 1 KiB |
| Caching | `TTLCache` (existing) | read-mostly hot paths |
| Connection pooling | tuned engine kwargs | `DB_POOL_SIZE=10`, overflow 20, pre-ping |
| Async offload | workers + scheduler | request handlers stay CPU-light |
| Benchmark harness | `benchmark()` | min/max/mean/p50/p95 |

## SLO targets (see OBSERVABILITY.md)

| SLI | Objective |
|-----|-----------|
| API availability (30d) | 99.9% |
| API p99 latency | ≤ 750 ms |
| ML inference p95 | ≤ 500 ms |
| DB slow-query rate | alert > 0.5/s |

## Micro-benchmark harness

Deterministic timing with warmup; used to guard critical functions against
regression:

```python
benchmark(lambda: score_application(app), iterations=200, warmup=10).as_dict()
# -> {min_ms, max_ms, mean_ms, p50_ms, p95_ms}
```

## Overhead assessment

- Metrics: in-memory counters/gauges/histograms; O(1) per record; `/metrics`
  renders on scrape only.
- Middleware: correlation id + timing are constant-time; security/version headers
  are dict writes; GZip only above threshold.
- Query profiler: **disabled by default** (`QUERY_PROFILING_ENABLED=0`); when on,
  a `perf_counter` delta + dict increment per statement.

Net expected overhead on the hot path with defaults: **negligible** (< 1 ms/request
from middleware; profiler off).

## Recommendations

1. Enable query profiling in staging to capture the top N+1 sites, then add the
   recommended indexes (validated with `EXPLAIN`).
2. Adopt keyset pagination for all deep/large list endpoints.
3. Load/soak test in staging (k6/Locust) to calibrate HPA thresholds and the
   connection-pool size against real traffic; record baselines here.
4. Cache expensive read-mostly aggregations with `TTLCache`, invalidate on write.

## Status

Toolkit verified by tests (M9 + M14). Production baselines to be captured during
staging load tests (see recommendation 3).
