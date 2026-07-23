"""Phase 7 — connector domain + import/snapshot tests (M2, M3, M4, M6, M7, M8).

Exercises every connector (GST, MCA, AA, bureau, ERP, payments) through the
factory + resilience stack, the versioned snapshot store, provider-mode config
switching, bureau normalization across providers, and the production gate.
"""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.services.integrations import config as cfg_svc
from backend.app.services.integrations import service as import_svc
from backend.app.services.integrations import snapshots as snap_store
from backend.app.services.integrations.factory import get_connector, register_all
from backend.app.services.integrations.base.registry import registry
from backend.tests._integrations_helpers import fresh_session, seed_configs

GSTIN = "27ABCDE1234F1Z5"
CIN = "U72200MH2015PTC123456"
PAN = "AAAAA1111A"


class ConfigAndRegistryTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_all_domains_registered(self):
        register_all()
        keys = set(registry.keys())
        self.assertTrue({"gst", "mca", "account_aggregator", "bureau", "erp", "payments"} <= keys)

    def test_seed_configs_idempotent(self):
        n1 = seed_configs(self.db)
        n2 = seed_configs(self.db)
        self.assertEqual(n1, 6)
        self.assertEqual(n2, 0)

    def test_mode_switch(self):
        seed_configs(self.db)
        cfg_svc.set_mode(self.db, "gst", "sandbox")
        self.assertEqual(cfg_svc.resolve_mode(self.db, "gst"), "sandbox")
        conn = get_connector(self.db, "gst")
        self.assertEqual(conn.mode.value, "sandbox")

    def test_default_mode_is_mock(self):
        self.assertEqual(cfg_svc.resolve_mode(self.db, "gst"), "mock")


class GSTConnectorTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)

    def tearDown(self):
        self.db.close()

    def test_profile_deterministic(self):
        c = get_connector(self.db, "gst")
        r1 = c.call("get_profile", {"gstin": GSTIN})
        r2 = get_connector(self.db, "gst").call("get_profile", {"gstin": GSTIN})
        self.assertTrue(r1.success)
        self.assertEqual(r1.data["legal_name"], r2.data["legal_name"])

    def test_returns_and_delays(self):
        c = get_connector(self.db, "gst")
        rr = c.call("get_returns", {"gstin": GSTIN, "months": 12})
        self.assertEqual(len(rr.data["returns"]), 12)
        rd = c.call("get_filing_delays", {"gstin": GSTIN})
        self.assertLessEqual(rd.data["late_filings"], rd.data["total_returns"])

    def test_validate_bad_format(self):
        c = get_connector(self.db, "gst")
        r = c.call("validate", {"gstin": "NOTVALID"})
        self.assertFalse(r.data["valid_format"])

    def test_unknown_operation_fails(self):
        c = get_connector(self.db, "gst")
        r = c.call("nonsense", {"gstin": GSTIN})
        self.assertFalse(r.success)

    def test_import_versions_snapshot(self):
        r, snap = import_svc.import_dataset(self.db, connector_key="gst", entity_ref=GSTIN, operation="get_profile")
        self.assertEqual(snap.version, 1)
        # Same content → no new version.
        r2, snap2 = import_svc.import_dataset(self.db, connector_key="gst", entity_ref=GSTIN, operation="get_profile")
        self.assertEqual(snap2.version, 1)

    def test_import_bundle(self):
        out = import_svc.import_bundle(self.db, connector_key="gst", entity_ref=GSTIN,
                                       operations=["get_profile", "get_filing_status", "get_tax_trends"])
        self.assertEqual(len(out["imported"]), 3)
        self.assertFalse(out["failed"])


class MCAConnectorTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)

    def tearDown(self):
        self.db.close()

    def test_company_master_and_directors(self):
        c = get_connector(self.db, "mca")
        master = c.call("get_company_master", {"cin": CIN})
        self.assertTrue(master.success)
        self.assertIn("authorized_capital", master.data)
        dirs = c.call("get_directors", {"cin": CIN})
        self.assertGreaterEqual(len(dirs.data["directors"]), 2)

    def test_director_network(self):
        c = get_connector(self.db, "mca")
        net = c.call("get_director_network", {"cin": CIN})
        self.assertIn("network", net.data)

    def test_financials(self):
        c = get_connector(self.db, "mca")
        fin = c.call("get_financial_statements", {"cin": CIN})
        self.assertEqual(len(fin.data["statements"]), 3)


class BureauConnectorTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)

    def tearDown(self):
        self.db.close()

    def test_score_and_grade(self):
        c = get_connector(self.db, "bureau")
        r = c.call("get_business_score", {"entity_ref": PAN})
        self.assertIn("score", r.data)
        self.assertIn("grade", r.data)

    def test_normalization_across_providers(self):
        mock = get_connector(self.db, "bureau", mode="mock").call("get_business_score", {"entity_ref": PAN})
        sandbox = get_connector(self.db, "bureau", mode="sandbox").call("get_business_score", {"entity_ref": PAN})
        self.assertEqual(set(mock.data.keys()), set(sandbox.data.keys()))
        self.assertNotEqual(mock.data["bureau"], sandbox.data["bureau"])

    def test_full_report(self):
        c = get_connector(self.db, "bureau")
        r = c.call("get_full_report", {"entity_ref": PAN})
        for key in ("score", "defaults", "outstanding", "dpd", "utilization"):
            self.assertIn(key, r.data)

    def test_dpd_history(self):
        c = get_connector(self.db, "bureau")
        r = c.call("get_dpd_history", {"entity_ref": PAN})
        self.assertEqual(len(r.data["dpd_history"]), 12)


class ERPConnectorTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)

    def tearDown(self):
        self.db.close()

    def test_systems_supported(self):
        for system in ("sap", "oracle", "dynamics", "zoho", "quickbooks", "tally"):
            c = get_connector(self.db, "erp", system=system)
            r = c.call("get_financial_statements", {"entity_ref": "E1"})
            self.assertTrue(r.success, r.error)
            self.assertEqual(r.data["system"], system)

    def test_unsupported_system_fails(self):
        c = get_connector(self.db, "erp")
        r = c.call("get_financial_statements", {"entity_ref": "E1", "system": "peachtree"})
        self.assertFalse(r.success)

    def test_trial_balance_balances(self):
        c = get_connector(self.db, "erp", system="tally")
        r = c.call("get_trial_balance", {"entity_ref": "E1"})
        self.assertAlmostEqual(r.data["total_debit"], r.data["total_credit"], places=2)

    def test_receivables_aging(self):
        c = get_connector(self.db, "erp", system="zoho")
        r = c.call("get_receivables", {"entity_ref": "E1"})
        self.assertIn("aging", r.data)


class PaymentsConnectorTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)

    def tearDown(self):
        self.db.close()

    def test_transaction_health(self):
        c = get_connector(self.db, "payments")
        r = c.call("get_transaction_health", {"entity_ref": "E1"})
        self.assertGreaterEqual(r.data["health_score"], 0)
        self.assertLessEqual(r.data["health_score"], 100)

    def test_payment_behaviour_rail_mix(self):
        c = get_connector(self.db, "payments")
        r = c.call("get_payment_behaviour", {"entity_ref": "E1"})
        self.assertIn("rail_mix", r.data)

    def test_counterparty_risk(self):
        c = get_connector(self.db, "payments")
        r = c.call("get_counterparty_risk", {"entity_ref": "E1"})
        self.assertIn("concentration", r.data)


class ProductionGateTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)

    def tearDown(self):
        self.db.close()

    def test_production_requires_credentials(self):
        for key, op, params in [
            ("gst", "get_profile", {"gstin": GSTIN}),
            ("mca", "get_company_master", {"cin": CIN}),
            ("bureau", "get_business_score", {"entity_ref": PAN}),
        ]:
            c = get_connector(self.db, key, mode="production")
            r = c.call(op, params)
            self.assertFalse(r.success)
            self.assertIn("not configured", r.error)


if __name__ == "__main__":
    unittest.main()
