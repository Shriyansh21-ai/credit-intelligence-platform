"""Enterprise telemetry layer (Phase 11, M7).

Turns the platform's existing in-process observability primitives
(``services.saas.observability``) into a production-grade, standards-based
telemetry surface **without duplicating** the metric registry or the
correlation/trace context that already exist:

* :func:`render_prometheus` — renders the live :class:`MetricsRegistry`
  snapshot into Prometheus text exposition format, served at ``GET /metrics``
  (the scrape target already declared in ``deploy/monitoring/prometheus``).
* :func:`configure_logging` — installs structured (JSON) logging that injects
  the current correlation/trace id into every record. Idempotent and safe to
  call from any process (API, worker, scheduler).
* :func:`init_tracing` — best-effort OpenTelemetry bootstrap. If the OTel SDK
  and an OTLP endpoint are configured it instruments FastAPI + SQLAlchemy and
  exports spans; otherwise it is a no-op. Never raises.
* :data:`domain` — thin, typed facades for the business / ML / database /
  queue / API / WebSocket metric families required by M7. Every helper writes
  into the shared registry, so all families appear on ``/metrics`` uniformly.

Everything here is additive and defensive: a telemetry failure must never
affect request handling or process startup.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from contextlib import contextmanager, suppress
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from backend.app.core.settings import AppSettings, get_settings
from backend.app.services.saas import observability as _obs

_NAMESPACE = "aicredit"
_METRIC_NAME_RE = re.compile(r"[^a-zA-Z0-9_:]")


# ===========================================================================
# Prometheus exposition
# ===========================================================================
def _split_key(key: str) -> tuple[str, dict[str, str]]:
    """Parse the registry key ``base{k=v,k2=v2}`` into (base, labels)."""
    if "{" not in key:
        return key, {}
    base, _, rest = key.partition("{")
    rest = rest.rstrip("}")
    labels: dict[str, str] = {}
    if rest:
        for pair in rest.split(","):
            if "=" in pair:
                k, _, v = pair.partition("=")
                labels[k.strip()] = v.strip()
    return base, labels


def _sanitize(name: str) -> str:
    clean = _METRIC_NAME_RE.sub("_", name)
    if clean and clean[0].isdigit():
        clean = "_" + clean
    return f"{_NAMESPACE}_{clean}"


def _fmt_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = []
    for k, v in sorted(labels.items()):
        kk = _METRIC_NAME_RE.sub("_", k)
        vv = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        parts.append(f'{kk}="{vv}"')
    return "{" + ",".join(parts) + "}"


def render_prometheus(snapshot: dict[str, Any] | None = None) -> str:
    """Render the metrics registry into Prometheus text exposition format."""
    snap = snapshot if snapshot is not None else _obs.metrics.snapshot()
    lines: list[str] = []
    emitted_types: set[str] = set()

    def _emit_type(metric: str, kind: str) -> None:
        if metric not in emitted_types:
            lines.append(f"# TYPE {metric} {kind}")
            emitted_types.add(metric)

    # Counters ---------------------------------------------------------------
    for key, value in sorted(snap.get("counters", {}).items()):
        base, labels = _split_key(key)
        metric = _sanitize(base)
        _emit_type(metric, "counter")
        lines.append(f"{metric}{_fmt_labels(labels)} {value}")

    # Gauges -----------------------------------------------------------------
    for key, value in sorted(snap.get("gauges", {}).items()):
        base, labels = _split_key(key)
        metric = _sanitize(base)
        _emit_type(metric, "gauge")
        lines.append(f"{metric}{_fmt_labels(labels)} {value}")

    # Histograms -> Prometheus summary (quantiles + _sum/_count) -------------
    for key, stats in sorted(snap.get("histograms", {}).items()):
        base, labels = _split_key(key)
        metric = _sanitize(base)
        _emit_type(metric, "summary")
        count = stats.get("count", 0)
        avg = stats.get("avg", 0.0)
        for q, field in (("0.5", "p50"), ("0.95", "p95"), ("0.99", "p99")):
            ql = dict(labels)
            ql["quantile"] = q
            lines.append(f"{metric}{_fmt_labels(ql)} {stats.get(field, 0.0)}")
        lines.append(f"{metric}_sum{_fmt_labels(labels)} {round(avg * count, 4)}")
        lines.append(f"{metric}_count{_fmt_labels(labels)} {count}")
        # Retain max as an auxiliary gauge (useful for latency SLOs).
        maxmetric = f"{metric}_max"
        _emit_type(maxmetric, "gauge")
        lines.append(f"{maxmetric}{_fmt_labels(labels)} {stats.get('max', 0.0)}")

    # Process/build info -----------------------------------------------------
    settings = get_settings()
    info_labels = _fmt_labels(
        {
            "version": settings.app_version,
            "env": settings.app_env,
            "service": settings.otel_service_name,
        }
    )
    _emit_type(f"{_NAMESPACE}_build_info", "gauge")
    lines.append(f"{_NAMESPACE}_build_info{info_labels} 1")

    return "\n".join(lines) + "\n"


# ===========================================================================
# /metrics router
# ===========================================================================
metrics_router = APIRouter(tags=["Observability"])


@metrics_router.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> PlainTextResponse:
    """Prometheus scrape endpoint (root-level, unauthenticated by convention).

    Returns an empty body when metrics collection is disabled so scrapers still
    receive a valid 200.
    """
    settings = get_settings()
    if not settings.metrics_enabled:
        return PlainTextResponse("", media_type="text/plain; version=0.0.4")
    try:
        body = render_prometheus()
    except Exception:  # pragma: no cover - defensive
        body = ""
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")


# ===========================================================================
# Structured logging
# ===========================================================================
class CorrelationFilter(logging.Filter):
    """Injects correlation/trace ids from the observability context."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _obs.current_correlation_id() or "-"
        record.trace_id = _obs.current_trace_id() or "-"
        return True


