""" tests: lifecycle state machine + service + API."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import approval as approval_model  # noqa: F401
from backend.app.models import audit as audit_model  # noqa: F401
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.application import Application
from backend.app.models.user import User
from backend.app.routes import applications as application_routes
from backend.app.services import lifecycle
from backend.app.services.lifecycle import state_machine as sm
from backend.app.services.lifecycle.state_machine import ApplicationStatus, InvalidTransition
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class StateMachineTest(unittest.TestCase):
    def test_valid_and_invalid_transitions(self):
        self.assertTrue(sm.can_transition(ApplicationStatus.DRAFT, ApplicationStatus.SUBMITTED))
        self.assertFalse(sm.can_transition(ApplicationStatus.DRAFT, ApplicationStatus.APPROVED))
        self.assertFalse(sm.can_transition(ApplicationStatus.CLOSED, ApplicationStatus.DRAFT))

    def test_validate_raises(self):
        with self.assertRaises(InvalidTransition):
            sm.validate_transition(ApplicationStatus.DRAFT, ApplicationStatus.APPROVED)
        with self.assertRaises(InvalidTransition):
            sm.validate_transition(ApplicationStatus.DRAFT, "nonsense")

    def test_terminal(self):
        self.assertTrue(sm.is_terminal(ApplicationStatus.CLOSED))
        self.assertFalse(sm.is_terminal(ApplicationStatus.DRAFT))

    def test_next_statuses(self):
        self.assertIn(ApplicationStatus.SUBMITTED, sm.next_statuses(ApplicationStatus.DRAFT))


class LifecycleServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _actor(self):
        class A:
            id = 1
            email = "a@x.com"
        return A()

    def test_create_records_history(self):
        db = self.Session()
        app = lifecycle.create_application(db, actor=self._actor(), company_name="Acme Ltd")
        self.assertEqual(app.status, ApplicationStatus.DRAFT)
        self.assertTrue(app.reference.startswith("APP-"))
        timeline = lifecycle.get_timeline(db, app)
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["to_status"], ApplicationStatus.DRAFT)
        db.close()

    def test_transition_and_history(self):
        db = self.Session()
        app = lifecycle.create_application(db, actor=self._actor(), company_name="Acme")
        lifecycle.transition(db, app, ApplicationStatus.SUBMITTED, actor=self._actor(), reason="go")
        self.assertEqual(app.status, ApplicationStatus.SUBMITTED)
        self.assertEqual(len(lifecycle.get_timeline(db, app)), 2)
        db.close()

    def test_invalid_transition_raises(self):
        db = self.Session()
        app = lifecycle.create_application(db, actor=self._actor(), company_name="Acme")
        with self.assertRaises(InvalidTransition):
            lifecycle.transition(db, app, ApplicationStatus.APPROVED, actor=self._actor())
        db.close()

    def test_rollback(self):
        db = self.Session()
        app = lifecycle.create_application(db, actor=self._actor(), company_name="Acme")
        lifecycle.transition(db, app, ApplicationStatus.SUBMITTED, actor=self._actor())
        lifecycle.rollback(db, app, actor=self._actor(), reason="undo")
        self.assertEqual(app.status, ApplicationStatus.DRAFT)
        db.close()


class ApplicationApiTest(unittest.TestCase):
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
        app.include_router(application_routes.router)

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

    def test_create_requires_permission(self):
        uid = self._user("viewer@x.com", "viewer")
        client = self._client(uid)
        resp = client.post("/api/applications", json={"company_name": "Acme"})
        self.assertEqual(resp.status_code, 403)

    def test_full_flow(self):
        uid = self._user("rm@x.com", "relationship_manager")
        client = self._client(uid)
        created = client.post(
            "/api/applications",
            json={"company_name": "Acme Ltd", "industry": "Manufacturing", "requested_amount": 5_000_000},
        )
        self.assertEqual(created.status_code, 201)
        app_id = created.json()["id"]

        submitted = client.post(f"/api/applications/{app_id}/submit")
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.json()["status"], "submitted")

        # Detail includes a timeline.
        detail = client.get(f"/api/applications/{app_id}").json()
        self.assertGreaterEqual(len(detail["timeline"]), 2)

    def test_illegal_transition_returns_409(self):
        # A risk_manager has applications.transition, so the request reaches the
        # state machine and is rejected for being an illegal move (not for perms).
        rm = self._user("rm@x.com", "relationship_manager")
        mgr = self._user("mgr@x.com", "risk_manager")
        create_client = self._client(rm)
        app_id = create_client.post("/api/applications", json={"company_name": "Acme"}).json()["id"]

        client = self._client(mgr)
        bad = client.post(f"/api/applications/{app_id}/transition", json={"to_status": "approved"})
        self.assertEqual(bad.status_code, 409)

    def test_statuses_catalog(self):
        uid = self._user("rm@x.com", "relationship_manager")
        client = self._client(uid)
        body = client.get("/api/applications/statuses").json()
        self.assertEqual(len(body["statuses"]), 14)

    def test_transition_needs_transition_permission(self):
        uid = self._user("rm@x.com", "relationship_manager")  # lacks applications.transition
        client = self._client(uid)
        created = client.post("/api/applications", json={"company_name": "Acme"})
        app_id = created.json()["id"]
        resp = client.post(f"/api/applications/{app_id}/transition", json={"to_status": "submitted"})
        self.assertEqual(resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()
