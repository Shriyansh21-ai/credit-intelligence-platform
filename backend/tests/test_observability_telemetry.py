""" observability / telemetry tests.

Covers the Prometheus exposition renderer, the /metrics endpoint (including the
METRICS_ENABLED toggle), the domain metric facades, structured logging, the
correlation filter, and the config-gated tracing bootstrap.
"""

import logging
import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core import telemetry
from backend.app.core.settings import reload_settings
from backend.app.services.saas import observability as obs


class PrometheusRenderTest(unittest.TestCase):
    def setUp(self):
        obs.metrics.reset()

    def test_counter_gauge_summary_rendering(self):
        obs.metrics.incr("http.requests", method="GET")
        obs.metrics.gauge("queue.depth", 5, queue="default")
        obs.metrics.observe("http.latency_ms", 10.0, path="/a")
        obs.metrics.observe("http.latency_ms", 20.0, path="/a")
        out = telemetry.render_prometheus()

        self.assertIn("# TYPE aicredit_http_requests counter", out)
        self.assertIn('aicredit_http_requests{method="GET"} 1.0', out)
        self.assertIn("# TYPE aicredit_queue_depth gauge", out)
        self.assertIn("# TYPE aicredit_http_latency_ms summary", out)
        self.assertIn('quantile="0.5"', out)
        self.assertIn("aicredit_http_latency_ms_count", out)
        self.assertIn("aicredit_http_latency_ms_max", out)
        self.assertIn("aicredit_build_info", out)

    def test_metric_name_sanitized_and_labels_escaped(self):
        obs.metrics.incr("weird.metric-name", note='a"b\\c')
        out = telemetry.render_prometheus()
        # dots and dashes become underscores; quotes/backslashes escaped.
        self.assertIn("aicredit_weird_metric_name", out)
        self.assertIn(r'note="a\"b\\c"', out)

    def test_split_key(self):
        base, labels = telemetry._split_key("x.y{a=1,b=two}")
        self.assertEqual(base, "x.y")
        self.assertEqual(labels, {"a": "1", "b": "two"})
        base2, labels2 = telemetry._split_key("plain")
        self.assertEqual((base2, labels2), ("plain", {}))


class MetricsEndpointTest(unittest.TestCase):
    def setUp(self):
        obs.metrics.reset()
        self.app = FastAPI()
        self.app.include_router(telemetry.metrics_router)
        self.client = TestClient(self.app)

    def tearDown(self):
        os.environ.pop("METRICS_ENABLED", None)
        reload_settings()

    def test_metrics_endpoint_serves_exposition(self):
        obs.metrics.incr("http.requests", method="GET")
        r = self.client.get("/metrics")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/plain", r.headers["content-type"])
        self.assertIn("aicredit_http_requests", r.text)

    def test_metrics_disabled_returns_empty_200(self):
        os.environ["METRICS_ENABLED"] = "false"
        reload_settings()
        r = self.client.get("/metrics")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "")


class DomainFacadeTest(unittest.TestCase):
    def setUp(self):
        obs.metrics.reset()

    def test_all_families_record(self):
        telemetry.domain.business_event("loan_approved", tenant="acme")
        telemetry.domain.business_value("exposure_usd", 1000.0)
        telemetry.domain.ml_inference("scorecard", 5.0, outcome="ok")
        telemetry.domain.ml_drift("scorecard", "income", 0.2)
        telemetry.domain.db_query(3.0, operation="select")
        telemetry.domain.db_pool(2, 10)
        telemetry.domain.queue_depth("default", 4)
        telemetry.domain.job("completed", 12.0, queue="default")
        telemetry.domain.api_request("GET", "/x", 200, 7.0)
        telemetry.domain.ws_connection(1)
        telemetry.domain.ws_message("out")

        snap = obs.metrics.snapshot()
        counters, gauges, hist = snap["counters"], snap["gauges"], snap["histograms"]
        self.assertIn("business.loan_approved{tenant=acme}", counters)
        self.assertIn("business.exposure_usd", gauges)
        self.assertIn("ml.predictions{model=scorecard,outcome=ok}", counters)
        self.assertIn("db.pool.in_use", gauges)
        self.assertIn("queue.depth{queue=default}", gauges)
        self.assertIn("ws.active", gauges)
        self.assertTrue(any(k.startswith("ml.inference_ms") for k in hist))

    def test_ws_connection_gauge_never_negative(self):
        telemetry.domain.ws_connection(1)
        telemetry.domain.ws_connection(-1)
        telemetry.domain.ws_connection(-1)
        self.assertEqual(obs.metrics.snapshot()["gauges"]["ws.active"], 0)

    def test_timed_context_manager_observes(self):
        with telemetry.timed("op.ms", tag="x"):
            pass
        hist = obs.metrics.snapshot()["histograms"]
        self.assertTrue(any(k.startswith("op.ms") for k in hist))


class LoggingTest(unittest.TestCase):
    def test_json_formatter_includes_correlation(self):
        obs.start_context("cid-123")
        rec = logging.makeLogRecord({"msg": "hello", "name": "t"})
        telemetry.CorrelationFilter().filter(rec)
        line = telemetry.JsonLogFormatter().format(rec)
        self.assertIn('"correlation_id": "cid-123"', line)
        self.assertIn('"message": "hello"', line)

    def test_configure_logging_idempotent(self):
        telemetry.configure_logging(force=True)
        n1 = len([h for h in logging.getLogger().handlers if getattr(h, "_aicredit", False)])
        telemetry.configure_logging()
        n2 = len([h for h in logging.getLogger().handlers if getattr(h, "_aicredit", False)])
        self.assertEqual(n1, 1)
        self.assertEqual(n2, 1)


class TracingTest(unittest.TestCase):
    def tearDown(self):
        for k in ("TRACING_ENABLED", "OTEL_EXPORTER_OTLP_ENDPOINT"):
            os.environ.pop(k, None)
        reload_settings()

    def test_tracing_disabled_is_noop(self):
        telemetry._TRACING_INITED = False
        os.environ["TRACING_ENABLED"] = "false"
        reload_settings()
        self.assertFalse(telemetry.init_tracing(None))


if __name__ == "__main__":
    unittest.main()
