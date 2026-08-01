"""Performance engineering toolkit.

Additive, opt-in instrumentation and analysis utilities. Nothing here is wired
into the hot path unless explicitly enabled, so it never regresses baseline
latency

* :class:`QueryProfiler` — attaches SQLAlchemy cursor-execute hooks that time
  every statement, feed the observability registry, and detect N+1 access
  patterns within a request/unit of work.
* :func:`analyze_slow_queries` — aggregates the observability slow-query buffer
  into a ranked report.
* :func:`recommend_indexes` — heuristic index recommendations parsed from the
  predicates of slow queries.
* :func:`benchmark` — a small, dependency-free micro-benchmark harness.

Pairs with the existing primitives: `core/cache.py` (caching), `app/workers/*`
(background execution), `services/saas/observability.py` (slow-query buffer)
and the connection-pool knobs in `core/settings.py`.
"""

from __future__ import annotations

import re
import statistics
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from backend.app.services.saas import observability as _obs

# Per-unit-of-work query tally for N+1 detection.
_query_tally: ContextVar[dict[str, int] | None] = ContextVar("perf_query_tally", default=None)

_N_PLUS_ONE_THRESHOLD = 10


def _normalize_sql(sql: str) -> str:
    """Collapse literals/whitespace so structurally-identical queries group."""
    s = re.sub(r"\s+", " ", sql.strip())
    s = re.sub(r"%\([^)]+\)s|\?|:\w+", "?", s)  # bound params
    s = re.sub(r"\b\d+\b", "?", s)  # numeric literals
    s = re.sub(r"'[^']*'", "?", s)  # string literals
    s = re.sub(r"\bIN\s*\([^)]*\)", "IN (?)", s, flags=re.IGNORECASE)
    return s.lower()


# ===========================================================================
# Query profiler + N+1 detection
# ===========================================================================
class QueryProfiler:
    """SQLAlchemy execute-hook profiler. Call :meth:`attach` once per engine."""

    def __init__(self) -> None:
        self._attached = False

    def attach(self, engine: Any) -> bool:
        if self._attached:
            return False
        try:
            from sqlalchemy import event  # noqa: PLC0415
        except Exception:  # pragma: no cover
            return False

        @event.listens_for(engine, "before_cursor_execute")
        def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
            context._perf_start = time.perf_counter()

        @event.listens_for(engine, "after_cursor_execute")
        def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
            start = getattr(context, "_perf_start", None)
            if start is None:
                return
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            _obs.record_query(statement, elapsed_ms)
            tally = _query_tally.get()
            if tally is not None:
                tally[_normalize_sql(statement)] += 1

        self._attached = True
        return True


profiler = QueryProfiler()


@dataclass
class UnitOfWorkStats:
    total_queries: int
    distinct_statements: int
    n_plus_one: list[tuple[str, int]] = field(default_factory=list)


@contextmanager
def profiling_scope():
    """Track per-unit-of-work query counts; yields a callable returning stats.

    Usage

        with profiling_scope() as stats
            ... do work ...
        report = stats() # UnitOfWorkStats
    """
    tally: dict[str, int] = defaultdict(int)
    token = _query_tally.set(tally)
    try:
        # Close over the dict itself so stats() is valid during *and* after the
        # scope (the contextvar is reset on exit, but the dict lives on).
        yield lambda: _summarize(tally)
    finally:
        _query_tally.reset(token)


def _summarize(tally: dict[str, int]) -> UnitOfWorkStats:
    n_plus_one = sorted(
        ((sql, n) for sql, n in tally.items() if n >= _N_PLUS_ONE_THRESHOLD),
        key=lambda kv: kv[1],
        reverse=True,
    )
    return UnitOfWorkStats(
        total_queries=sum(tally.values()),
        distinct_statements=len(tally),
        n_plus_one=n_plus_one,
    )


# ===========================================================================
# Slow-query analysis
# ===========================================================================
@dataclass
class SlowQueryReport:
    count: int
    slowest_ms: float
    by_pattern: list[dict[str, Any]]


def analyze_slow_queries(limit: int = 100) -> SlowQueryReport:
    """Aggregate the observability slow-query buffer by normalized pattern."""
    rows = _obs.slow_queries(limit=limit)
    if not rows:
        return SlowQueryReport(count=0, slowest_ms=0.0, by_pattern=[])
    grouped: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        grouped[_normalize_sql(r["statement"])].append(float(r["duration_ms"]))
    by_pattern = [
        {
            "pattern": pat,
            "occurrences": len(durs),
            "avg_ms": round(sum(durs) / len(durs), 2),
            "max_ms": round(max(durs), 2),
        }
        for pat, durs in grouped.items()
    ]
    by_pattern.sort(key=lambda d: d["max_ms"], reverse=True)
    return SlowQueryReport(
        count=len(rows),
        slowest_ms=round(max(r["duration_ms"] for r in rows), 2),
        by_pattern=by_pattern,
    )


