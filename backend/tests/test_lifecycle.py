""" tests: lifecycle state machine + service + API."""

import unittest

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_tenant_id, get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import approval as approval_model  # noqa: F401
from backend.app.models import audit as audit_model  # noqa: F401
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.application import Application
from backend.app.models.application import ApplicationStatusHistory
from backend.app.models.tenancy import Organization, Tenant, TenantMembership
from backend.app.models.user import User
from backend.app.routes import applications as application_routes
from backend.app.services import lifecycle
from backend.app.services.lifecycle import state_machine as sm
from backend.app.services.lifecycle.state_machine import ApplicationStatus, InvalidTransition
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role
from backend.tests.tenant_test_utils import ensure_test_membership


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
        db = self.Session()
        self.tenant_id = ensure_test_membership(db, 1, "a@x.com")
        db.close()

    def _actor(self):
        class A:
            id = 1
            email = "a@x.com"
        return A()

    def test_create_records_history(self):
        db = self.Session()
        app = lifecycle.create_application(
            db, actor=self._actor(), tenant_id=self.tenant_id, company_name="Acme Ltd"
        )
        self.assertEqual(app.status, ApplicationStatus.DRAFT)
        self.assertTrue(app.reference.startswith("APP-"))
        timeline = lifecycle.get_timeline(db, app, tenant_id=self.tenant_id)
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["to_status"], ApplicationStatus.DRAFT)
        db.close()

    def test_transition_and_history(self):
        db = self.Session()
        app = lifecycle.create_application(
            db, actor=self._actor(), tenant_id=self.tenant_id, company_name="Acme"
        )
        lifecycle.transition(db, app, ApplicationStatus.SUBMITTED, actor=self._actor(), reason="go")
        self.assertEqual(app.status, ApplicationStatus.SUBMITTED)
        self.assertEqual(len(lifecycle.get_timeline(db, app, tenant_id=self.tenant_id)), 2)
        db.close()

    def test_invalid_transition_raises(self):
        db = self.Session()
        app = lifecycle.create_application(
            db, actor=self._actor(), tenant_id=self.tenant_id, company_name="Acme"
        )
        with self.assertRaises(InvalidTransition):
            lifecycle.transition(db, app, ApplicationStatus.APPROVED, actor=self._actor())
        db.close()

    def test_rollback(self):
        db = self.Session()
        app = lifecycle.create_application(
            db, actor=self._actor(), tenant_id=self.tenant_id, company_name="Acme"
        )
        lifecycle.transition(db, app, ApplicationStatus.SUBMITTED, actor=self._actor())
        lifecycle.rollback(db, app, actor=self._actor(), reason="undo")
        self.assertEqual(app.status, ApplicationStatus.DRAFT)
        db.close()

    def test_creation_rejects_another_tenant(self):
        db = self.Session()
        other_tenant_id = ensure_test_membership(db, 2, "other@x.com")
        with self.assertRaises(PermissionError):
            lifecycle.create_application(
                db,
                actor=self._actor(),
                tenant_id=other_tenant_id,
                company_name="Wrong tenant",
            )
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

    def test_cross_tenant_reads_and_lifecycle_mutations_are_hidden(self):
        owner_id = self._user("owner@x.com", "relationship_manager")
        owner = self._client(owner_id)
        created = owner.post("/api/applications", json={"company_name": "Tenant A"})
        self.assertEqual(created.status_code, 201)
        application_id = created.json()["id"]

        other_id = self._user("other@x.com", "administrator")
        other = self._client(other_id)
        self.assertEqual(other.get(f"/api/applications/{application_id}").status_code, 404)
        listed = other.get("/api/applications").json()
        self.assertEqual(listed["items"], [])
        self.assertEqual(listed["total"], 0)
        self.assertEqual(
            other.get(f"/api/applications/{application_id}/history").status_code,
            404,
        )
        self.assertEqual(
            other.patch(
                f"/api/applications/{application_id}",
                json={"company_name": "Changed"},
            ).status_code,
            404,
        )
        self.assertEqual(
            other.post(f"/api/applications/{application_id}/submit").status_code,
            404,
        )
        self.assertEqual(
            other.post(
                f"/api/applications/{application_id}/transition",
                json={"to_status": "submitted"},
            ).status_code,
            404,
        )
        self.assertEqual(
            other.post(
                f"/api/applications/{application_id}/rollback",
                json={"reason": "unauthorized"},
            ).status_code,
            404,
        )
        self.assertEqual(
            other.post(
                f"/api/applications/{application_id}/cancel",
                json={"reason": "unauthorized"},
            ).status_code,
            404,
        )

        db = self.Session()
        app = db.query(Application).filter(Application.id == application_id).one()
        self.assertEqual(app.company_name, "Tenant A")
        self.assertEqual(app.status, "draft")
        self.assertEqual(
            db.query(ApplicationStatusHistory)
            .filter(ApplicationStatusHistory.application_id == application_id)
            .count(),
            1,
        )
        db.close()

    def test_client_tenant_id_cannot_override_server_membership(self):
        owner_id = self._user("owner@x.com", "relationship_manager")
        other_id = self._user("other@x.com", "relationship_manager")
        other = self._client(other_id)
        self.assertEqual(other.get("/api/applications").status_code, 200)
        db = self.Session()
        other_tenant_id = (
            db.query(TenantMembership)
            .filter(TenantMembership.user_id == other_id)
            .one()
            .tenant_id
        )
        db.close()

        response = self._client(owner_id).post(
            "/api/applications",
            json={"company_name": "Owned by caller", "tenant_id": other_tenant_id},
        )
        self.assertEqual(response.status_code, 201)
        db = self.Session()
        created = db.query(Application).filter(Application.id == response.json()["id"]).one()
        self.assertNotEqual(created.tenant_id, other_tenant_id)
        self.assertEqual(created.user_id, owner_id)
        db.close()

    def test_missing_tenant_context_fails_closed(self):
        user_id = self._user("no-tenant@x.com", "relationship_manager")
        client = self._client(user_id)

        def missing_tenant():
            raise HTTPException(status_code=409, detail="Could not resolve tenant for user")

        client.app.dependency_overrides[get_current_tenant_id] = missing_tenant
        response = client.post("/api/applications", json={"company_name": "No tenant"})
        self.assertEqual(response.status_code, 409)

    def test_unassigned_legacy_application_is_not_listed_or_retrievable(self):
        user_id = self._user("legacy@x.com", "relationship_manager")
        client = self._client(user_id)
        client.get("/api/applications")

        db = self.Session()
        application = Application(
            user_id=user_id,
            tenant_id=None,
            company_name="Unassigned historical record",
            status="draft",
        )
        db.add(application)
        db.flush()
        db.add(
            ApplicationStatusHistory(
                application_id=application.id,
                from_status=None,
                to_status="draft",
                kind="create",
            )
        )
        db.commit()
        application_id = application.id
        db.close()

        self.assertEqual(client.get(f"/api/applications/{application_id}").status_code, 404)
        listing = client.get("/api/applications").json()
        self.assertEqual(listing["total"], 0)
        db = self.Session()
        self.assertIsNone(
            db.query(Application).filter(Application.id == application_id).one().tenant_id
        )
        self.assertEqual(
            db.query(ApplicationStatusHistory)
            .filter(ApplicationStatusHistory.application_id == application_id)
            .count(),
            1,
        )
        db.close()

    def test_auditor_and_tenant_administrator_do_not_cross_tenant(self):
        owner_id = self._user("owner@x.com", "relationship_manager")
        owner_client = self._client(owner_id)
        application_id = owner_client.post(
            "/api/applications", json={"company_name": "Tenant A"}
        ).json()["id"]

        auditor_id = self._user("auditor@x.com", "auditor")
        self.assertEqual(
            self._client(auditor_id).get(f"/api/applications/{application_id}").status_code,
            404,
        )

        admin_id = self._user("tenant-admin@x.com", "administrator")
        admin_client = self._client(admin_id)
        self.assertEqual(admin_client.get("/api/applications").status_code, 200)
        db = self.Session()
        membership = (
            db.query(TenantMembership)
            .filter(TenantMembership.user_id == admin_id)
            .one()
        )
        membership.org_role = "admin"
        db.commit()
        db.close()
        self.assertEqual(
            admin_client.get(f"/api/applications/{application_id}").status_code,
            404,
        )

    def test_platform_admin_has_no_implicit_application_bypass(self):
        owner_id = self._user("owner@x.com", "relationship_manager")
        application_id = self._client(owner_id).post(
            "/api/applications", json={"company_name": "Tenant A"}
        ).json()["id"]
        platform_id = self._user("platform@x.com", "platform_admin")
        self.assertEqual(
            self._client(platform_id).get(f"/api/applications/{application_id}").status_code,
            403,
        )

    def test_multiple_memberships_use_existing_default_tenant(self):
        user_id = self._user("multi@x.com", "relationship_manager")
        client = self._client(user_id)
        self.assertEqual(client.get("/api/applications").status_code, 200)
        db = self.Session()
        default_membership = (
            db.query(TenantMembership)
            .filter(TenantMembership.user_id == user_id)
            .one()
        )
        organization = Organization(
            slug="secondary-tenant-org",
            name="Secondary tenant",
            org_type="enterprise",
        )
        db.add(organization)
        db.flush()
        tenant = Tenant(
            organization_id=organization.id,
            slug="secondary",
            name="Secondary tenant",
            is_default=False,
        )
        db.add(tenant)
        db.flush()
        db.add(
            TenantMembership(
                tenant_id=tenant.id,
                user_id=user_id,
                status="active",
                org_role="member",
                is_default=False,
            )
        )
        db.commit()
        expected_tenant_id = default_membership.tenant_id
        db.close()

        created = client.post("/api/applications", json={"company_name": "Default tenant"})
        self.assertEqual(created.status_code, 201)
        db = self.Session()
        app = db.query(Application).filter(Application.id == created.json()["id"]).one()
        self.assertEqual(app.tenant_id, expected_tenant_id)
        db.close()

    def test_illegal_transition_returns_409(self):
        # A risk_manager has applications.transition, so the request reaches the
        # state machine and is rejected for being an illegal move (not for perms).
        rm = self._user("rm@x.com", "relationship_manager")
        mgr = self._user("mgr@x.com", "risk_manager")
        create_client = self._client(rm)
        app_id = create_client.post("/api/applications", json={"company_name": "Acme"}).json()["id"]
        db = self.Session()
        tenant_id = (
            db.query(TenantMembership.tenant_id)
            .filter(TenantMembership.user_id == rm, TenantMembership.status == "active")
            .one()[0]
        )
        ensure_test_membership(db, mgr, "mgr@x.com", tenant_id)
        db.close()

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
