""" connector framework tests.

Covers the resilience primitives (retry / circuit breaker / rate limiter), the
security layer (secret resolution, encryption, PII masking), the observability
collector, the registry, and the BaseConnector call flow (auth, cache, retries
circuit short-circuit, metrics) with a synthetic in-test connector.
"""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.services.integrations.base.connector import BaseConnector
from backend.app.services.integrations.base.exceptions import (
    AuthenticationError, CircuitOpenError, ConfigurationError, ProviderError,
)
from backend.app.services.integrations.base.observability import MetricsCollector
from backend.app.services.integrations.base.registry import ConnectorRegistry
from backend.app.services.integrations.base.resilience import (
    CircuitBreaker, RateLimiter, RetryPolicy,
)
from backend.app.services.integrations.base.security import (
    SecretResolver, decrypt_secret, encrypt_secret, mask_pii, mask_text, mask_value,
)
from backend.app.services.integrations.base.types import (
    ConnectorCategory, ConnectorRequest, ProviderMode,
)


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------
class RetryPolicyTest(unittest.TestCase):
    def test_retries_retriable_then_succeeds(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ProviderError("transient")
            return "ok"

        rp = RetryPolicy(max_attempts=5, sleep=lambda s: None)
        self.assertEqual(rp.run(fn), "ok")
        self.assertEqual(calls["n"], 3)

    def test_does_not_retry_non_retriable(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            raise AuthenticationError("bad creds")

        rp = RetryPolicy(max_attempts=5, sleep=lambda s: None)
        with self.assertRaises(AuthenticationError):
            rp.run(fn)
        self.assertEqual(calls["n"], 1)

    def test_exhausts_and_raises_last(self):
        rp = RetryPolicy(max_attempts=3, sleep=lambda s: None)
        with self.assertRaises(ProviderError):
            rp.run(lambda: (_ for _ in ()).throw(ProviderError("always")))

    def test_backoff_grows_and_caps(self):
        rp = RetryPolicy(base_backoff=0.1, max_backoff=0.5)
        self.assertAlmostEqual(rp.backoff_for(1), 0.1)
        self.assertAlmostEqual(rp.backoff_for(2), 0.2)
        self.assertAlmostEqual(rp.backoff_for(10), 0.5)  # capped


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------
class CircuitBreakerTest(unittest.TestCase):
    def test_trips_open_after_threshold(self):
        clk = _Clock()
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10, clock=clk)
        for _ in range(3):
            cb.record_failure()
        self.assertEqual(cb.state, "open")
        self.assertFalse(cb.allow())

    def test_half_open_after_timeout_then_close(self):
        clk = _Clock()
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=5, success_threshold=1, clock=clk)
        cb.record_failure(); cb.record_failure()
        self.assertEqual(cb.state, "open")
        clk.advance(6)
        self.assertEqual(cb.state, "half_open")
        cb.record_success()
        self.assertEqual(cb.state, "closed")

    def test_half_open_failure_reopens(self):
        clk = _Clock()
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=5, clock=clk)
        cb.record_failure()
        clk.advance(6)
        self.assertEqual(cb.state, "half_open")
        cb.record_failure()
        self.assertEqual(cb.state, "open")

    def test_call_short_circuits_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=100)
        cb.record_failure()
        with self.assertRaises(CircuitOpenError):
            cb.call(lambda: "never")

    def test_success_resets_failures_when_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure(); cb.record_failure()
        cb.record_success()
        cb.record_failure(); cb.record_failure()
        self.assertEqual(cb.state, "closed")  # counter was reset


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
class RateLimiterTest(unittest.TestCase):
    def test_consumes_and_refills(self):
        clk = _Clock()
        rl = RateLimiter(rate=1, capacity=2, clock=clk)
        self.assertTrue(rl.acquire())
        self.assertTrue(rl.acquire())
        self.assertFalse(rl.acquire())
        clk.advance(1.0)
        self.assertTrue(rl.acquire())

    def test_enforce_raises(self):
        clk = _Clock()
        rl = RateLimiter(rate=1, capacity=1, clock=clk)
        rl.enforce()
        with self.assertRaises(Exception):
            rl.enforce()

    def test_capacity_cap(self):
        clk = _Clock()
        rl = RateLimiter(rate=5, capacity=3, clock=clk)
        clk.advance(100)
        self.assertLessEqual(rl.available, 3)


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
class SecurityTest(unittest.TestCase):
    def test_secret_resolution_precedence(self):
        sr = SecretResolver(store={"gst.api_key": "store-val"}, env=lambda k: "env-val")
        self.assertEqual(sr.resolve("gst.api_key"), "store-val")
        self.assertEqual(sr.resolve("other.key"), "env-val")

    def test_secret_missing_raises(self):
        sr = SecretResolver(store={}, env=lambda k: None)
        with self.assertRaises(ConfigurationError):
            sr.resolve("missing")

    def test_encrypt_roundtrip(self):
        tok = encrypt_secret("super-secret", key="k1", salt=b"0" * 16)
        self.assertNotIn("super-secret", tok)
        self.assertEqual(decrypt_secret(tok, key="k1"), "super-secret")

    def test_mask_value(self):
        self.assertTrue(mask_value("1234567890").endswith("7890"))
        self.assertTrue(mask_value("1234567890").startswith("*"))

    def test_mask_text_redacts_pan_and_email(self):
        masked = mask_text("PAN ABCDE1234F and mail x@y.com")
        self.assertNotIn("ABCDE1234F", masked)
        self.assertIn("x***@y.com", masked)

    def test_mask_pii_dict_recursive(self):
        m = mask_pii({"api_key": "secretvalue", "nested": {"account_number": "123456789012"}})
        self.assertTrue(m["api_key"].startswith("*"))
        self.assertTrue(m["nested"]["account_number"].endswith("9012"))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTest(unittest.TestCase):
    def test_records_and_aggregates(self):
        mc = MetricsCollector()
        mc.record("gov", "p1", success=True, latency_ms=10, attempts=1)
        mc.record("gov", "p1", success=False, latency_ms=20, attempts=2)
        mc.record("gov", "p1", success=True, latency_ms=30, cache_hit=True)
        snap = mc.for_provider("gov", "p1")
        self.assertEqual(snap["calls"], 3)
        self.assertEqual(snap["failures"], 1)
        self.assertEqual(snap["retries"], 1)
        self.assertEqual(snap["cache_hits"], 1)
        self.assertAlmostEqual(snap["avg_latency_ms"], 20.0)

    def test_totals(self):
        mc = MetricsCollector()
        mc.record("a", "x", success=True, latency_ms=5)
        mc.record("b", "y", success=False, latency_ms=5)
        totals = mc.totals()
        self.assertEqual(totals["calls"], 2)
        self.assertEqual(totals["providers"], 2)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class _DummyConn(BaseConnector):
    category = ConnectorCategory.BANKING

    def _execute(self, request):
        return {"echo": request.params}


