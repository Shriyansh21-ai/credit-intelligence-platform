"""In-process connector observability (Milestone 13).

A thread-safe metrics registry that every connector call feeds. It tracks, per
``(category, provider)``: call counts, success/failure, retries, cache hits,
circuit-open rejections and a latency summary. This is the live source for the
observability dashboard; durable per-call rows are persisted separately as
``ConnectorCallLog`` (see :mod:`..logging`).

Kept dependency-free and in-memory (one registry per process) — the same shape
as :mod:`backend.app.core.cache`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ProviderMetrics:
    category: str
    provider: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    retries: int = 0
    cache_hits: int = 0
    circuit_rejections: int = 0
    total_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    _latencies: List[float] = field(default_factory=list)

    def record(
        self,
        *,
        success: bool,
        latency_ms: float,
        attempts: int = 1,
        cache_hit: bool = False,
        circuit_rejected: bool = False,
    ) -> None:
        self.calls += 1
        if success:
            self.successes += 1
        else:
            self.failures += 1
        self.retries += max(0, attempts - 1)
        if cache_hit:
            self.cache_hits += 1
        if circuit_rejected:
            self.circuit_rejections += 1
        self.total_latency_ms += latency_ms
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        # Keep a bounded window for percentile estimates.
        self._latencies.append(latency_ms)
        if len(self._latencies) > 512:
            self._latencies = self._latencies[-512:]

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.calls if self.calls else 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.calls if self.calls else 0.0

    @property
    def failure_rate(self) -> float:
        return self.failures / self.calls if self.calls else 0.0

    def percentile(self, p: float) -> float:
        if not self._latencies:
            return 0.0
        ordered = sorted(self._latencies)
        idx = min(len(ordered) - 1, max(0, int(round((p / 100.0) * (len(ordered) - 1)))))
        return ordered[idx]

    def to_dict(self) -> Dict[str, object]:
        return {
            "category": self.category,
            "provider": self.provider,
            "calls": self.calls,
            "successes": self.successes,
            "failures": self.failures,
            "retries": self.retries,
            "cache_hits": self.cache_hits,
            "circuit_rejections": self.circuit_rejections,
            "success_rate": round(self.success_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "max_latency_ms": round(self.max_latency_ms, 3),
            "p50_latency_ms": round(self.percentile(50), 3),
            "p95_latency_ms": round(self.percentile(95), 3),
        }


class MetricsCollector:
    """Thread-safe registry of :class:`ProviderMetrics`, keyed by provider."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_provider: Dict[str, ProviderMetrics] = {}

    def record(
        self,
        category: str,
        provider: str,
        *,
        success: bool,
        latency_ms: float,
        attempts: int = 1,
        cache_hit: bool = False,
        circuit_rejected: bool = False,
    ) -> None:
        with self._lock:
            key = f"{category}:{provider}"
            pm = self._by_provider.get(key)
            if pm is None:
                pm = ProviderMetrics(category=category, provider=provider)
                self._by_provider[key] = pm
            pm.record(
                success=success,
                latency_ms=latency_ms,
                attempts=attempts,
                cache_hit=cache_hit,
                circuit_rejected=circuit_rejected,
            )

    def snapshot(self) -> List[Dict[str, object]]:
        with self._lock:
            return [pm.to_dict() for pm in sorted(self._by_provider.values(), key=lambda m: (m.category, m.provider))]

    def for_provider(self, category: str, provider: str) -> Dict[str, object]:
        with self._lock:
            pm = self._by_provider.get(f"{category}:{provider}")
            return pm.to_dict() if pm else {}

    def totals(self) -> Dict[str, object]:
        with self._lock:
            calls = sum(m.calls for m in self._by_provider.values())
            successes = sum(m.successes for m in self._by_provider.values())
            failures = sum(m.failures for m in self._by_provider.values())
            retries = sum(m.retries for m in self._by_provider.values())
            cache_hits = sum(m.cache_hits for m in self._by_provider.values())
        return {
            "providers": len(self._by_provider),
            "calls": calls,
            "successes": successes,
            "failures": failures,
            "retries": retries,
            "cache_hits": cache_hits,
            "success_rate": round(successes / calls, 4) if calls else 0.0,
        }

    def reset(self) -> None:
        with self._lock:
            self._by_provider.clear()


# Process-wide default collector (like the cache singleton).
metrics = MetricsCollector()
