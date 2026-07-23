"""Phase 7 — Account Aggregator + bank statement analytics tests (M4, M5)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.services.integrations.aa import service as aa_svc
from backend.app.services.integrations.analytics import compute_metrics
from backend.app.services.integrations.analytics import statement as analytics_svc
from backend.tests._integrations_helpers import fresh_session, seed_configs


class ConsentLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)

    def tearDown(self):
        self.db.close()

    def test_consent_create_and_activate(self):
        c = aa_svc.create_consent(self.db, entity_ref="ENT1", months=6)
        self.assertEqual(c.status, "pending")
        c = aa_svc.sync_consent_status(self.db, c.id)
        self.assertIn(c.status, ("active", "rejected"))

    def test_consent_revoke(self):
        c = aa_svc.create_consent(self.db, entity_ref="ENT1")
        c = aa_svc.revoke_consent(self.db, c.id)
        self.assertEqual(c.status, "revoked")

    def test_discover_requires_active(self):
        c = aa_svc.create_consent(self.db, entity_ref="ENT1")
        with self.assertRaises(ValueError):
            aa_svc.discover_accounts(self.db, c.id)  # still pending

    def test_import_requires_active_consent(self):
        c = aa_svc.create_consent(self.db, entity_ref="ENT1")  # pending
        with self.assertRaises(ValueError):
            aa_svc.import_statement(self.db, entity_ref="ENT1", account_ref="X", consent_id=c.id)


class StatementImportTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)

    def tearDown(self):
        self.db.close()

    def test_import_persists_transactions(self):
        stmt = aa_svc.import_statement(self.db, entity_ref="ENT1", account_ref="XXXX1", months=6)
        self.assertGreater(stmt.txn_count, 0)
        d = aa_svc.statement_to_dict(stmt, with_transactions=True, db=self.db)
        self.assertEqual(len(d["transactions"]), stmt.txn_count)


class ComputeMetricsTest(unittest.TestCase):
    def _txns(self):
        return [
            {"txn_date": "2026-01-05", "amount": 100000, "direction": "credit", "balance": 200000, "category": "collection"},
            {"txn_date": "2026-01-25", "amount": 30000, "direction": "debit", "balance": 170000, "category": "salary"},
            {"txn_date": "2026-01-28", "amount": 20000, "direction": "debit", "balance": 150000, "category": "vendor"},
            {"txn_date": "2026-02-05", "amount": 120000, "direction": "credit", "balance": 270000, "category": "collection"},
            {"txn_date": "2026-02-10", "amount": 5000, "direction": "debit", "balance": 265000, "category": "cheque_bounce"},
            {"txn_date": "2026-02-25", "amount": 30000, "direction": "debit", "balance": 235000, "category": "salary"},
        ]

    def test_empty(self):
        m = compute_metrics([])
        self.assertEqual(m["transaction_count"], 0)
        self.assertEqual(m["bank_health_score"], 0.0)

    def test_cash_flow_and_categories(self):
        m = compute_metrics(self._txns(), closing_balance=235000)
        self.assertEqual(m["transaction_count"], 6)
        self.assertEqual(m["cash_flow"]["total_inflow"], 220000)
        self.assertEqual(m["cash_flow"]["total_outflow"], 85000)
        self.assertEqual(m["cash_flow"]["net_cash_flow"], 135000)
        self.assertTrue(m["salary_detection"]["detected"])
        self.assertEqual(m["salary_detection"]["payouts"], 2)
        self.assertEqual(m["vendor_payments"]["count"], 1)
        self.assertEqual(m["cheque_bounce"]["count"], 1)

    def test_monthly_grouping(self):
        m = compute_metrics(self._txns())
        self.assertEqual(m["period_months"], 2)
        self.assertEqual(len(m["monthly_balance"]), 2)

    def test_health_score_bounds(self):
        m = compute_metrics(self._txns(), closing_balance=235000)
        self.assertGreaterEqual(m["bank_health_score"], 0)
        self.assertLessEqual(m["bank_health_score"], 100)

    def test_bounces_reduce_score(self):
        clean = [t for t in self._txns() if t["category"] != "cheque_bounce"]
        bouncy = self._txns() + [
            {"txn_date": "2026-02-11", "amount": 5000, "direction": "debit", "balance": 260000, "category": "cheque_bounce"},
            {"txn_date": "2026-02-12", "amount": 5000, "direction": "debit", "balance": 255000, "category": "cheque_bounce"},
        ]
        self.assertGreater(
            compute_metrics(clean, closing_balance=235000)["bank_health_score"],
            compute_metrics(bouncy, closing_balance=235000)["bank_health_score"],
        )


class AnalyzeStatementTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_configs(self.db)

    def tearDown(self):
        self.db.close()

    def test_analyze_statement_persists(self):
        stmt = aa_svc.import_statement(self.db, entity_ref="ENT2", account_ref="A1", months=6)
        metrics = analytics_svc.analyze_statement(self.db, stmt.id)
        self.assertIn("bank_health_score", metrics)
        from backend.app.models.integrations import StatementAnalytics
        rows = self.db.query(StatementAnalytics).filter(StatementAnalytics.statement_id == stmt.id).all()
        self.assertEqual(len(rows), 1)

    def test_analyze_entity_aggregates(self):
        aa_svc.import_statement(self.db, entity_ref="ENT3", account_ref="A1", months=6)
        aa_svc.import_statement(self.db, entity_ref="ENT3", account_ref="A2", months=6)
        metrics = analytics_svc.analyze_entity(self.db, "ENT3")
        self.assertGreater(metrics["transaction_count"], 0)

    def test_analyze_missing_statement(self):
        with self.assertRaises(ValueError):
            analytics_svc.analyze_statement(self.db, 99999)


if __name__ == "__main__":
    unittest.main()
