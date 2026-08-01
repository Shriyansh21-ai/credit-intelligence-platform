""" tests: DB-driven system configuration."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import audit as audit_model  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.system_config import SystemConfig  # noqa: F401
from backend.app.models.user import User
from backend.app.routes import config as config_routes
from backend.app.services import config as config_service
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class ConfigServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_sync_seeds_defaults(self):
        db = self.Session()
        config_service.sync_config(db)
        self.assertGreaterEqual(db.query(SystemConfig).count(), 8)
        db.close()

    def test_sync_idempotent(self):
        db = self.Session()
        config_service.sync_config(db)
        n = db.query(SystemConfig).count()
        config_service.sync_config(db)
        self.assertEqual(db.query(SystemConfig).count(), n)
        db.close()

    def test_get_falls_back_to_catalog(self):
        db = self.Session()
        # No sync yet -> comes from catalog defaults.
        limits = config_service.get_config(db, "loan_limits")
        self.assertIn("max", limits)
        db.close()

    def test_set_updates_and_preserves_on_resync(self):
        db = self.Session()
        config_service.sync_config(db)
        config_service.set_config(db, "loan_limits", {"min": 1, "max": 2})
        config_service.sync_config(db)  # must not overwrite the changed value
        self.assertEqual(config_service.get_config(db, "loan_limits"), {"min": 1, "max": 2})
        db.close()


class ConfigApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
        config_service.sync_config(db)
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
        app.include_router(config_routes.router)

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

    def test_view_requires_config_view(self):
        uid = self._user("analyst@x.com", "credit_analyst")  # no config.view
        client = self._client(uid)
        self.assertEqual(client.get("/api/config").status_code, 403)

    def test_compliance_officer_can_view(self):
        uid = self._user("co@x.com", "compliance_officer")  # config.view yes, manage no
        client = self._client(uid)
        self.assertEqual(client.get("/api/config").status_code, 200)
        # Cannot write.
        resp = client.put("/api/config/loan_limits", json={"value": {"min": 1, "max": 2}})
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_update(self):
        uid = self._user("admin@x.com", "administrator")
        client = self._client(uid)
        resp = client.put("/api/config/loan_limits", json={"value": {"min": 5, "max": 9}})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["value"], {"min": 5, "max": 9})


if __name__ == "__main__":
    unittest.main()
