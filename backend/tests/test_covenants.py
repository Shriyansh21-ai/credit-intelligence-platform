""" tests: covenant tracking, breach alerts, trend, API."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import audit as audit_model  # noqa: F401
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.application import Application  # noqa: F401
from backend.app.models.covenant import Covenant, CovenantAlert
from backend.app.models.user import User
from backend.app.routes import covenants as covenant_routes
from backend.app.services import covenants
from backend.app.services.covenants.service import evaluate_covenant
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class CovenantEvalTest(unittest.TestCase):
    def test_min_operator(self):
        self.assertEqual(evaluate_covenant("min", 1.25, 1.5)["status"], "ok")
        self.assertEqual(evaluate_covenant("min", 1.25, 1.0)["status"], "breach")
        self.assertEqual(evaluate_covenant("min", 1.25, 1.26)["status"], "warning")
        self.assertEqual(evaluate_covenant("min", 1.25, None)["status"], "unknown")

    def test_max_operator(self):
        self.assertEqual(evaluate_covenant("max", 0.6, 0.4)["status"], "ok")
        self.assertEqual(evaluate_covenant("max", 0.6, 0.8)["status"], "breach")
        self.assertEqual(evaluate_covenant("max", 0.6, 0.59)["status"], "warning")


class CovenantServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_breach_creates_alert(self):
        db = self.Session()
        cov = covenants.create_covenant(db, application_id=1, metric_key="dscr", threshold=1.25)
        result = covenants.record_measurement(db, cov, value=1.0, period="Q1")
        self.assertEqual(result["measurement"]["status"], "breach")
        self.assertIsNotNone(result["alert"])
        self.assertEqual(db.query(CovenantAlert).count(), 1)
        db.close()

    def test_no_alert_when_compliant(self):
        db = self.Session()
        cov = covenants.create_covenant(db, application_id=1, metric_key="dscr", threshold=1.25)
        result = covenants.record_measurement(db, cov, value=1.8)
        self.assertEqual(result["measurement"]["status"], "ok")
        self.assertIsNone(result["alert"])
        db.close()

    def test_trend_direction(self):
        db = self.Session()
        cov = covenants.create_covenant(db, application_id=1, metric_key="dscr", threshold=1.25)
        for v in (1.2, 1.4, 1.6):
            covenants.record_measurement(db, cov, value=v)
        trend = covenants.covenant_trend(db, cov)
        self.assertEqual(trend["direction"], "improving")
        self.assertEqual(len(trend["points"]), 3)
        db.close()


class CovenantApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
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
        app.include_router(covenant_routes.router)

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

    def test_create_requires_manage(self):
        uid = self._user("viewer@x.com", "viewer")
        client = self._client(uid)
        resp = client.post("/api/covenants/applications/1", json={"metric_key": "dscr", "threshold": 1.25})
        self.assertEqual(resp.status_code, 403)

    def test_flow_with_breach(self):
        uid = self._user("rm@x.com", "risk_manager")
        client = self._client(uid)
        created = client.post(
            "/api/covenants/applications/1",
            json={"metric_key": "dscr", "threshold": 1.25},
        )
        self.assertEqual(created.status_code, 201)
        cov_id = created.json()["id"]

        m = client.post(f"/api/covenants/{cov_id}/measurements", json={"value": 1.0})
        self.assertEqual(m.json()["measurement"]["status"], "breach")

        alerts = client.get("/api/covenants/applications/1/alerts").json()["alerts"]
        self.assertEqual(len(alerts), 1)

        # Covenant listing reflects current value/status.
        listed = client.get("/api/covenants/applications/1").json()["covenants"]
        self.assertEqual(listed[0]["current_status"], "breach")

    def test_metrics_catalog(self):
        uid = self._user("rm@x.com", "risk_manager")
        client = self._client(uid)
        metrics = client.get("/api/covenants/metrics").json()["metrics"]
        self.assertTrue(any(m["key"] == "dscr" for m in metrics))


if __name__ == "__main__":
    unittest.main()