# ===========================================================================
# Index recommendations
# ===========================================================================
_WHERE_COL = re.compile(
    r"\bwhere\b(.*?)(?:\bgroup\b|\border\b|\blimit\b|$)", re.IGNORECASE | re.DOTALL
)
_JOIN_COL = re.compile(r"\bjoin\b\s+(\w+)\s+.*?\bon\b\s+([\w.]+)\s*=\s*([\w.]+)", re.IGNORECASE)
_PRED_COL = re.compile(r"([a-zA-Z_][\w.]*)\s*(?:<=|>=|!=|=|<|>|\blike\b|\bin\b)", re.IGNORECASE)
_FROM_TBL = re.compile(r"\bfrom\s+([a-zA-Z_]\w*)", re.IGNORECASE)


def recommend_indexes(
    patterns: list[dict[str, Any]] | None = None, *, min_occurrences: int = 2
) -> list[dict[str, str]]:
    """Suggest indexes from slow-query predicates (heuristic, advisory only)."""
    patterns = patterns if patterns is not None else analyze_slow_queries().by_pattern
    recs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for p in patterns:
        if p.get("occurrences", 0) < min_occurrences:
            continue
        sql = p["pattern"]
        table_m = _FROM_TBL.search(sql)
        table = table_m.group(1) if table_m else "?"
        where_m = _WHERE_COL.search(sql)
        cols: list[str] = []
        if where_m:
            cols = [c.split(".")[-1] for c in _PRED_COL.findall(where_m.group(1))]
        for jm in _JOIN_COL.finditer(sql):
            cols.append(jm.group(2).split(".")[-1])
            cols.append(jm.group(3).split(".")[-1])
        # De-dup while preserving order.
        ordered = list(dict.fromkeys(c for c in cols if c and c != "?"))
        if not ordered:
            continue
        key = (table, ",".join(ordered))
        if key in seen:
            continue
        seen.add(key)
        cols_csv = ", ".join(ordered)
        ix_name = f"ix_{table}_{'_'.join(ordered)}"
        recs.append(
            {
                "table": table,
                "columns": cols_csv,
                "ddl": f"CREATE INDEX {ix_name} ON {table} ({cols_csv});",
                "rationale": f"appears in {p['occurrences']} slow queries (max {p['max_ms']}ms)",
            }
        )
    return recs


# ===========================================================================
# Micro-benchmark harness
# ===========================================================================
@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    min_ms: float
    max_ms: float
    mean_ms: float
    p50_ms: float
    p95_ms: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "min_ms": round(self.min_ms, 4),
            "max_ms": round(self.max_ms, 4),
            "mean_ms": round(self.mean_ms, 4),
            "p50_ms": round(self.p50_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
        }


def benchmark(
    func: Callable[[], Any], *, iterations: int = 100, warmup: int = 5, name: str | None = None
) -> BenchmarkResult:
    """Time ``func`` over ``iterations`` runs after ``warmup`` warm-up runs."""
    for _ in range(max(0, warmup)):
        func()
    samples: list[float] = []
    for _ in range(max(1, iterations)):
        start = time.perf_counter()
        func()
        samples.append((time.perf_counter() - start) * 1000.0)
    samples.sort()
    return BenchmarkResult(
        name=name or getattr(func, "__name__", "benchmark"),
        iterations=len(samples),
        min_ms=samples[0],
        max_ms=samples[-1],
        mean_ms=statistics.fmean(samples),
        p50_ms=_percentile(samples, 50),
        p95_ms=_percentile(samples, 95),
    )


def _percentile(sorted_samples: list[float], pct: int) -> float:
    if not sorted_samples:
        return 0.0
    idx = min(len(sorted_samples) - 1, round((pct / 100.0) * (len(sorted_samples) - 1)))
    return sorted_samples[idx]


def top_statement_patterns(limit: int = 10) -> list[tuple[str, int]]:
    """Most-frequent normalized statements seen this unit of work (if profiling)."""
    tally = _query_tally.get() or {}
    return Counter(tally).most_common(limit)


__all__ = [
    "BenchmarkResult",
    "QueryProfiler",
    "SlowQueryReport",
    "UnitOfWorkStats",
    "analyze_slow_queries",
    "benchmark",
    "profiler",
    "profiling_scope",
    "recommend_indexes",
    "top_statement_patterns",
]
