"""Phase 8 — Real-time (M8), observability (M9) and cache (M10) platforms."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.models.user import User
from backend.app.services.saas import observability as obs
from backend.app.services.saas import realtime
from backend.app.services.saas import tenancy as tsvc
from backend.app.services.saas.cache import CachePlatform, MemoryCacheBackend
from backend.tests._saas_helpers import fresh_session, seed_all


class RealtimeTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)
        self.org = tsvc.create_organization(self.db, slug="rt", name="RT")
        self.tid = tsvc.default_tenant(self.db, self.org.id).id

    def tearDown(self):
        self.db.close()

    def test_publish_persists_activity(self):
        realtime.publish(self.db, channel="apps", event_type="app.created",
                         tenant_id=self.tid, actor="rm@x", subject="42")
        feed = realtime.recent_activity(self.db, tenant_id=self.tid)
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0].event_type, "app.created")

    def test_channel_filtering(self):
        realtime.publish(self.db, channel="a", event_type="x", tenant_id=self.tid)
        realtime.publish(self.db, channel="b", event_type="y", tenant_id=self.tid)
        self.assertEqual(len(realtime.recent_activity(self.db, tenant_id=self.tid, channel="a")), 1)

    def test_hub_fanout_to_connection(self):
        conn = realtime.hub.connect(tenant_id=self.tid, channels={"apps"})
        realtime.publish(self.db, channel="apps", event_type="e", tenant_id=self.tid)
        self.assertFalse(conn.queue.empty())
        event = conn.queue.get_nowait()
        self.assertEqual(event["event_type"], "e")
        realtime.hub.disconnect(conn.id)

    def test_hub_tenant_scoping(self):
        conn = realtime.hub.connect(tenant_id=self.tid, channels={"apps"})
        realtime.publish(self.db, channel="apps", event_type="e", tenant_id=99999)
        self.assertTrue(conn.queue.empty())  # different tenant not delivered
        realtime.hub.disconnect(conn.id)

    def test_presence(self):
        u = User(email="p@rt.com", password="x")
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        realtime.mark_presence(self.db, self.tid, u.id, status="online")
        self.assertEqual(len(realtime.online_users(self.db, self.tid)), 1)
        realtime.mark_presence(self.db, self.tid, u.id, status="offline")
        self.assertEqual(len(realtime.online_users(self.db, self.tid)), 0)


class ObservabilityTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)
        obs.metrics.reset()

    def tearDown(self):
        self.db.close()

    def test_correlation_context(self):
        cid = obs.start_context()
        self.assertEqual(obs.current_correlation_id(), cid)

    def test_metrics_counters_and_histograms(self):
        obs.metrics.incr("hits", 3)
        obs.metrics.observe("latency", 10)
        obs.metrics.observe("latency", 30)
        snap = obs.metrics.snapshot()
        self.assertEqual(snap["counters"]["hits"], 3)
        self.assertEqual(snap["histograms"]["latency"]["count"], 2)

    def test_trace_span_persist(self):
        obs.start_context()
        with obs.trace(self.db, "op.slow"):
            pass
        cid = obs.current_correlation_id()
        spans = obs.trace_timeline(self.db, cid)
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].name, "op.slow")

    def test_trace_records_error_status(self):
        obs.start_context()
        with self.assertRaises(RuntimeError):
            with obs.trace(self.db, "op.err"):
                raise RuntimeError("x")
        spans = obs.trace_timeline(self.db, obs.current_correlation_id())
        self.assertEqual(spans[0].status, "error")

    def test_slow_query_detection(self):
        obs.record_query("SELECT * FROM big", 500.0)
        obs.record_query("SELECT 1", 5.0)
        slow = obs.slow_queries()
        self.assertTrue(any(q["duration_ms"] == 500.0 for q in slow))

    def test_error_analytics(self):
        obs.record_error("ValueError", "bad input")
        obs.record_error("ValueError", "bad input 2")
        a = obs.error_analytics()
        self.assertGreaterEqual(a["by_kind"].get("ValueError", 0), 2)

    def test_health_report(self):
        report = obs.health_report(self.db)
        self.assertIn(report["status"], ("healthy", "degraded"))
        self.assertTrue(any(c["name"] == "database" for c in report["checks"]))

    def test_service_map(self):
        sm = obs.service_map()
        self.assertIn("dependencies", sm)
        self.assertTrue(len(sm["edges"]) > 0)


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.cache = CachePlatform(MemoryCacheBackend())

    def test_set_get(self):
        self.cache.set("k", 123, tenant_id=1)
        self.assertEqual(self.cache.get("k", tenant_id=1), 123)

    def test_tenant_isolation(self):
        self.cache.set("k", "a", tenant_id=1)
        self.cache.set("k", "b", tenant_id=2)
        self.assertEqual(self.cache.get("k", tenant_id=1), "a")
        self.assertEqual(self.cache.get("k", tenant_id=2), "b")

    def test_miss_returns_none(self):
        self.assertIsNone(self.cache.get("absent", tenant_id=1))

    def test_get_or_set(self):
        calls = {"n": 0}

        def factory():
            calls["n"] += 1
            return "computed"

        self.assertEqual(self.cache.get_or_set("x", factory, tenant_id=1), "computed")
        self.assertEqual(self.cache.get_or_set("x", factory, tenant_id=1), "computed")
        self.assertEqual(calls["n"], 1)  # cached second time

    def test_invalidate(self):
        self.cache.set("k", 1, tenant_id=1)
        self.cache.invalidate("k", tenant_id=1)
        self.assertIsNone(self.cache.get("k", tenant_id=1))

    def test_invalidate_tenant_namespace(self):
        self.cache.set("a", 1, tenant_id=1)
        self.cache.set("b", 2, tenant_id=1)
        self.cache.set("c", 3, tenant_id=2)
        removed = self.cache.invalidate_tenant(1)
        self.assertEqual(removed, 2)
        self.assertEqual(self.cache.get("c", tenant_id=2), 3)

    def test_warm_and_stats(self):
        self.cache.warm([("a", 1), ("b", 2)], tenant_id=1)
        self.cache.get("a", tenant_id=1)
        self.cache.get("missing", tenant_id=1)
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hit_rate"], 0.5)

    def test_ttl_expiry(self):
        clock = {"t": 0.0}
        cache = CachePlatform(MemoryCacheBackend(clock=lambda: clock["t"]))
        cache.set("k", 1, ttl=10, tenant_id=1)
        clock["t"] = 5
        self.assertEqual(cache.get("k", tenant_id=1), 1)
        clock["t"] = 11
        self.assertIsNone(cache.get("k", tenant_id=1))


if __name__ == "__main__":
    unittest.main()