class JsonLogFormatter(logging.Formatter):
    """Compact single-line JSON log formatter."""

    _RESERVED = frozenset(vars(logging.makeLogRecord({})).keys()) | {
        "correlation_id",
        "trace_id",
        "message",
        "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "-"),
            "trace_id": getattr(record, "trace_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Merge any structured extras attached to the record.
        for k, v in record.__dict__.items():
            if k not in self._RESERVED and not k.startswith("_"):
                try:
                    json.dumps(v)
                    payload[k] = v
                except (TypeError, ValueError):
                    payload[k] = str(v)
        return json.dumps(payload, default=str)


_LOGGING_CONFIGURED = False


def configure_logging(settings: AppSettings | None = None, *, force: bool = False) -> None:
    """Install structured logging on the root logger. Idempotent."""
    global _LOGGING_CONFIGURED  # noqa: PLW0603 - process-wide init-once flag
    if _LOGGING_CONFIGURED and not force:
        return
    settings = settings or get_settings()
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(CorrelationFilter())
    if settings.log_format == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] [cid=%(correlation_id)s] %(message)s"
            )
        )

    # Replace only handlers we previously installed, so we don't fight pytest
    # or uvicorn's handlers; tag ours to make the swap idempotent.
    root.handlers = [h for h in root.handlers if not getattr(h, "_aicredit", False)]
    handler._aicredit = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    _LOGGING_CONFIGURED = True


# ===========================================================================
# OpenTelemetry (best-effort, config-gated)
# ===========================================================================
_TRACING_INITED = False


def init_tracing(app: Any = None, settings: AppSettings | None = None) -> bool:
    """Bootstrap OpenTelemetry tracing if enabled and the SDK is available.

    Returns True if tracing was activated, False otherwise. Never raises.
    """
    global _TRACING_INITED  # noqa: PLW0603 - process-wide init-once flag
    if _TRACING_INITED:
        return True
    settings = settings or get_settings()
    if not settings.tracing_enabled or not settings.otel_exporter_otlp_endpoint:
        return False
    try:  # pragma: no cover - exercised only when OTel is installed
        # Lazy imports: OpenTelemetry is an optional dependency; importing at
        # module load would make the whole app hard-depend on the OTel SDK.
        from opentelemetry import trace  # noqa: PLC0415
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource  # noqa: PLC0415
        from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: PLC0415

        resource = Resource.create(
            {
                "service.name": settings.otel_service_name,
                "service.version": settings.app_version,
                "deployment.environment": settings.app_env,
            }
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
        )
        trace.set_tracer_provider(provider)

        if app is not None:
            with suppress(Exception):
                from opentelemetry.instrumentation.fastapi import (  # noqa: PLC0415
                    FastAPIInstrumentor,
                )

                FastAPIInstrumentor.instrument_app(app)
        with suppress(Exception):
            from opentelemetry.instrumentation.sqlalchemy import (  # noqa: PLC0415
                SQLAlchemyInstrumentor,
            )

            SQLAlchemyInstrumentor().instrument()

        _TRACING_INITED = True
        logging.getLogger(__name__).info(
            "OpenTelemetry tracing enabled", extra={"otlp": settings.otel_exporter_otlp_endpoint}
        )
        return True
    except Exception:
        logging.getLogger(__name__).warning(
            "OpenTelemetry requested but SDK unavailable; tracing disabled"
        )
        return False


