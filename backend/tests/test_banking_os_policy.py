import unittest

from backend.tests._banking_os_helpers import (
    client_for, fresh_session, make_user, seed_rbac,
)
from backend.app.services.banking_os import policy


class PolicyEvaluatorTest(unittest.TestCase):
    """Pure, DB-free evaluation core."""

    def test_eval_condition_operators(self):
        d = {"pd": 0.3, "rating": "B", "sector": "textile", "flags": ["watchlist"]}
        self.assertTrue(policy.eval_condition({"field": "pd", "op": "gte", "value": 0.25}, d))
        self.assertFalse(policy.eval_condition({"field": "pd", "op": "lt", "value": 0.25}, d))
        self.assertTrue(policy.eval_condition({"field": "rating", "op": "in", "value": ["B", "CCC"]}, d))
        self.assertTrue(policy.eval_condition({"field": "sector", "op": "eq", "value": "textile"}, d))
        self.assertTrue(policy.eval_condition({"field": "flags", "op": "contains", "value": "watchlist"}, d))
        self.assertTrue(policy.eval_condition({"field": "pd", "op": "between", "value": [0.1, 0.4]}, d))
        self.assertTrue(policy.eval_condition({"field": "rating", "op": "exists"}, d))
        self.assertTrue(policy.eval_condition({"field": "missing", "op": "not_exists"}, d))
        self.assertTrue(policy.eval_condition({"field": "sector", "op": "starts_with", "value": "tex"}, d))

    def test_dotted_path_resolution(self):
        d = {"financials": {"ratios": {"current_ratio": 0.8}}}
        self.assertTrue(policy.eval_condition(
            {"field": "financials.ratios.current_ratio", "op": "lt", "value": 1.0}, d))

    def test_first_match_stops(self):
        rules = [
            {"id": "a", "when": [{"field": "pd", "op": "gte", "value": 0.2}],
             "then": {"decision": "reject"}, "priority": 100, "stop": True},
            {"id": "b", "when": [], "then": {"decision": "pass"}, "priority": 10},
        ]
        out = policy.evaluate_rules(rules, {"pd": 0.3}, combine="first_match")
        self.assertEqual(out["decision"], "reject")
        self.assertEqual(len(out["matched_rules"]), 1)

    def test_combine_all_worst_wins(self):
        rules = [
            {"id": "flag", "when": [], "then": {"decision": "flag"}, "priority": 5},
            {"id": "reject", "when": [{"field": "x", "op": "eq", "value": 1}],
             "then": {"decision": "reject"}, "priority": 1},
        ]
        out = policy.evaluate_rules(rules, {"x": 1}, combine="all")
        self.assertEqual(out["decision"], "reject")
        self.assertEqual(len(out["matched_rules"]), 2)

    def test_default_when_no_match(self):
        out = policy.evaluate_rules(
            [{"id": "a", "when": [{"field": "x", "op": "eq", "value": 9}], "then": {"decision": "reject"}}],
            {"x": 1}, default_decision="pass")
        self.assertEqual(out["decision"], "pass")
        self.assertEqual(out["matched_rules"], [])

    def test_validate_rules_catches_problems(self):
        problems = policy.validate_rules([
            {"when": [{"op": "eq"}], "then": {}},  # missing id, field, decision
        ])
        self.assertTrue(any("missing 'id'" in p for p in problems))
        self.assertTrue(any("field" in p for p in problems))
        self.assertTrue(any("decision" in p for p in problems))

    def test_validate_rules_duplicate_id(self):
        problems = policy.validate_rules([
            {"id": "a", "then": {"decision": "pass"}},
            {"id": "a", "then": {"decision": "pass"}},
        ])
        self.assertTrue(any("duplicate" in p for p in problems))


class PolicyServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _loan_policy(self, publish=True):
        p = policy.create_policy(self.db, key="loan-appetite", name="Loan Risk Appetite",
                                 domain="loan")
        rules = [
            {"id": "high-pd", "name": "Reject very high PD",
             "when": [{"field": "pd", "op": "gte", "value": 0.25}],
             "then": {"decision": "reject", "action": "decline", "message": "PD above appetite"},
             "priority": 100, "stop": True},
            {"id": "refer-mid", "name": "Refer mid PD",
             "when": [{"field": "pd", "op": "gte", "value": 0.1}],
             "then": {"decision": "refer", "action": "manual_review"}, "priority": 50, "stop": True},
        ]
        policy.add_version(self.db, p.id, rules=rules, publish=publish)
        return p

    def test_create_requires_valid_domain(self):
        with self.assertRaises(ValueError):
            policy.create_policy(self.db, key="x", name="X", domain="not-a-domain")

    def test_duplicate_key_rejected(self):
        policy.create_policy(self.db, key="dup", name="A", domain="loan")
        with self.assertRaises(ValueError):
            policy.create_policy(self.db, key="dup", name="B", domain="loan")

    def test_add_version_validates(self):
        p = policy.create_policy(self.db, key="v", name="V", domain="loan")
        with self.assertRaises(ValueError):
            policy.add_version(self.db, p.id, rules=[{"then": {}}])

    def test_versioning_increments(self):
        p = policy.create_policy(self.db, key="v", name="V", domain="loan")
        v1 = policy.add_version(self.db, p.id, rules=[{"id": "a", "then": {"decision": "pass"}}])
        v2 = policy.add_version(self.db, p.id, rules=[{"id": "b", "then": {"decision": "pass"}}])
        self.assertEqual(v1.version, 1)
        self.assertEqual(v2.version, 2)

    def test_publish_activates(self):
        p = self._loan_policy(publish=True)
        refreshed = policy.get_policy(self.db, policy_id=p.id)
        self.assertEqual(refreshed.status, "active")
        self.assertEqual(refreshed.current_version, 1)

    def test_evaluate_reject_and_refer(self):
        self._loan_policy()
        r1 = policy.evaluate(self.db, policy_key="loan-appetite", data={"pd": 0.3})
        self.assertEqual(r1["decision"], "reject")
        self.assertEqual(r1["confidence"], 1.0)
        self.assertTrue(r1["evidence"])
        r2 = policy.evaluate(self.db, policy_key="loan-appetite", data={"pd": 0.15})
        self.assertEqual(r2["decision"], "refer")
        r3 = policy.evaluate(self.db, policy_key="loan-appetite", data={"pd": 0.02})
        self.assertEqual(r3["decision"], "pass")

    def test_evaluate_unpublished_raises(self):
        policy.create_policy(self.db, key="draft-only", name="D", domain="loan")
        with self.assertRaises(ValueError):
            policy.evaluate(self.db, policy_key="draft-only", data={})

    def test_evaluation_history_persisted(self):
        self._loan_policy()
        policy.evaluate(self.db, policy_key="loan-appetite", data={"pd": 0.3}, subject_ref="Acme")
        hist = policy.evaluation_history(self.db, policy_key="loan-appetite")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0].subject_ref, "Acme")

    def test_evaluate_domain_aggregates_worst(self):
        self._loan_policy()
        p2 = policy.create_policy(self.db, key="loan-fraud", name="Fraud", domain="loan")
        policy.add_version(self.db, p2.id, rules=[
            {"id": "flag", "when": [{"field": "velocity", "op": "gt", "value": 5}],
             "then": {"decision": "flag"}}], publish=True)
        out = policy.evaluate_domain(self.db, domain="loan", data={"pd": 0.02, "velocity": 9})
        self.assertEqual(out["decision"], "flag")
        self.assertEqual(out["policy_count"], 2)

    def test_playground_dryrun(self):
        out = policy.playground(
            [{"id": "a", "when": [{"field": "kyc", "op": "eq", "value": False}],
              "then": {"decision": "reject"}}],
            {"kyc": False})
        self.assertTrue(out["valid"])
        self.assertEqual(out["decision"], "reject")

    def test_playground_invalid(self):
        out = policy.playground([{"then": {}}], {})
        self.assertFalse(out["valid"])


class PolicyApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.admin = make_user(self.Session, "admin@os.test", "administrator")
        self.analyst = make_user(self.Session, "analyst@os.test", "credit_analyst")
        self.viewer = make_user(self.Session, "viewer@os.test", "viewer")

    def test_full_lifecycle_over_api(self):
        c = client_for(self.Session, self.admin)
        r = c.post("/api/os/policy", json={"key": "aml-1", "name": "AML", "domain": "aml"})
        self.assertEqual(r.status_code, 200, r.text)
        pid = r.json()["id"]
        r = c.post(f"/api/os/policy/{pid}/versions", json={
            "rules": [{"id": "sanction", "when": [{"field": "sanctioned", "op": "eq", "value": True}],
                       "then": {"decision": "block", "message": "Sanctioned party"}}],
            "publish": True})
        self.assertEqual(r.status_code, 200, r.text)
        r = c.post("/api/os/policy/aml-1/evaluate", json={"data": {"sanctioned": True}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["decision"], "block")

    def test_domains_endpoint(self):
        c = client_for(self.Session, self.analyst)
        r = c.get("/api/os/policy/domains")
        self.assertEqual(r.status_code, 200)
        self.assertIn("loan", r.json()["domains"])

    def test_analyst_cannot_author(self):
        # credit_analyst can evaluate/view but not author (policy.manage)
        c = client_for(self.Session, self.analyst)
        r = c.post("/api/os/policy", json={"key": "x", "name": "X", "domain": "loan"})
        self.assertEqual(r.status_code, 403)

    def test_viewer_denied_without_permission(self):
        c = client_for(self.Session, self.viewer)
        r = c.get("/api/os/policy/domains")
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
