import unittest

from backend.tests._autonomous_helpers import fresh_session, seed_assessment
from backend.app.services.autonomous import recommendations, workflow, alerts


class RecommendationsTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_strong_profile_approves(self):
        seed_assessment(self.db, company_name="Strong", probability_of_default=0.02,
                        risk_rating="AA", debt_health=80, liquidity_health=80)
        res = recommendations.recommend(self.db, company_ref="Strong")
        actions = {r["action"] for r in res["recommendations"]}
        self.assertIn("approve", actions)

    def test_weak_profile_rejects(self):
        seed_assessment(self.db, company_name="Weak", probability_of_default=0.25,
                        risk_rating="CCC")
        res = recommendations.recommend(self.db, company_ref="Weak")
        self.assertEqual(res["recommendations"][0]["action"], "reject")

    def test_manual_review_band(self):
        seed_assessment(self.db, company_name="Mid", probability_of_default=0.12, risk_rating="B")
        res = recommendations.recommend(self.db, company_ref="Mid")
        self.assertEqual(res["recommendations"][0]["action"], "manual_review")

    def test_collateral_on_weak_debt(self):
        seed_assessment(self.db, company_name="Lev", probability_of_default=0.05,
                        risk_rating="BBB", debt_health=30)
        res = recommendations.recommend(self.db, company_ref="Lev")
        self.assertTrue(any(r["action"] == "additional_collateral" for r in res["recommendations"]))

    def test_restructure_on_red_ews(self):
        seed_assessment(self.db, company_name="Red", probability_of_default=0.05, risk_rating="BBB")
        res = recommendations.recommend(self.db, company_ref="Red", context={"ews_band": "red"})
        self.assertTrue(any(r["action"] == "restructure" for r in res["recommendations"]))

    def test_every_rec_has_evidence(self):
        seed_assessment(self.db, company_name="Ev", probability_of_default=0.05, risk_rating="BBB")
        res = recommendations.recommend(self.db, company_ref="Ev")
        for r in res["recommendations"]:
            self.assertIn("confidence", r)
            self.assertIn("reason", r)
            self.assertIn("evidence", r)
            self.assertIn("supporting_metrics", r)

    def test_no_assessment_honest(self):
        res = recommendations.recommend(self.db, company_ref="Ghost")
        self.assertEqual(res["recommendations"], [])

    def test_persist_and_status(self):
        seed_assessment(self.db, company_name="P", probability_of_default=0.05, risk_rating="BBB")
        res = recommendations.recommend(self.db, company_ref="P", persist=True)
        stored = recommendations.list_recommendations(self.db, company_ref="P")
        self.assertGreater(len(stored), 0)
        recommendations.set_status(self.db, stored[0].id, "accepted")
        self.assertEqual(recommendations.list_recommendations(self.db, status="accepted")[0].id, stored[0].id)

    def test_invalid_status(self):
        seed_assessment(self.db, company_name="Q", probability_of_default=0.05, risk_rating="BBB")
        res = recommendations.recommend(self.db, company_ref="Q", persist=True)
        rid = recommendations.list_recommendations(self.db, company_ref="Q")[0].id
        with self.assertRaises(ValueError):
            recommendations.set_status(self.db, rid, "bogus")


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_plan_sets_monitoring_frequency(self):
        seed_assessment(self.db, company_name="Acme", probability_of_default=0.05, risk_rating="BBB")
        actions = workflow.plan(self.db, company_ref="Acme")
        self.assertTrue(any(a["action_type"] == "set_monitoring_frequency" for a in actions))

    def test_plan_manual_review_assigns_reviewer(self):
        seed_assessment(self.db, company_name="MR", probability_of_default=0.12, risk_rating="B")
        actions = workflow.plan(self.db, company_ref="MR")
        types = {a["action_type"] for a in actions}
        self.assertIn("assign_reviewer", types)
        self.assertIn("create_task", types)

    def test_plan_committee_on_open_critical_alert(self):
        seed_assessment(self.db, company_name="Crit", probability_of_default=0.05, risk_rating="BBB")
        alerts.raise_alert(self.db, company_ref="Crit", category="monitoring",
                           alert_type="t", title="t", severity="critical")
        actions = workflow.plan(self.db, company_ref="Crit")
        types = {a["action_type"] for a in actions}
        self.assertIn("recommend_committee_review", types)
        self.assertIn("trigger_reassessment", types)

    def test_run_proposed_persists(self):
        seed_assessment(self.db, company_name="Acme", probability_of_default=0.05, risk_rating="BBB")
        res = workflow.run(self.db, company_ref="Acme", mode="proposed")
        self.assertGreater(res["action_count"], 0)
        self.assertEqual(len(workflow.list_actions(self.db, company_ref="Acme")), res["action_count"])

    def test_run_execute_mode(self):
        seed_assessment(self.db, company_name="Exec", probability_of_default=0.12, risk_rating="B")
        res = workflow.run(self.db, company_ref="Exec", mode="execute", actor_user_id=1)
        self.assertEqual(res["mode"], "execute")
        # create_task action should be executed
        executed = [a for a in res["actions"] if a["status"] == "executed"]
        self.assertGreater(len(executed), 0)

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            workflow.run(self.db, company_ref="X", mode="bogus")

    def test_monitoring_frequency_bands(self):
        self.assertEqual(workflow._monitoring_frequency(0.2, "green"), "weekly")
        self.assertEqual(workflow._monitoring_frequency(0.09, "green"), "monthly")
        self.assertEqual(workflow._monitoring_frequency(0.01, "green"), "quarterly")


if __name__ == "__main__":
    unittest.main()
