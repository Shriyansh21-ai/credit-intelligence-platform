import unittest

from backend.tests._autonomous_helpers import fresh_session, seed_assessment
from backend.app.services.autonomous import monitoring, ews, alerts


class MonitoringTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_financial_detector(self):
        sigs = monitoring.detect_financial({"current": {"revenue": 70}, "previous": {"revenue": 100}})
        self.assertTrue(any(s["signal_type"] == "revenue_deterioration" for s in sigs))
        self.assertEqual(sigs[0]["direction"], "negative")

    def test_financial_detector_ignores_small_change(self):
        sigs = monitoring.detect_financial({"current": {"revenue": 99}, "previous": {"revenue": 100}})
        self.assertEqual(sigs, [])

    def test_mca_auditor_critical(self):
        sigs = monitoring.detect_mca({"auditor_resigned": True})
        self.assertEqual(sigs[0]["severity"], "critical")

    def test_payment_detector(self):
        sigs = monitoring.detect_payment({"dpd": 60, "bounced_cheques": 1})
        types = {s["signal_type"] for s in sigs}
        self.assertIn("payment_delay", types)
        self.assertIn("cheque_bounce", types)

    def test_bureau_score_drop(self):
        sigs = monitoring.detect_bureau({"score": 600, "previous_score": 720})
        self.assertTrue(any(s["signal_type"] == "bureau_score_drop" for s in sigs))

    def test_run_monitoring_escalates(self):
        res = monitoring.run_monitoring(self.db, "Acme", {
            "financial": {"current": {"revenue": 50}, "previous": {"revenue": 100}},
            "mca": {"auditor_resigned": True}})
        self.assertGreaterEqual(res["signal_count"], 2)
        self.assertTrue(res["reassessment_recommended"])
        self.assertGreater(len(res["alerts"]), 0)
        self.assertIn(res["escalation"], ["credit_committee", "risk_manager", "senior_analyst", "monitor"])

    def test_run_monitoring_no_escalation_flag(self):
        res = monitoring.run_monitoring(self.db, "Acme", {"mca": {"auditor_resigned": True}},
                                        escalate=False)
        self.assertEqual(len(res["alerts"]), 0)

    def test_record_and_recent_signals(self):
        monitoring.record_signal(self.db, company_ref="Acme", source="news",
                                 signal_type="adverse_news", severity="high")
        recent = monitoring.recent_signals(self.db, company_ref="Acme")
        self.assertEqual(len(recent), 1)

    def test_sources_constant(self):
        self.assertIn("financial", monitoring.MONITORING_SOURCES)
        self.assertEqual(len(monitoring.MONITORING_SOURCES), 10)


class EWSTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_no_signals_green(self):
        seed_assessment(self.db, company_name="Healthy", probability_of_default=0.02,
                        liquidity_health=90, debt_health=90, working_capital_health=90)
        res = ews.evaluate(self.db, company_ref="Healthy")
        self.assertEqual(res["ews_band"], "green")
        self.assertEqual(res["signal_count"], 0)

    def test_auditor_resignation_signal(self):
        seed_assessment(self.db, company_name="Distress")
        res = ews.evaluate(self.db, company_ref="Distress",
                           context={"auditor_resigned": True})
        codes = {s["code"] for s in res["signals"]}
        self.assertIn("auditor_resignation", codes)
        self.assertGreater(res["ews_score"], 0)

    def test_multiple_signals_red_escalates(self):
        seed_assessment(self.db, company_name="Bad", liquidity_health=20, debt_health=20)
        res = ews.evaluate(self.db, company_ref="Bad", context={
            "auditor_resigned": True, "director_changes": 3, "tax_default": True,
            "covenant_breaches": ["dscr"], "customer_concentration": 0.8,
            "sector_index_change": -0.3})
        self.assertEqual(res["ews_band"], "red")
        # red band escalates into an alert
        open_alerts = alerts.list_alerts(self.db, category="ews")
        self.assertGreater(len(open_alerts), 0)

    def test_concentration_signals(self):
        seed_assessment(self.db, company_name="Conc")
        res = ews.evaluate(self.db, company_ref="Conc",
                           context={"supplier_concentration": 0.7, "customer_concentration": 0.5})
        codes = {s["code"] for s in res["signals"]}
        self.assertIn("supplier_concentration", codes)
        self.assertIn("customer_concentration", codes)

    def test_persist_and_history(self):
        seed_assessment(self.db, company_name="Hist")
        ews.evaluate(self.db, company_ref="Hist", context={"director_changes": 1})
        hist = ews.history(self.db, "Hist")
        self.assertEqual(len(hist), 1)

    def test_no_persist(self):
        seed_assessment(self.db, company_name="NoPersist")
        ews.evaluate(self.db, company_ref="NoPersist", context={"director_changes": 1}, persist=False)
        self.assertEqual(len(ews.history(self.db, "NoPersist")), 0)

    def test_signals_have_required_fields(self):
        seed_assessment(self.db, company_name="Fields")
        res = ews.evaluate(self.db, company_ref="Fields", context={"auditor_resigned": True})
        s = res["signals"][0]
        for key in ("code", "name", "severity", "confidence", "business_impact",
                    "recommended_action", "evidence"):
            self.assertIn(key, s)


class AlertsTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_dedup(self):
        a1 = alerts.raise_alert(self.db, company_ref="X", category="monitoring",
                                alert_type="t", title="t", dedup_key="k")
        a2 = alerts.raise_alert(self.db, company_ref="X", category="monitoring",
                                alert_type="t", title="t2", dedup_key="k")
        self.assertEqual(a1.id, a2.id)
        self.assertEqual(a2.title, "t2")

    def test_status_lifecycle(self):
        a = alerts.raise_alert(self.db, company_ref="X", category="ews", alert_type="t", title="t")
        alerts.set_status(self.db, a.id, "resolved")
        self.assertEqual(len(alerts.list_alerts(self.db, status="open")), 0)
        self.assertEqual(len(alerts.list_alerts(self.db, status="resolved")), 1)

    def test_invalid_status(self):
        a = alerts.raise_alert(self.db, company_ref="X", category="ews", alert_type="t", title="t")
        with self.assertRaises(ValueError):
            alerts.set_status(self.db, a.id, "bogus")

    def test_summary(self):
        alerts.raise_alert(self.db, company_ref="X", category="ews", alert_type="t",
                           title="t", severity="high")
        alerts.raise_alert(self.db, company_ref="Y", category="monitoring", alert_type="u",
                           title="u", severity="low")
        s = alerts.summary(self.db)
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["open"], 2)


if __name__ == "__main__":
    unittest.main()
