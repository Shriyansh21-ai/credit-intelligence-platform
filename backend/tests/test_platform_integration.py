""" integration tests over the real application.

Exercises the full middleware stack (security headers, API-version, gzip
observability), the probes, and the Prometheus /metrics endpoint end-to-end
plus telemetry render edge cases.
"""

import unittest

from fastapi.testclient import TestClient

from backend.app.core import telemetry
from backend.app.main import app
from backend.app.services.saas import observability as obs


class ProbeIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_livez(self):
        r = self.client.get("/livez")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "alive")

    def test_healthz(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)

    def test_readyz(self):
        r = self.client.get("/readyz")
        self.assertEqual(r.status_code, 200)
        self.assertIn("status", r.json())

    def test_root(self):
        self.assertEqual(self.client.get("/").status_code, 200)


class MiddlewareStackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_security_headers_on_every_response(self):
        r = self.client.get("/livez")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertIn("Content-Security-Policy", r.headers)
        self.assertIn("Referrer-Policy", r.headers)

    def test_correlation_id_echoed(self):
        r = self.client.get("/livez", headers={"X-Correlation-ID": "test-cid-999"})
        self.assertEqual(r.headers.get("X-Correlation-ID"), "test-cid-999")

    def test_api_version_header(self):
        r = self.client.get("/livez")
        self.assertEqual(r.headers.get("X-API-Version"), "v1")

    def test_correlation_id_generated_when_absent(self):
        r = self.client.get("/healthz")
        self.assertTrue(r.headers.get("X-Correlation-ID"))


class MetricsEndpointIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_metrics_content_type_and_namespace(self):
        # Generate some traffic first so counters exist.
        self.client.get("/livez")
        r = self.client.get("/metrics")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/plain", r.headers["content-type"])
        self.assertIn("aicredit_build_info", r.text)

    def test_http_request_metric_recorded(self):
        obs.metrics.reset()
        self.client.get("/livez")
        r = self.client.get("/metrics")
        self.assertIn("aicredit_http_requests", r.text)

    def test_metrics_valid_exposition_lines(self):
        r = self.client.get("/metrics")
        for line in r.text.splitlines():
            if line and not line.startswith("#"):
                # metric lines must have a value token
                self.assertGreaterEqual(len(line.rsplit(" ", 1)), 2)


class TelemetryRenderExtraTest(unittest.TestCase):
    def setUp(self):
        obs.metrics.reset()

    def test_empty_registry_renders_build_info(self):
        out = telemetry.render_prometheus()
        self.assertIn("aicredit_build_info", out)

    def test_gauge_updates_last_wins(self):
        obs.metrics.gauge("q.depth", 3, queue="a")
        obs.metrics.gauge("q.depth", 7, queue="a")
        out = telemetry.render_prometheus()
        self.assertIn('aicredit_q_depth{queue="a"} 7', out)

    def test_counter_accumulates(self):
        obs.metrics.incr("hits")
        obs.metrics.incr("hits")
        out = telemetry.render_prometheus()
        self.assertIn("aicredit_hits 2", out)

    def test_domain_business_and_ml(self):
        telemetry.domain.business_event("approved")
        telemetry.domain.ml_inference("m", 5.0)
        out = telemetry.render_prometheus()
        self.assertIn("aicredit_business_approved", out)
        self.assertIn("aicredit_ml_inference_ms", out)


class OpenApiIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_openapi_available_with_metadata(self):
        r = self.client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)
        spec = r.json()
        self.assertIn("info", spec)
        self.assertIn("contact", spec["info"])

    def test_metrics_excluded_from_schema(self):
        spec = self.client.get("/openapi.json").json()
        self.assertNotIn("/metrics", spec.get("paths", {}))


if __name__ == "__main__":
    unittest.main()
