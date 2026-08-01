""" Integration Platform API tests (HTTP + RBAC)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.routes.integrations import ROUTERS
from backend.app.services.integrations.config import sync_connector_configs
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role
from backend.tests._integrations_helpers import fresh_session

GSTIN = "27ABCDE1234F1Z5"


class IntegrationsApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        sync_rbac(db)
        sync_connector_configs(db)
        db.close()

    def _user(self, email, role):
        db = self.Session()
        try:
            u = User(email=email, password="x")
            db.add(u)
            db.commit()
            db.refresh(u)
            assign_role(db, u, role)
            return u.id
        finally:
            db.close()

    def _client(self, uid):
        app = FastAPI()
        for r in ROUTERS:
            app.include_router(r)

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        def override_user():
            db = self.Session()
            try:
                return db.query(User).filter(User.id == uid).first()
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        return TestClient(app)

    # -- RBAC ----------------------------------------------------------
    def test_viewer_forbidden_from_manage(self):
        c = self._client(self._user("viewer@x", "viewer"))
        resp = c.post("/api/integrations/data/gst/import", json={"entity_ref": GSTIN, "operation": "get_profile"})
        self.assertEqual(resp.status_code, 403)

    def test_view_permission_can_list_connectors(self):
        c = self._client(self._user("analyst@x", "credit_analyst"))
        resp = c.get("/api/integrations/connectors")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(resp.json()["connectors"]), 6)

    # -- Data import ---------------------------------------------------
    def test_import_and_fetch_snapshot(self):
        c = self._client(self._user("rm@x", "risk_manager"))
        resp = c.post("/api/integrations/data/gst/import",
                      json={"entity_ref": GSTIN, "operation": "get_profile"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["snapshot"]["version"], 1)
        got = c.get(f"/api/integrations/data/gst/{GSTIN}?dataset=get_profile")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json()["payload"]["gstin"], GSTIN)

    def test_import_bundle(self):
        c = self._client(self._user("rm@x", "risk_manager"))
        resp = c.post("/api/integrations/data/bureau/import",
                      json={"entity_ref": "AAAAA1111A", "operations": ["get_business_score", "get_dpd_history"]})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(resp.json()["imported"]), 2)

    def test_unknown_snapshot_connector_404(self):
        c = self._client(self._user("rm@x", "risk_manager"))
        resp = c.post("/api/integrations/data/nope/import", json={"entity_ref": "x", "operation": "y"})
        self.assertEqual(resp.status_code, 404)

    # -- Connector mode switch -----------------------------------------
    def test_switch_mode(self):
        c = self._client(self._user("rm@x", "risk_manager"))
        resp = c.put("/api/integrations/connectors/gst/mode", json={"provider_mode": "sandbox"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["provider_mode"], "sandbox")

    # -- Account Aggregator flow ---------------------------------------
    def test_consent_and_statement_flow(self):
        c = self._client(self._user("rm@x", "risk_manager"))
        consent = c.post("/api/integrations/aa/consents", json={"entity_ref": "ENT1", "months": 6})
        self.assertEqual(consent.status_code, 200, consent.text)
        cid = consent.json()["id"]
        c.post(f"/api/integrations/aa/consents/{cid}/refresh")
        stmt = c.post("/api/integrations/aa/statements/import",
                      json={"entity_ref": "ENT1", "account_ref": "XXXX1", "months": 6})
        self.assertEqual(stmt.status_code, 200, stmt.text)
        sid = stmt.json()["id"]
        analysis = c.post(f"/api/integrations/aa/statements/{sid}/analyze")
        self.assertEqual(analysis.status_code, 200)
        self.assertIn("bank_health_score", analysis.json())

    # -- Collateral ----------------------------------------------------
    def test_collateral_crud(self):
        c = self._client(self._user("rm@x", "risk_manager"))
        resp = c.post("/api/collateral", json={
            "collateral_type": "real_estate", "description": "Plant",
            "market_value": 10000000, "loan_amount": 6000000, "entity_ref": "E1"})
        self.assertEqual(resp.status_code, 200, resp.text)
        cid = resp.json()["id"]
        self.assertAlmostEqual(resp.json()["coverage_ratio"], 1.25)
        reval = c.post(f"/api/collateral/{cid}/revalue", json={"market_value": 8000000})
        self.assertEqual(reval.status_code, 200)
        summary = c.get("/api/collateral/entities/E1")
        self.assertEqual(summary.json()["summary"]["item_count"], 1)

    def test_collateral_view_forbidden_for_manage(self):
        c = self._client(self._user("viewer@x", "viewer"))
        resp = c.post("/api/collateral", json={"collateral_type": "vehicle", "description": "x", "market_value": 1})
        self.assertEqual(resp.status_code, 403)

    # -- Sync ----------------------------------------------------------
    def test_run_sync(self):
        c = self._client(self._user("admin@x", "administrator"))
        resp = c.post("/api/integrations/sync/run", json={
            "sync_type": "full", "connectors": ["gst"], "entity_refs": [GSTIN]})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["status"], "completed")

    # -- Open API platform ---------------------------------------------
    def test_api_key_lifecycle(self):
        c = self._client(self._user("admin@x", "administrator"))
        created = c.post("/api/platform/keys", json={"name": "partner", "scopes": ["read"]})
        self.assertEqual(created.status_code, 200, created.text)
        self.assertIn("api_key", created.json())  # returned once
        kid = created.json()["id"]
        listed = c.get("/api/platform/keys")
        self.assertEqual(len(listed.json()["keys"]), 1)
        revoked = c.delete(f"/api/platform/keys/{kid}")
        self.assertEqual(revoked.status_code, 200)

    def test_webhook_emit(self):
        c = self._client(self._user("admin@x", "administrator"))
        sub = c.post("/api/platform/webhooks", json={"url": "https://x", "events": ["snapshot.created"]})
        self.assertEqual(sub.status_code, 200, sub.text)
        emit = c.post("/api/platform/webhooks/emit", json={"event": "snapshot.created", "payload": {"a": 1}})
        self.assertEqual(len(emit.json()["deliveries"]), 1)

    # -- Observability -------------------------------------------------
    def test_observability_overview(self):
        c = self._client(self._user("rm@x", "risk_manager"))
        c.post("/api/integrations/data/gst/import", json={"entity_ref": GSTIN, "operation": "get_profile"})
        resp = c.get("/api/integrations/observability/overview")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["connectors"]), 6)

    def test_observability_health(self):
        c = self._client(self._user("rm@x", "risk_manager"))
        resp = c.get("/api/integrations/observability/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["health"]), 6)

    # -- Customer 360 --------------------------------------------------
    def test_customer360_entity(self):
        c = self._client(self._user("rm@x", "risk_manager"))
        c.post("/api/integrations/data/gst/import", json={"entity_ref": GSTIN, "operation": "get_profile"})
        resp = c.get(f"/api/customer360/entities/{GSTIN}")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.json()["gst"])


if __name__ == "__main__":
    unittest.main()
