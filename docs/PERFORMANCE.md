# Performance Engineering

_Phase 11, M9 — performance toolkit for the AI Credit Intelligence Platform._

Additive and mostly **opt-in**: analysis/instrumentation utilities stay off the
hot path unless explicitly enabled, so baseline latency is never regressed.

---

## 1. Modules & existing primitives

| Concern | Where |
|---------|-------|
| Query profiling + N+1 detection | `core/performance.py` — `QueryProfiler`, `profiling_scope` |
| Slow-query analysis | `core/performance.py` — `analyze_slow_queries` |
| Index recommendations | `core/performance.py` — `recommend_indexes` |
| Micro-benchmarks | `core/performance.py` — `benchmark` |
| Pagination (offset + keyset) | `core/pagination.py` — `paginate`, `keyset_paginate` |
| Streaming APIs | `core/pagination.py` — `stream_ndjson` |
| Response compression | `GZipMiddleware` (wired in `main.py`, `COMPRESSION_*`) |
| Caching | `core/cache.py` — `TTLCache` (existing) |
| Background workers / async | `app/workers/*` (existing) |
| Connection pooling | `core/settings.py` — `DB_POOL_*` → `sqlalchemy_engine_kwargs` |
| Queue metrics | `core/telemetry.py` — `domain.queue_depth`/`job` (M7) |

## 2. Query profiling & N+1 prevention

`QueryProfiler.attach(engine)` installs SQLAlchemy `before/after_cursor_execute`
hooks that time every statement and feed the observability registry. Enable in
production with `QUERY_PROFILING_ENABLED=1` (wired at startup in `main.py`).

Wrap a unit of work to catch N+1 patterns:

```python
from backend.app.core.performance import profiling_scope

with profiling_scope() as stats:
    orders = session.query(Order).all()
    for o in orders:          # <-- naive per-row access triggers N+1
        _ = o.customer.name
report = stats()
# report.n_plus_one -> [("select * from customers where id = ?", 500), ...]
```

A normalized statement executed ≥10× in one scope is flagged. The fix is the
usual `joinedload`/`selectinload` eager loading — the profiler tells you where.

## 3. Slow-query analysis & index recommendations

Statements over 200 ms land in the observability slow-query buffer.

```python
from backend.app.core.performance import analyze_slow_queries, recommend_indexes

report = analyze_slow_queries()           # ranked by max latency, grouped by pattern
for rec in recommend_indexes():
    print(rec["ddl"])   # CREATE INDEX ix_applications_tenant_id_status ON ...
```

Recommendations are heuristic (parsed from `WHERE`/`JOIN` predicates) and
**advisory** — validate with `EXPLAIN` before applying.

## 4. Pagination

Prefer **keyset** pagination for deep/large lists (constant cost regardless of
depth); use **offset** for small, bounded lists that need a total count.

```python
from backend.app.core.pagination import paginate, keyset_paginate

page = paginate(query.order_by(Model.id), page=2, page_size=50)   # -> Page (with total)
page.as_dict()  # {"items": [...], "pagination": {"total", "page", "pages", "has_next", ...}}

ks = keyset_paginate(query, order_column=Model.id, page_size=50, after=last_id)
ks.next_cursor   # feed as `after` for the next page
```

Page size is clamped (`DEFAULT_PAGE_SIZE=50`, `MAX_PAGE_SIZE=500`) so a client
cannot request an unbounded window.

## 5. Streaming & compression

- `stream_ndjson(rows)` returns a `StreamingResponse` that serializes lazily —
  a million-row export never materialises in memory.
- `GZipMiddleware` compresses responses above `COMPRESSION_MIN_SIZE` (1 KiB
  default); toggle with `COMPRESSION_ENABLED`.

## 6. Connection pooling

Tuned via settings and applied in `db/database.py` for non-SQLite engines:
`DB_POOL_SIZE` (10), `DB_MAX_OVERFLOW` (20), `DB_POOL_TIMEOUT` (30s),
`DB_POOL_RECYCLE` (1800s), `DB_POOL_PRE_PING` (on — drops dead connections).

## 7. Benchmark harness

```python
from backend.app.core.performance import benchmark
res = benchmark(lambda: score_application(app), iterations=200, warmup=10)
res.as_dict()   # {"min_ms", "max_ms", "mean_ms", "p50_ms", "p95_ms", ...}
```

## 8. Guidance

- Cache expensive, read-mostly computations with `TTLCache`; invalidate on write.
- Offload slow/async work to `app/workers`; keep request handlers CPU-light.
- Page every list endpoint; never return unbounded result sets.
- Watch the M7 dashboards (`db_query_ms`, `http_latency_ms`, `queue_depth`) and
  the SLO burn-rate alerts to catch regressions early.