class RegistryTest(unittest.TestCase):
    def test_register_and_create(self):
        reg = ConnectorRegistry()
        reg.register("dummy", ProviderMode.MOCK,
                     lambda **kw: _DummyConn(provider="dummy", **kw),
                     category=ConnectorCategory.BANKING)
        self.assertTrue(reg.is_registered("dummy"))
        self.assertTrue(reg.is_registered("dummy", "mock"))
        conn = reg.create("dummy", "mock")
        self.assertIsInstance(conn, _DummyConn)

    def test_unknown_key_raises(self):
        reg = ConnectorRegistry()
        with self.assertRaises(ConfigurationError):
            reg.create("nope")

    def test_missing_mode_raises(self):
        reg = ConnectorRegistry()
        reg.register("dummy", ProviderMode.MOCK, lambda **kw: _DummyConn(provider="dummy", **kw))
        with self.assertRaises(ConfigurationError):
            reg.create("dummy", "production")


# ---------------------------------------------------------------------------
# BaseConnector call flow
# ---------------------------------------------------------------------------
class _FlakyConn(BaseConnector):
    category = ConnectorCategory.BANKING

    def __init__(self, fail_times=0, **kw):
        super().__init__(provider="flaky", **kw)
        self._fail_times = fail_times
        self.calls = 0

    def _execute(self, request):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ProviderError("boom")
        return {"ok": True, "n": self.calls}


class BaseConnectorFlowTest(unittest.TestCase):
    def test_success_and_cache(self):
        mc = MetricsCollector()
        c = _FlakyConn(metrics_collector=mc)
        r1 = c.call("op", {"x": 1})
        self.assertTrue(r1.success)
        self.assertFalse(r1.from_cache)
        r2 = c.call("op", {"x": 1})
        self.assertTrue(r2.from_cache)  # served from cache
        self.assertEqual(c.calls, 1)    # provider only hit once
        self.assertEqual(mc.for_provider("banking", "flaky")["cache_hits"], 1)

    def test_retry_then_success(self):
        c = _FlakyConn(fail_times=2, retry=RetryPolicy(max_attempts=4, sleep=lambda s: None))
        r = c.call("op", {"x": 2})
        self.assertTrue(r.success)
        self.assertGreaterEqual(r.attempts, 3)

    def test_failure_returns_unsuccessful_response(self):
        c = _FlakyConn(fail_times=10, retry=RetryPolicy(max_attempts=2, sleep=lambda s: None))
        r = c.call("op", {"x": 3})
        self.assertFalse(r.success)
        self.assertIsNotNone(r.error)

    def test_circuit_opens_after_failures(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=100)
        c = _FlakyConn(fail_times=100, breaker=cb,
                       retry=RetryPolicy(max_attempts=1, sleep=lambda s: None))
        c.call("op", {"a": 1})
        c.call("op", {"b": 2})
        self.assertEqual(c.circuit_state, "open")
        r = c.call("op", {"c": 3})
        self.assertFalse(r.success)
        self.assertIn("circuit", r.error.lower())

    def test_auth_failure_is_terminal(self):
        class _AuthConn(BaseConnector):
            category = ConnectorCategory.BANKING

            def _authenticate(self):
                raise AuthenticationError("no creds")

            def _execute(self, request):
                return {"never": True}

        c = _AuthConn(provider="auth")
        r = c.call("op", {})
        self.assertFalse(r.success)
        self.assertIn("no creds", r.error)

    def test_health_check(self):
        c = _FlakyConn()
        report = c.health_check()
        self.assertEqual(report.status.value, "healthy")


if __name__ == "__main__":
    unittest.main()
