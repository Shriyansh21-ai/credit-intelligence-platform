"""Phase 11, M10 — API platform tests (versioning + webhook robustness)."""

import unittest
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core import api_versioning as ver
from backend.app.core import webhooks


class VersionRegistryTest(unittest.TestCase):
    def test_register_and_extract(self):
        reg = ver.VersionRegistry()
        reg.register(ver.APIVersion("v1"), current=True)
        reg.register(ver.APIVersion("v2"))
        self.assertEqual(reg.current, "v1")
        self.assertEqual(reg.extract_version("/api/v2/applications"), "v2")
        self.assertIsNone(reg.extract_version("/api/v9/x"))
        self.assertIsNone(reg.extract_version("/healthz"))

    def test_deprecation_and_sunset_dates(self):
        v = ver.APIVersion("v1", deprecated_on=date(2026, 1, 1), sunset_on=date(2026, 6, 1))
        self.assertTrue(v.is_deprecated(on=date(2026, 3, 1)))
        self.assertFalse(v.is_deprecated(on=date(2025, 12, 1)))
        self.assertTrue(v.is_sunset(on=date(2026, 7, 1)))
        self.assertFalse(v.is_sunset(on=date(2026, 5, 1)))

    def test_status_implies_deprecated(self):
        v = ver.APIVersion("v0", status=ver.VersionStatus.DEPRECATED)
        self.assertTrue(v.is_deprecated())


class VersionMiddlewareTest(unittest.TestCase):
    def _app(self, registry):
        app = FastAPI()
        app.add_middleware(ver.APIVersionMiddleware, version_registry=registry)

        @app.get("/api/v1/ping")
        def _p1():
            return {"ok": True}

        @app.get("/api/v2/ping")
        def _p2():
            return {"ok": True}

        return TestClient(app)

    def test_active_version_header(self):
        reg = ver.VersionRegistry()
        reg.register(ver.APIVersion("v1"), current=True)
        r = self._app(reg).get("/api/v1/ping")
        self.assertEqual(r.headers["X-API-Version"], "v1")
        self.assertNotIn("Deprecation", r.headers)

    def test_deprecated_version_headers(self):
        reg = ver.VersionRegistry()
        reg.register(ver.APIVersion("v1"), current=True)
        reg.register(
            ver.APIVersion(
                "v2",
                status=ver.VersionStatus.DEPRECATED,
                sunset_on=date(2027, 1, 1),
                docs_url="/docs#v2",
            )
        )
        r = self._app(reg).get("/api/v2/ping")
        self.assertEqual(r.headers["X-API-Version"], "v2")
        self.assertEqual(r.headers["Deprecation"], "true")
        self.assertEqual(r.headers["Sunset"], "2027-01-01")
        self.assertIn('rel="deprecation"', r.headers["Link"])


class WebhookSigningTest(unittest.TestCase):
    def test_sign_verify_roundtrip(self):
        body = {"event": "loan.approved", "data": {"id": 1}}
        header = webhooks.sign("whsec", body, timestamp=1_700_000_000)
        self.assertTrue(webhooks.verify("whsec", body, header, now=1_700_000_100))

    def test_tampered_body_fails(self):
        header = webhooks.sign("whsec", {"a": 1}, timestamp=1_700_000_000)
        self.assertFalse(webhooks.verify("whsec", {"a": 2}, header, now=1_700_000_000))

    def test_replay_outside_tolerance_fails(self):
        header = webhooks.sign("whsec", {"a": 1}, timestamp=1_700_000_000)
        # 10 minutes later, tolerance 300s -> rejected as replay.
        self.assertFalse(webhooks.verify("whsec", {"a": 1}, header, now=1_700_000_000 + 600))

    def test_wrong_secret_fails(self):
        header = webhooks.sign("whsec", {"a": 1}, timestamp=1_700_000_000)
        self.assertFalse(webhooks.verify("other", {"a": 1}, header, now=1_700_000_000))

    def test_malformed_header(self):
        self.assertFalse(webhooks.verify("whsec", {}, "garbage", now=1))


class RetryPolicyTest(unittest.TestCase):
    def test_backoff_schedule(self):
        p = webhooks.RetryPolicy(
            max_attempts=5, base_delay_seconds=1, factor=2, max_delay_seconds=10
        )
        self.assertEqual(p.delay_for(1), 0.0)  # first attempt immediate
        self.assertEqual(p.delay_for(2), 1.0)
        self.assertEqual(p.delay_for(3), 2.0)
        self.assertEqual(p.delay_for(4), 4.0)
        self.assertEqual(p.delay_for(5), 8.0)
        self.assertEqual(len(p.schedule()), 5)

    def test_delay_capped(self):
        p = webhooks.RetryPolicy(
            max_attempts=10, base_delay_seconds=1, factor=10, max_delay_seconds=5
        )
        self.assertEqual(p.delay_for(9), 5.0)


class DispatcherTest(unittest.TestCase):
    def setUp(self):
        self.slept = []
        self.policy = webhooks.RetryPolicy(max_attempts=4, base_delay_seconds=1, factor=2)

    def _dispatcher(self, transport):
        return webhooks.WebhookDispatcher(
            transport, policy=self.policy, sleep=self.slept.append, clock=lambda: 1_700_000_000
        )

    def test_success_first_attempt(self):
        d = self._dispatcher(lambda url, headers, body: 200)
        res = d.deliver("https://x/hook", "s", "e", {"id": 1})
        self.assertTrue(res.delivered)
        self.assertEqual(res.attempt_count, 1)
        self.assertEqual(self.slept, [])  # no backoff before first attempt

    def test_retries_then_succeeds(self):
        calls = {"n": 0}

        def transport(url, headers, body):
            calls["n"] += 1
            return 200 if calls["n"] == 3 else 500

        res = self._dispatcher(transport).deliver("https://x/hook", "s", "e", {"id": 1})
        self.assertTrue(res.delivered)
        self.assertEqual(res.attempt_count, 3)
        self.assertEqual(self.slept, [1.0, 2.0])  # backoff before attempts 2 and 3

    def test_exhausts_attempts(self):
        def transport(url, headers, body):
            raise ConnectionError("boom")

        res = self._dispatcher(transport).deliver("https://x/hook", "s", "e", {"id": 1})
        self.assertFalse(res.delivered)
        self.assertEqual(res.attempt_count, 4)
        self.assertTrue(all(not a.ok for a in res.attempts))

    def test_signed_headers_present_and_verifiable(self):
        captured = {}

        def transport(url, headers, body):
            captured.update(headers=headers, body=body)
            return 200

        d = self._dispatcher(transport)
        d.deliver("https://x/hook", "whsec", "loan.approved", {"id": 1})
        sig = captured["headers"][webhooks.SIGNATURE_HEADER]
        self.assertTrue(webhooks.verify("whsec", captured["body"], sig, now=1_700_000_000))

    def test_replay_redelivers(self):
        d = self._dispatcher(lambda url, headers, body: 200)
        res = d.replay("https://x/hook", "s", "e", {"id": 1})
        self.assertTrue(res.delivered)


if __name__ == "__main__":
    unittest.main()
