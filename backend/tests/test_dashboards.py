""" tests: dashboard aggregation endpoints."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import audit as audit_model  # noqa: F401
from backend.app.models import approval as approval_model  # noqa: F401
from backend.app.models import covenant as covenant_model  # noqa: F401
from backend.app.models import monitoring as monitoring_model  # noqa: F401
from backend.app.models import notification as notification_model  # noqa: F401
from backend.app.models import task as task_model  # noqa: F401
from backend.app.models import system_config as system_config_model  # noqa: F401
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models.application import Application  # noqa: F401
from backend.app.models.user import User
from backend.app.routes import dashboards as dashboard_routes
from backend.app.services import config as config_service, lifecycle
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class _Actor:
    def __init__(self, uid=1, email="a@x.com"):
        self.id = uid
        self.email = email


class DashboardApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
        config_service.sync_config(db)
        # Seed a few applications in various states.
        for name, status in [("Acme", "submitted"), ("Beta", "analyst_review"), ("Gamma", "approved")]:
            app = lifecycle.create_application(db, actor=_Actor(), company_name=name)
            app.status = status
            db.commit()
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
        app.include_router(dashboard_routes.router)

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

    def test_operations_dashboard(self):
        uid = self._user("rm@x.com", "relationship_manager")
        client = self._client(uid)
        body = client.get("/api/dashboards/operations").json()
        self.assertEqual(body["totals"]["applications"], 3)
        self.assertTrue(len(body["status_breakdown"]) >= 1)

    def test_admin_requires_users_manage(self):
        uid = self._user("analyst@x.com", "credit_analyst")
        client = self._client(uid)
        self.assertEqual(client.get("/api/dashboards/admin").status_code, 403)

    def test_admin_dashboard_for_admin(self):
        uid = self._user("admin@x.com", "administrator")
        client = self._client(uid)
        body = client.get("/api/dashboards/admin").json()
        self.assertGreaterEqual(body["totals"]["roles"], 8)

    def test_portfolio_dashboard(self):
        uid = self._user("mgr@x.com", "risk_manager")
        client = self._client(uid)
        body = client.get("/api/dashboards/portfolio").json()
        self.assertIn("by_status", body)
        self.assertEqual(body["totals"]["applications"], 3)

    def test_manager_and_compliance_and_monitoring(self):
        uid = self._user("mgr@x.com", "risk_manager")
        client = self._client(uid)
        self.assertEqual(client.get("/api/dashboards/manager").status_code, 200)
        self.assertEqual(client.get("/api/dashboards/monitoring").status_code, 200)
        # risk_manager lacks audit.view -> compliance denied
        self.assertEqual(client.get("/api/dashboards/compliance").status_code, 403)

    def test_analyst_dashboard_self(self):
        uid = self._user("analyst@x.com", "credit_analyst")
        client = self._client(uid)
        body = client.get("/api/dashboards/analyst").json()
        self.assertIn("totals", body)
        self.assertIn("my_open_tasks", body["totals"])


if __name__ == "__main__":
    unittest.main()
