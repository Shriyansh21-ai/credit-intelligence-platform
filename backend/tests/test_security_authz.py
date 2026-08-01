import unittest

from backend.app.services.security_compliance import authz


class AuthnAuditTest(unittest.TestCase):
    def test_authn_audit_structure(self):
        res = authz.authn_audit()
        self.assertIn("checks", res)
        self.assertIn("findings", res)
        self.assertGreater(res["total_checks"], 0)
        self.assertLessEqual(res["passed"], res["total_checks"])

    def test_authn_checks_cover_core_controls(self):
        controls = {c["control"] for c in authz.authn_audit()["checks"]}
        self.assertTrue(any("expiry" in c for c in controls))
        self.assertTrue(any("Password policy" in c for c in controls))
        self.assertTrue(any("lockout" in c.lower() for c in controls))
        self.assertTrue(any("MFA" in c for c in controls))

    def test_dev_secret_flagged(self):
        # The default dev profile ships an insecure SECRET_KEY; the audit must
        # surface it as a finding.
        res = authz.authn_audit()
        codes = [f["code"] for f in res["findings"]]
        self.assertTrue(any(c.startswith("AUTHN-SECRET") for c in codes))


class RbacAuditTest(unittest.TestCase):
    def test_no_dangling_grants(self):
        res = authz.rbac_audit()
        dangling = [f for f in res["findings"] if f["code"] == "RBAC-DANGLING"]
        self.assertEqual(dangling, [], f"dangling grants: {dangling}")

    def test_only_administrator_wildcard(self):
        res = authz.rbac_audit()
        self.assertEqual(res["wildcard_roles"], ["administrator"])

    def test_least_privilege_ok(self):
        res = authz.rbac_audit()
        self.assertTrue(res["least_privilege_ok"], res["findings"])

    def test_totals(self):
        res = authz.rbac_audit()
        self.assertGreater(res["total_permissions"], 100)
        self.assertGreater(res["total_roles"], 5)


class TenantIsolationTest(unittest.TestCase):
    def test_all_boundaries_enforced(self):
        res = authz.tenant_isolation_audit()
        self.assertEqual(res["enforced"], res["total_boundaries"])
        self.assertTrue(res["no_cross_tenant_leakage"])

    def test_covers_required_boundaries(self):
        res = authz.tenant_isolation_audit()
        names = {b["boundary"] for b in res["boundaries"]}
        for required in ("Row isolation", "Cache isolation", "AI memory isolation",
                         "RAG isolation", "ML isolation", "Audit logs", "Search",
                         "Knowledge graph"):
            self.assertIn(required, names)

    def test_score_high(self):
        res = authz.tenant_isolation_audit()
        self.assertGreaterEqual(res["score"], 90)


class AuthzAggregateTest(unittest.TestCase):
    def test_aggregate(self):
        res = authz.authz_audit()
        self.assertIn("authentication", res)
        self.assertIn("authorization", res)
        self.assertEqual(res["open_findings"], len(res["findings"]))
        self.assertGreaterEqual(res["score"], 0)
        self.assertLessEqual(res["score"], 100)


if __name__ == "__main__":
    unittest.main()
