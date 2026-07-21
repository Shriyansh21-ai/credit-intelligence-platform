"""Phase 5, Milestone 2 tests: approval workflow + decisions + API."""

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
from backend.app.models.user import User
from backend.app.routes import applications as application_routes
from backend.app.routes import approvals as approval_routes
from backend.app.services import approvals, lifecycle
from backend.app.services.approvals.workflow import ensure_default_workflow
from backend.app.services.lifecycle.state_machine import ApplicationStatus
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class ApprovalTestBase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
        ensure_default_workflow(db)
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
        app.include_router(approval_routes.router)

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

    def _app_at(self, status):
        """Create an application and push it to a given lifecycle status."""
        db = self.Session()
        try:
            class A:
                id = 1
                email = "seed@x.com"
            app = lifecycle.create_application(db, actor=A(), company_name="Acme")
            # Walk it forward through legal transitions to reach `status`.
            path = {
                ApplicationStatus.ANALYST_REVIEW: [
                    ApplicationStatus.SUBMITTED,
                    ApplicationStatus.UNDER_AI_ANALYSIS,
                    ApplicationStatus.ANALYST_REVIEW,
                ],
                ApplicationStatus.SENIOR_ANALYST_REVIEW: [
                    ApplicationStatus.SUBMITTED,
                    ApplicationStatus.UNDER_AI_ANALYSIS,
                    ApplicationStatus.ANALYST_REVIEW,
                    ApplicationStatus.SENIOR_ANALYST_REVIEW,
                ],
                ApplicationStatus.CREDIT_COMMITTEE: [
                    ApplicationStatus.SUBMITTED,
                    ApplicationStatus.UNDER_AI_ANALYSIS,
                    ApplicationStatus.ANALYST_REVIEW,
                    ApplicationStatus.SENIOR_ANALYST_REVIEW,
                    ApplicationStatus.CREDIT_COMMITTEE,
                ],
            }[status]
            for target in path:
                lifecycle.transition(db, app, target, actor=A())
            return app.id
        finally:
            db.close()


class ApprovalServiceTest(ApprovalTestBase):
    def test_approve_advances_pipeline(self):
        app_id = self._app_at(ApplicationStatus.SENIOR_ANALYST_REVIEW)
        db = self.Session()
        app = db.query(Application).filter(Application.id == app_id).first()

        class Actor:
            id = 9
            email = "sa@x.com"

        result = approvals.submit_decision(
            db, app, action="approve", actor=Actor(), stage_key="senior_analyst"
        )
        self.assertTrue(result["status_changed"])
        self.assertEqual(app.status, ApplicationStatus.CREDIT_COMMITTEE)
        db.close()

    def test_reject_moves_to_rejected(self):
        app_id = self._app_at(ApplicationStatus.ANALYST_REVIEW)
        db = self.Session()
        app = db.query(Application).filter(Application.id == app_id).first()

        class Actor:
            id = 9
            email = "sa@x.com"

        result = approvals.submit_decision(db, app, action="reject", actor=Actor())
        self.assertTrue(result["status_changed"])
        self.assertEqual(app.status, ApplicationStatus.REJECTED)
        db.close()

    def test_comment_does_not_change_status(self):
        app_id = self._app_at(ApplicationStatus.ANALYST_REVIEW)
        db = self.Session()
        app = db.query(Application).filter(Application.id == app_id).first()

        class Actor:
            id = 9
            email = "x@x.com"

        result = approvals.submit_decision(db, app, action="comment", actor=Actor(), comment="looks ok")
        self.assertFalse(result["status_changed"])
        self.assertEqual(app.status, ApplicationStatus.ANALYST_REVIEW)
        db.close()

    def test_timeline(self):
        app_id = self._app_at(ApplicationStatus.SENIOR_ANALYST_REVIEW)
        db = self.Session()
        app = db.query(Application).filter(Application.id == app_id).first()

        class Actor:
            id = 9
            email = "x@x.com"

        approvals.submit_decision(db, app, action="hold", actor=Actor())
        approvals.submit_decision(db, app, action="approve", actor=Actor())
        timeline = approvals.get_approval_timeline(db, app)
        self.assertEqual(len(timeline), 2)
        db.close()


class ApprovalApiTest(ApprovalTestBase):
    def test_workflow_config(self):
        uid = self._user("sa@x.com", "senior_analyst")
        client = self._client(uid)
        body = client.get("/api/approvals/workflow").json()
        self.assertEqual(body["is_default"], True)
        self.assertTrue(len(body["stages"]) >= 4)

    def test_configure_requires_permission(self):
        uid = self._user("sa@x.com", "senior_analyst")  # lacks approvals.configure
        client = self._client(uid)
        resp = client.put("/api/approvals/workflow", json={"description": "x"})
        self.assertEqual(resp.status_code, 403)

    def test_decision_permission_enforced(self):
        app_id = self._app_at(ApplicationStatus.SENIOR_ANALYST_REVIEW)
        uid = self._user("analyst@x.com", "credit_analyst")  # cannot approve
        client = self._client(uid)
        resp = client.post(
            f"/api/approvals/applications/{app_id}/decisions",
            json={"action": "approve", "stage_key": "senior_analyst"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_senior_analyst_can_approve(self):
        app_id = self._app_at(ApplicationStatus.SENIOR_ANALYST_REVIEW)
        uid = self._user("sa@x.com", "senior_analyst")
        client = self._client(uid)
        resp = client.post(
            f"/api/approvals/applications/{app_id}/decisions",
            json={"action": "approve", "stage_key": "senior_analyst", "comment": "ok"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["status_changed"])

        timeline = client.get(f"/api/approvals/applications/{app_id}/decisions").json()
        self.assertEqual(len(timeline["timeline"]), 1)


if __name__ == "__main__":
    unittest.main()