# ===========================================================================
# Domain metric facades — business / ML / DB / queue / API / WebSocket
# ===========================================================================
class _Domain:
    """Typed helpers that record the M7 metric families into the shared registry."""

    _m = _obs.metrics

    # -- business ---------------------------------------------------------
    def business_event(self, event: str, value: float = 1.0, **labels: Any) -> None:
        self._m.incr(f"business.{event}", value, **labels)

    def business_value(self, name: str, value: float, **labels: Any) -> None:
        self._m.gauge(f"business.{name}", value, **labels)

    # -- ML ---------------------------------------------------------------
    def ml_inference(self, model: str, duration_ms: float, *, outcome: str = "ok") -> None:
        self._m.incr("ml.predictions", model=model, outcome=outcome)
        self._m.observe("ml.inference_ms", duration_ms, model=model)

    def ml_score(self, model: str, score: float) -> None:
        self._m.observe("ml.score", score, model=model)

    def ml_drift(self, model: str, feature: str, drift: float) -> None:
        self._m.gauge("ml.drift", drift, model=model, feature=feature)

    # -- database ---------------------------------------------------------
    def db_query(self, duration_ms: float, *, operation: str = "query") -> None:
        self._m.observe("db.query_ms", duration_ms, operation=operation)

    def db_pool(self, in_use: int, size: int) -> None:
        self._m.gauge("db.pool.in_use", in_use)
        self._m.gauge("db.pool.size", size)

    # -- queue / jobs -----------------------------------------------------
    def queue_depth(self, queue: str, depth: int) -> None:
        self._m.gauge("queue.depth", depth, queue=queue)

    def job(self, status: str, duration_ms: float | None = None, *, queue: str = "default") -> None:
        self._m.incr("queue.jobs", status=status, queue=queue)
        if duration_ms is not None:
            self._m.observe("queue.job_ms", duration_ms, queue=queue)

    # -- API --------------------------------------------------------------
    def api_request(self, method: str, path: str, status: int, duration_ms: float) -> None:
        self._m.incr("http.requests", method=method, status=str(status))
        self._m.observe("http.latency_ms", duration_ms, path=path)

    # -- WebSocket / realtime --------------------------------------------
    def ws_connection(self, delta: int = 1) -> None:
        self._m.incr("ws.connections_total") if delta > 0 else None
        # Track a live gauge alongside the monotonic counter.
        current = _obs.metrics.snapshot()["gauges"].get("ws.active", 0)
        self._m.gauge("ws.active", max(0, current + delta))

    def ws_message(self, direction: str = "out") -> None:
        self._m.incr("ws.messages", direction=direction)


domain = _Domain()


# ===========================================================================
# Timing helper
# ===========================================================================
@contextmanager
def timed(metric: str, **labels: Any):
    """Context manager that observes wall-clock milliseconds into ``metric``."""
    start = time.perf_counter()
    try:
        yield
    finally:
        _obs.metrics.observe(metric, (time.perf_counter() - start) * 1000.0, **labels)


def instrument_app(app: Any, settings: AppSettings | None = None) -> None:
    """One-call wiring used by ``main.py``: logging + tracing + /metrics.

    Fully best-effort; a failure here must not stop the app from serving.
    """
    settings = settings or get_settings()
    with suppress(Exception):
        configure_logging(settings)
    with suppress(Exception):
        init_tracing(app, settings)


__all__ = [
    "configure_logging",
    "domain",
    "init_tracing",
    "instrument_app",
    "metrics_router",
    "render_prometheus",
    "timed",
]
