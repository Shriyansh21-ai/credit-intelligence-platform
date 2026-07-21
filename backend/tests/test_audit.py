"""Phase 5, Milestone 4 tests: audit recording and searchable dashboard."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.audit import AuditLog  # noqa: F401
from backend.app.models.user import User
from backend.app.routes import audit as audit_routes
from backend.app.services import audit
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class AuditTestBase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
        db.close()

    def _make_user(self, email, role):
        db = self.Session()
        try:
            user = User(email=email, password="x")
            db.add(user)
            db.commit()
            db.refresh(user)
            assign_role(db, user, role)
            return user.id
        finally:
            db.close()

    def _client(self, user_id):
        app = FastAPI()
        app.include_router(audit_routes.router)

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        def override_user():
            db = self.Session()
            try:
                return db.query(User).filter(User.id == user_id).first()
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        return TestClient(app)


class AuditRecorderTest(AuditTestBase):
    def test_record_persists(self):
        db = self.Session()
        entry = audit.record(
            db,
            action="application.transition",
            entity_type="application",
            entity_id=5,
            previous_value={"status": "draft"},
            new_value={"status": "submitted"},
            reason="Kickoff",
        )
        self.assertIsNotNone(entry.id)
        self.assertEqual(db.query(AuditLog).count(), 1)
        db.close()

    def test_record_safe_never_raises(self):
        db = self.Session()
        # Pass a non-serialisable actor-ish value; should not raise.
        result = audit.record_safe(db, action="x.y", new_value=object())
        self.assertIsNotNone(result)
        db.close()

    def test_search_filters_and_paginates(self):
        db = self.Session()
        for i in range(30):
            audit.record(db, action="api.request", entity_type="loan", entity_id=i)
        audit.record(db, action="auth.login", status="failure", reason="Bad password")
        db.close()

        db = self.Session()
        page1 = audit.search_audit(db, page=1, page_size=10)
        self.assertEqual(page1["total"], 31)
        self.assertEqual(len(page1["items"]), 10)
        self.assertEqual(page1["pages"], 4)

        failures = audit.search_audit(db, status="failure")
        self.assertEqual(failures["total"], 1)

        logins = audit.search_audit(db, action="auth")
        self.assertEqual(logins["total"], 1)
        db.close()


class AuditApiTest(AuditTestBase):
    def _seed(self):
        db = self.Session()
        audit.record(db, action="auth.login", entity_type="user", entity_id=1)
        audit.record(db, action="application.create", entity_type="application", entity_id=1)
        db.close()

    def test_dashboard_requires_permission(self):
        uid = self._make_user("rm@x.com", "relationship_manager")
        client = self._client(uid)
        self.assertEqual(client.get("/api/audit").status_code, 403)

    def test_auditor_can_read(self):
        self._seed()
        uid = self._make_user("auditor@x.com", "auditor")
        client = self._client(uid)
        resp = client.get("/api/audit")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["total"], 2)

    def test_stats_and_actions(self):
        self._seed()
        uid = self._make_user("auditor@x.com", "auditor")
        client = self._client(uid)
        stats = client.get("/api/audit/stats").json()
        self.assertIn("total", stats)
        actions = client.get("/api/audit/actions").json()["actions"]
        self.assertIn("auth.login", actions)


if __name__ == "__main__":
    unittest.main()
