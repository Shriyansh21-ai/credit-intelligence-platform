""" expanded telemetry, logging & tracing tests."""

import logging
import os
import unittest

from backend.app.core import telemetry
from backend.app.core.settings import reload_settings
from backend.app.services.saas import observability as obs


class ExpositionShapeTest(unittest.TestCase):
    def setUp(self):
        obs.metrics.reset()

    def test_counter_type_emitted_once(self):
        obs.metrics.incr("x", method="GET")
        obs.metrics.incr("x", method="POST")
        out = telemetry.render_prometheus()
        self.assertEqual(out.count("# TYPE aicredit_x counter"), 1)

    def test_summary_has_sum_and_count(self):
        for v in (1.0, 2.0, 3.0):
            obs.metrics.observe("lat", v)
        out = telemetry.render_prometheus()
        self.assertIn("aicredit_lat_sum", out)
        self.assertIn("aicredit_lat_count", out)
        self.assertIn("aicredit_lat_max", out)

    def test_all_three_quantiles(self):
        for v in range(100):
            obs.metrics.observe("lat", float(v))
        out = telemetry.render_prometheus()
        for q in ("0.5", "0.95", "0.99"):
            self.assertIn(f'quantile="{q}"', out)

    def test_label_ordering_deterministic(self):
        obs.metrics.incr("x", b="2", a="1")
        out = telemetry.render_prometheus()
        self.assertIn('aicredit_x{a="1",b="2"}', out)

    def test_snapshot_passthrough(self):
        snap = {"counters": {"c": 5}, "gauges": {}, "histograms": {}}
        out = telemetry.render_prometheus(snap)
        self.assertIn("aicredit_c 5", out)

    def test_leading_digit_metric_prefixed(self):
        _base, labels = telemetry._split_key("9lives")
        self.assertEqual(labels, {})
        self.assertTrue(telemetry._sanitize("9lives").startswith("aicredit_"))


class SanitizeTest(unittest.TestCase):
    def test_dots_dashes_spaces(self):
        self.assertEqual(telemetry._sanitize("a.b-c d"), "aicredit_a_b_c_d")

    def test_colon_preserved(self):
        self.assertIn(":", telemetry._sanitize("job:metric"))

    def test_fmt_labels_empty(self):
        self.assertEqual(telemetry._fmt_labels({}), "")

    def test_fmt_labels_escapes(self):
        out = telemetry._fmt_labels({"k": 'a"b\\c\nd'})
        self.assertIn(r"\"", out)
        self.assertIn(r"\\", out)
        self.assertIn(r"\n", out)


class CorrelationFilterTest(unittest.TestCase):
    def test_dash_when_no_context(self):
        obs._correlation_id.set(None)
        obs._trace_id.set(None)
        rec = logging.makeLogRecord({"msg": "m"})
        telemetry.CorrelationFilter().filter(rec)
        self.assertEqual(rec.correlation_id, "-")
        self.assertEqual(rec.trace_id, "-")

    def test_context_values_injected(self):
        obs.start_context("cid-x")
        rec = logging.makeLogRecord({"msg": "m"})
        telemetry.CorrelationFilter().filter(rec)
        self.assertEqual(rec.correlation_id, "cid-x")


class JsonFormatterTest(unittest.TestCase):
    def test_includes_level_and_logger(self):
        rec = logging.makeLogRecord(
            {"msg": "hi", "name": "svc", "levelno": logging.INFO, "levelname": "INFO"}
        )
        telemetry.CorrelationFilter().filter(rec)
        import json

        payload = json.loads(telemetry.JsonLogFormatter().format(rec))
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["logger"], "svc")

    def test_extra_fields_merged(self):
        rec = logging.makeLogRecord({"msg": "hi", "name": "svc"})
        rec.tenant_id = 42
        telemetry.CorrelationFilter().filter(rec)
        import json

        payload = json.loads(telemetry.JsonLogFormatter().format(rec))
        self.assertEqual(payload["tenant_id"], 42)

    def test_non_serializable_extra_stringified(self):
        rec = logging.makeLogRecord({"msg": "hi", "name": "svc"})
        rec.obj = object()
        telemetry.CorrelationFilter().filter(rec)
        import json

        payload = json.loads(telemetry.JsonLogFormatter().format(rec))
        self.assertIsInstance(payload["obj"], str)


class ConfigureLoggingTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("LOG_FORMAT", None)
        reload_settings()

    def test_json_mode_installs_json_formatter(self):
        os.environ["LOG_FORMAT"] = "json"
        reload_settings()
        telemetry.configure_logging(force=True)
        handlers = [h for h in logging.getLogger().handlers if getattr(h, "_aicredit", False)]
        self.assertEqual(len(handlers), 1)
        self.assertIsInstance(handlers[0].formatter, telemetry.JsonLogFormatter)

    def test_console_mode(self):
        os.environ["LOG_FORMAT"] = "console"
        reload_settings()
        telemetry.configure_logging(force=True)
        handlers = [h for h in logging.getLogger().handlers if getattr(h, "_aicredit", False)]
        self.assertEqual(len(handlers), 1)


class TracingGateTest(unittest.TestCase):
    def tearDown(self):
        for k in ("TRACING_ENABLED", "OTEL_EXPORTER_OTLP_ENDPOINT"):
            os.environ.pop(k, None)
        telemetry._TRACING_INITED = False
        reload_settings()

    def test_enabled_without_endpoint_is_noop(self):
        telemetry._TRACING_INITED = False
        os.environ["TRACING_ENABLED"] = "true"
        reload_settings()
        self.assertFalse(telemetry.init_tracing(None))

    def test_instrument_app_best_effort(self):
        # Should never raise even with a bogus app object.
        telemetry.instrument_app(None)


class DomainMetricsTest(unittest.TestCase):
    def setUp(self):
        obs.metrics.reset()

    def test_queue_and_job(self):
        telemetry.domain.queue_depth("q", 9)
        telemetry.domain.job("failed", 3.0, queue="q")
        snap = obs.metrics.snapshot()
        self.assertEqual(snap["gauges"]["queue.depth{queue=q}"], 9)
        self.assertIn("queue.jobs{queue=q,status=failed}", snap["counters"])

    def test_ml_drift_gauge(self):
        telemetry.domain.ml_drift("m", "feat", 0.42)
        self.assertEqual(obs.metrics.snapshot()["gauges"]["ml.drift{feature=feat,model=m}"], 0.42)

    def test_ws_messages_direction(self):
        telemetry.domain.ws_message("in")
        telemetry.domain.ws_message("out")
        counters = obs.metrics.snapshot()["counters"]
        self.assertIn("ws.messages{direction=in}", counters)
        self.assertIn("ws.messages{direction=out}", counters)

    def test_db_pool_gauges(self):
        telemetry.domain.db_pool(3, 20)
        g = obs.metrics.snapshot()["gauges"]
        self.assertEqual(g["db.pool.in_use"], 3)
        self.assertEqual(g["db.pool.size"], 20)

    def test_timed_records_ms(self):
        with telemetry.timed("op", stage="x"):
            pass
        self.assertTrue(any(k.startswith("op") for k in obs.metrics.snapshot()["histograms"]))

    def test_api_request_records_both(self):
        telemetry.domain.api_request("POST", "/p", 201, 4.0)
        snap = obs.metrics.snapshot()
        self.assertIn("http.requests{method=POST,status=201}", snap["counters"])
        self.assertTrue(any(k.startswith("http.latency_ms") for k in snap["histograms"]))


if __name__ == "__main__":
    unittest.main()
