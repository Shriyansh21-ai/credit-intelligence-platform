"""Phase 7 — synchronization engine + Open API platform tests (M11, M12)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.models.integrations import IntegrationSnapshot, SyncDeadLetter
from backend.app.services.integrations import snapshots as snap_store
from backend.app.services.integrations.apiplatform import service as api_svc
from backend.app.services.integrations.apiplatform import webhooks as wh_svc
from backend.app.services.integrations.sync import service as sync_svc
from backend.tests._integrations_helpers import fresh_session, seed_configs

GSTIN = "27ABCDE1234F1Z5"


class SyncEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)

    def tearDown(self):
        self.db.close()

    def test_full_sync_processes_all(self):
        job = sync_svc.run_sync(self.db, sync_type="full", connectors=["gst", "bureau"],
                                entity_refs=[GSTIN, "AAAAA1111A"])
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.stats["targets"], 4)
        self.assertEqual(job.stats["processed"], 4)

    def test_incremental_skips_fresh(self):
        sync_svc.run_sync(self.db, sync_type="full", connectors=["gst"], entity_refs=[GSTIN])
        job2 = sync_svc.run_sync(self.db, sync_type="incremental", connectors=["gst"], entity_refs=[GSTIN])
        self.assertEqual(job2.stats["skipped"], 1)
        self.assertEqual(job2.stats["processed"], 0)

    def test_conflict_detected_on_change(self):
        # Seed a differing current snapshot so a re-fetch produces a conflict.
        snap_store.save_snapshot(self.db, connector_key="gst", provider="mock_gst", mode="mock",
                                 dataset="get_profile", entity_ref=GSTIN, payload={"status": "STALE"},
                                 refresh_after_days=-1)
        job = sync_svc.run_sync(self.db, sync_type="full", connectors=["gst"], entity_refs=[GSTIN])
        self.assertEqual(job.stats["conflicts"], 1)
        self.assertEqual(len(job.conflicts), 1)

    def test_dead_letter_and_replay(self):
        job = sync_svc.start_job(self.db, sync_type="full", connectors=["gst"], entity_refs=[GSTIN])
        # Force a dead letter by processing with an unknown operation mapping.
        sync_svc.process_job(self.db, job.id, operations={"gst": "does_not_exist"})
        dls = self.db.query(SyncDeadLetter).filter(SyncDeadLetter.resolved.is_(False)).all()
        self.assertEqual(len(dls), 1)
        # Replay with a valid default operation.
        dls[0].operation = "get_profile"
        self.db.commit()
        result = sync_svc.replay_dead_letters(self.db, job_id=job.id)
        self.assertEqual(result["resolved"], 1)

    def test_job_serialization(self):
        job = sync_svc.run_sync(self.db, sync_type="full", connectors=["gst"], entity_refs=[GSTIN])
        d = sync_svc.job_to_dict(job)
        self.assertIn("stats", d)
        self.assertIn("connectors", d)


class ApiKeyTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_create_and_verify(self):
        row, raw = api_svc.create_api_key(self.db, name="partner", scopes=["read"])
        self.assertTrue(raw.startswith("cak_"))
        self.assertIsNotNone(api_svc.verify_api_key(self.db, raw))
        self.assertIsNone(api_svc.verify_api_key(self.db, "bogus"))

    def test_scope_check(self):
        row, raw = api_svc.create_api_key(self.db, name="p", scopes=["read"])
        self.assertTrue(api_svc.check_scope(row, "read"))
        self.assertFalse(api_svc.check_scope(row, "write"))

    def test_revoke(self):
        row, raw = api_svc.create_api_key(self.db, name="p", scopes=["read"])
        api_svc.revoke_api_key(self.db, row.id)
        self.assertIsNone(api_svc.verify_api_key(self.db, raw))

    def test_rate_limit(self):
        row, raw = api_svc.create_api_key(self.db, name="p", rate_limit_per_min=2)
        self.assertTrue(api_svc.enforce_rate_limit(self.db, row))
        api_svc.record_usage(self.db, api_key_id=row.id, endpoint="/x", method="GET", status_code=200, latency_ms=1)
        api_svc.record_usage(self.db, api_key_id=row.id, endpoint="/x", method="GET", status_code=200, latency_ms=1)
        self.assertFalse(api_svc.enforce_rate_limit(self.db, row))

    def test_usage_analytics(self):
        row, raw = api_svc.create_api_key(self.db, name="p")
        api_svc.record_usage(self.db, api_key_id=row.id, endpoint="/a", method="GET", status_code=200, latency_ms=5)
        api_svc.record_usage(self.db, api_key_id=row.id, endpoint="/a", method="GET", status_code=500, latency_ms=15)
        stats = api_svc.usage_analytics(self.db, api_key_id=row.id)
        self.assertEqual(stats["total_calls"], 2)
        self.assertAlmostEqual(stats["avg_latency_ms"], 10.0)


class WebhookTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_subscription_validation(self):
        with self.assertRaises(ValueError):
            wh_svc.create_subscription(self.db, url="https://x", events=["not.a.real.event"])

    def test_emit_fans_out_and_signs(self):
        wh_svc.create_subscription(self.db, url="https://a", events=["snapshot.created"], secret="s")
        wh_svc.create_subscription(self.db, url="https://b", events=["*"])
        wh_svc.create_subscription(self.db, url="https://c", events=["consent.revoked"])
        deliveries = wh_svc.emit(self.db, "snapshot.created", {"entity": "E1"})
        self.assertEqual(len(deliveries), 2)  # a (explicit) + b (wildcard), not c
        signed = [d for d in deliveries if "_signature" in (d.payload or {})]
        self.assertEqual(len(signed), 1)

    def test_delivery_history(self):
        sub = wh_svc.create_subscription(self.db, url="https://a", events=["sync.completed"])
        wh_svc.emit(self.db, "sync.completed", {"job": 1})
        hist = wh_svc.delivery_history(self.db, subscription_id=sub.id)
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0].status, "delivered")


if __name__ == "__main__":
    unittest.main()
