""" tests: post-disbursement monitoring + deterioration."""

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
from backend.app.models.monitoring import MonitoringAlert
from backend.app.models.user import User
from backend.app.routes import monitoring as monitoring_routes
from backend.app.services import monitoring
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class MonitoringServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_health_drop_alerts(self):
        db = self.Session()
        monitoring.add_record(db, application_id=1, record_type="quarterly_statement", health_score=80)
        result = monitoring.add_record(
            db, application_id=1, record_type="quarterly_statement", health_score=60
        )
        cats = [a["category"] for a in result["alerts"]]
        self.assertIn("deterioration", cats)
        db.close()

    def test_rating_downgrade_alerts(self):
        db = self.Session()
        monitoring.add_record(db, application_id=1, record_type="rating_change", risk_rating="A")
        result = monitoring.add_record(db, application_id=1, record_type="rating_change", risk_rating="BB")
        self.assertIn("rating_downgrade", [a["category"] for a in result["alerts"]])
        db.close()

    def test_payment_default_alerts(self):
        db = self.Session()
        result = monitoring.add_record(
            db, application_id=1, record_type="payment_behaviour", payment_status="default"
        )
        self.assertIn("payment_delay", [a["category"] for a in result["alerts"]])
        db.close()

    def test_no_alert_when_stable(self):
        db = self.Session()
        monitoring.add_record(db, application_id=1, record_type="quarterly_statement", health_score=80)
        result = monitoring.add_record(
            db, application_id=1, record_type="quarterly_statement", health_score=79
        )
        self.assertEqual(result["alerts"], [])
        db.close()

    def test_risk_trend(self):
        db = self.Session()
        for score in (70, 65, 60):
            monitoring.add_record(db, application_id=1, record_type="quarterly_statement", health_score=score)
        trend = monitoring.risk_trend(db, 1)
        self.assertEqual(trend["direction"], "deteriorating")
        db.close()


class MonitoringApiTest(unittest.TestCase):
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
        app.include_router(monitoring_routes.router)

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

    def test_add_requires_manage(self):
        uid = self._user("viewer@x.com", "viewer")
        client = self._client(uid)
        resp = client.post(
            "/api/monitoring/applications/1/records",
            json={"record_type": "gst"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_full_flow(self):
        uid = self._user("rm@x.com", "risk_manager")
        client = self._client(uid)
        client.post(
            "/api/monitoring/applications/1/records",
            json={"record_type": "quarterly_statement", "health_score": 80, "period": "Q1"},
        )
        second = client.post(
            "/api/monitoring/applications/1/records",
            json={"record_type": "quarterly_statement", "health_score": 55, "period": "Q2"},
        )
        self.assertTrue(len(second.json()["alerts"]) >= 1)

        health = client.get("/api/monitoring/applications/1/health").json()
        self.assertEqual(len(health["timeline"]), 2)

        trend = client.get("/api/monitoring/applications/1/trend").json()
        self.assertEqual(trend["direction"], "deteriorating")

        alerts = client.get("/api/monitoring/applications/1/alerts").json()["alerts"]
        self.assertTrue(len(alerts) >= 1)


if __name__ == "__main__":
    unittest.main()
