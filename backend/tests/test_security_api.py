"""API + DB integration tests for the Stage 4 Security & Compliance routers.

Exercises auth/RBAC enforcement, scan persistence, findings triage, the risk
register, the privacy (DSAR) queue, the dashboard and tenant isolation.
"""

import unittest

from backend.tests._security_helpers import client_for, setup_env


class SecurityApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Session, cls.ids = setup_env(
            "administrator", "risk_manager", "compliance_officer", "auditor", "viewer")

    def admin(self):
        return client_for(self.Session, self.ids["administrator"])

    # -- read surfaces ------------------------------------------------------
    def test_posture(self):
        r = self.admin().get("/api/sec/posture")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("overall_score", body)
        self.assertIn("dimensions", body)

    def test_threat_endpoints(self):
        c = self.admin()
        for path in ("/api/sec/threat", "/api/sec/threat/stride",
                     "/api/sec/threat/attack-surface", "/api/sec/threat/attack-trees",
                     "/api/sec/threat/boundaries"):
            self.assertEqual(c.get(path).status_code, 200, path)

    def test_owasp_endpoints(self):
        c = self.admin()
        for path in ("/api/sec/owasp", "/api/sec/owasp/top10",
                     "/api/sec/owasp/api-top10", "/api/sec/owasp/asvs"):
            self.assertEqual(c.get(path).status_code, 200, path)

    def test_authz_and_tenant(self):
        c = self.admin()
        self.assertEqual(c.get("/api/sec/authz").status_code, 200)
        self.assertEqual(c.get("/api/sec/authz/tenant-isolation").status_code, 200)

    def test_secrets_data_supply_container(self):
        c = self.admin()
        for path in ("/api/sec/secrets", "/api/sec/data", "/api/sec/data/pii-catalog",
                     "/api/sec/supply-chain", "/api/sec/supply-chain/sbom",
                     "/api/sec/supply-chain/dependencies", "/api/sec/supply-chain/licenses",
                     "/api/sec/container", "/api/sec/ai/security", "/api/sec/ai/ml-security"):
            self.assertEqual(c.get(path).status_code, 200, path)

    def test_compliance_endpoints(self):
        c = self.admin()
        self.assertEqual(c.get("/api/sec/compliance/matrix").status_code, 200)
        self.assertEqual(c.get("/api/sec/compliance/gap-analysis").status_code, 200)
        self.assertEqual(c.get("/api/sec/compliance/readiness").status_code, 200)
        self.assertEqual(c.get("/api/sec/compliance/framework/soc2").status_code, 200)
        self.assertEqual(c.get("/api/sec/compliance/framework/nope").status_code, 404)

    # -- scans + findings ---------------------------------------------------
    def test_run_scan_persists_findings(self):
        c = self.admin()
        r = c.post("/api/sec/scans", json={"scan_type": "owasp"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("scan", body)
        self.assertGreaterEqual(body["findings_count"], 0)
        scan_id = body["scan"]["id"]
        # fetch it back
        got = c.get(f"/api/sec/scans/{scan_id}")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json()["scan"]["id"], scan_id)

    def test_full_scan(self):
        c = self.admin()
        r = c.post("/api/sec/scans", json={"scan_type": "full"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["scan"]["scan_type"], "full")

    def test_invalid_scan_type(self):
        r = self.admin().post("/api/sec/scans", json={"scan_type": "bogus"})
        self.assertEqual(r.status_code, 400)

    def test_findings_lifecycle(self):
        c = self.admin()
        c.post("/api/sec/scans", json={"scan_type": "owasp"})
        listing = c.get("/api/sec/findings").json()["findings"]
        self.assertTrue(listing)
        fid = listing[0]["id"]
        upd = c.patch(f"/api/sec/findings/{fid}", json={"status": "resolved"})
        self.assertEqual(upd.status_code, 200)
        self.assertEqual(upd.json()["status"], "resolved")

    def test_finding_invalid_status(self):
        c = self.admin()
        c.post("/api/sec/scans", json={"scan_type": "owasp"})
        fid = c.get("/api/sec/findings").json()["findings"][0]["id"]
        r = c.patch(f"/api/sec/findings/{fid}", json={"status": "banana"})
        self.assertEqual(r.status_code, 400)

    def test_finding_not_found(self):
        r = self.admin().patch("/api/sec/findings/999999", json={"status": "resolved"})
        self.assertEqual(r.status_code, 404)

    # -- compliance assessment ---------------------------------------------
    def test_record_compliance(self):
        c = self.admin()
        r = c.post("/api/sec/compliance/assess", json={"framework": "gdpr"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["framework"], "gdpr")
        hist = c.get("/api/sec/compliance/assessments").json()["assessments"]
        self.assertTrue(any(a["framework"] == "gdpr" for a in hist))

    # -- risk register ------------------------------------------------------
    def test_risk_crud(self):
        c = self.admin()
        r = c.post("/api/sec/risk", json={
            "title": "Prompt injection", "category": "elevation_of_privilege",
            "likelihood": 4, "impact": 5})
        self.assertEqual(r.status_code, 200)
        risk = r.json()
        self.assertEqual(risk["inherent_score"], 20)
        self.assertEqual(risk["inherent_level"], "critical")
        rid = risk["id"]
        upd = c.patch(f"/api/sec/risk/{rid}", json={"status": "mitigating", "likelihood": 2})
        self.assertEqual(upd.status_code, 200)
        self.assertEqual(upd.json()["status"], "mitigating")
        self.assertEqual(upd.json()["inherent_score"], 10)

    def test_risk_invalid_treatment(self):
        r = self.admin().post("/api/sec/risk", json={
            "title": "x", "category": "y", "likelihood": 2, "impact": 2,
            "treatment": "ignore"})
        self.assertEqual(r.status_code, 400)

    # -- privacy ------------------------------------------------------------
    def test_privacy_request_lifecycle(self):
        c = self.admin()
        r = c.post("/api/sec/privacy/requests", json={
            "subject_ref": "subject-123", "request_type": "erasure"})
        self.assertEqual(r.status_code, 200)
        pid = r.json()["id"]
        self.assertIsNotNone(r.json()["due_at"])
        upd = c.patch(f"/api/sec/privacy/requests/{pid}", json={"status": "completed"})
        self.assertEqual(upd.status_code, 200)
        self.assertIsNotNone(upd.json()["completed_at"])

    def test_privacy_invalid_type(self):
        r = self.admin().post("/api/sec/privacy/requests", json={
            "subject_ref": "s", "request_type": "teleport"})
        self.assertEqual(r.status_code, 400)

    # -- dashboard ----------------------------------------------------------
    def test_dashboard(self):
        c = self.admin()
        r = c.get("/api/sec/posture/dashboard")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        for key in ("posture", "findings", "risk_register", "compliance",
                    "privacy", "secrets", "recent_scans", "sessions"):
            self.assertIn(key, body)

    def test_snapshot(self):
        c = self.admin()
        r = c.post("/api/sec/posture/snapshot")
        self.assertEqual(r.status_code, 200)
        self.assertIn("overall_score", r.json())
        snaps = c.get("/api/sec/posture/snapshots").json()["snapshots"]
        self.assertTrue(snaps)


class SecurityRbacEnforcementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Session, cls.ids = setup_env(
            "administrator", "risk_manager", "compliance_officer", "auditor", "viewer")

    def test_viewer_denied_dashboard(self):
        c = client_for(self.Session, self.ids["viewer"])
        self.assertEqual(c.get("/api/sec/posture/dashboard").status_code, 403)

    def test_auditor_can_view_but_not_manage(self):
        c = client_for(self.Session, self.ids["auditor"])
        self.assertEqual(c.get("/api/sec/posture").status_code, 200)
        self.assertEqual(c.get("/api/sec/compliance/matrix").status_code, 200)
        # auditor cannot run scans (needs sec.findings.manage)
        self.assertEqual(c.post("/api/sec/scans", json={"scan_type": "owasp"}).status_code, 403)
        # auditor cannot record compliance
        self.assertEqual(
            c.post("/api/sec/compliance/assess", json={"framework": "soc2"}).status_code, 403)

    def test_risk_manager_can_manage_findings_and_risk(self):
        c = client_for(self.Session, self.ids["risk_manager"])
        self.assertEqual(c.post("/api/sec/scans", json={"scan_type": "owasp"}).status_code, 200)
        self.assertEqual(c.post("/api/sec/risk", json={
            "title": "r", "category": "c", "likelihood": 3, "impact": 3}).status_code, 200)

    def test_compliance_officer_can_run_compliance_and_privacy(self):
        c = client_for(self.Session, self.ids["compliance_officer"])
        self.assertEqual(
            c.post("/api/sec/compliance/assess", json={"framework": "pci_dss"}).status_code, 200)
        self.assertEqual(c.post("/api/sec/privacy/requests", json={
            "subject_ref": "s1", "request_type": "access"}).status_code, 200)

    def test_compliance_officer_cannot_manage_risk(self):
        c = client_for(self.Session, self.ids["compliance_officer"])
        # compliance_officer is not granted sec.risk.manage
        self.assertEqual(c.post("/api/sec/risk", json={
            "title": "r", "category": "c", "likelihood": 3, "impact": 3}).status_code, 403)


class SecurityTenantIsolationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Session, cls.ids = setup_env("administrator")

    def test_scans_scoped_by_tenant(self):
        c = client_for(self.Session, self.ids["administrator"])
        # create a scan under tenant 1 and tenant 2
        c.post("/api/sec/scans", json={"scan_type": "owasp", "tenant_id": 1})
        c.post("/api/sec/scans", json={"scan_type": "container", "tenant_id": 2})
        # Direct service query scoped to tenant 1 must not see tenant 2 rows.
        from backend.app.services.security_compliance import service as svc
        db = self.Session()
        try:
            t1 = svc.list_scans(db, tenant_id=1)
            t2 = svc.list_scans(db, tenant_id=2)
        finally:
            db.close()
        self.assertTrue(all(s["tenant_id"] == 1 for s in t1))
        self.assertTrue(all(s["tenant_id"] == 2 for s in t2))
        self.assertTrue(t1 and t2)

    def test_risk_scoped_by_tenant(self):
        c = client_for(self.Session, self.ids["administrator"])
        c.post("/api/sec/risk", json={"title": "a", "category": "x",
                                      "likelihood": 2, "impact": 2, "tenant_id": 10})
        c.post("/api/sec/risk", json={"title": "b", "category": "x",
                                      "likelihood": 2, "impact": 2, "tenant_id": 20})
        from backend.app.services.security_compliance import service as svc
        db = self.Session()
        try:
            t10 = svc.list_risks(db, tenant_id=10)
            t20 = svc.list_risks(db, tenant_id=20)
        finally:
            db.close()
        self.assertTrue(all(r["tenant_id"] == 10 for r in t10))
        self.assertTrue(all(r["tenant_id"] == 20 for r in t20))
        self.assertEqual({r["title"] for r in t10}, {"a"})
        self.assertEqual({r["title"] for r in t20}, {"b"})


if __name__ == "__main__":
    unittest.main()
