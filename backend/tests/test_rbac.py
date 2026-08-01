""" tests: RBAC (roles, permissions, enforcement)."""

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
from backend.app.models.user import User
from backend.app.routes import rbac as rbac_routes
from backend.app.services.rbac import (
    has_permission,
    sync_rbac,
    user_permission_codes,
)
from backend.app.services.rbac.seeding import assign_role


class RbacTestBase(unittest.TestCase):
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

    def _make_user(self, email, role=None):
        db = self.Session()
        try:
            user = User(email=email, password="x")
            db.add(user)
            db.commit()
            db.refresh(user)
            if role:
                assign_role(db, user, role)
            return user.id
        finally:
            db.close()

    def _app_for(self, user_id):
        app = FastAPI()
        app.include_router(rbac_routes.router)

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


class RbacSeedingTest(RbacTestBase):
    def test_sync_is_idempotent(self):
        db = self.Session()
        sync_rbac(db)  # second run
        from backend.app.models.rbac import Permission, Role

        from backend.app.services.rbac.catalog import ALL_PERMISSION_CODES

        self.assertEqual(db.query(Role).count(), 9)
        self.assertEqual(db.query(Permission).count(), len(ALL_PERMISSION_CODES))
        db.close()

    def test_admin_has_all_permissions(self):
        uid = self._make_user("admin@x.com", "administrator")
        db = self.Session()
        user = db.query(User).filter(User.id == uid).first()
        from backend.app.services.rbac.catalog import ALL_PERMISSION_CODES

        self.assertTrue(has_permission(db, user, "users.manage"))
        self.assertTrue(has_permission(db, user, "config.manage"))
        self.assertEqual(len(user_permission_codes(db, user)), len(ALL_PERMISSION_CODES))
        db.close()

    def test_viewer_is_restricted(self):
        uid = self._make_user("viewer@x.com", "viewer")
        db = self.Session()
        user = db.query(User).filter(User.id == uid).first()
        self.assertTrue(has_permission(db, user, "applications.view"))
        self.assertFalse(has_permission(db, user, "approvals.approve"))
        self.assertFalse(has_permission(db, user, "users.manage"))
        db.close()


class RbacApiTest(RbacTestBase):
    def test_me_returns_roles_and_permissions(self):
        uid = self._make_user("analyst@x.com", "credit_analyst")
        client = self._app_for(uid)
        body = client.get("/api/rbac/me").json()
        self.assertIn("credit_analyst", body["roles"])
        self.assertIn("analysis.run", body["permissions"])

    def test_roles_endpoint_requires_permission(self):
        uid = self._make_user("viewer@x.com", "viewer")
        client = self._app_for(uid)
        self.assertEqual(client.get("/api/rbac/roles").status_code, 403)

    def test_admin_can_list_roles(self):
        uid = self._make_user("admin@x.com", "administrator")
        client = self._app_for(uid)
        resp = client.get("/api/rbac/roles")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 9)

    def test_assign_role_requires_users_manage(self):
        target = self._make_user("target@x.com", "viewer")
        actor = self._make_user("analyst@x.com", "credit_analyst")
        client = self._app_for(actor)
        resp = client.post(f"/api/rbac/users/{target}/roles", json={"role": "senior_analyst"})
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_assign_and_replace_roles(self):
        target = self._make_user("target@x.com", "viewer")
        admin = self._make_user("admin@x.com", "administrator")
        client = self._app_for(admin)

        resp = client.post(
            f"/api/rbac/users/{target}/roles",
            json={"role": "senior_analyst", "replace": True},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["roles"], ["senior_analyst"])

        resp = client.put(
            f"/api/rbac/users/{target}/roles",
            json={"roles": ["viewer", "auditor"]},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(sorted(resp.json()["roles"]), ["auditor", "viewer"])

    def test_assign_unknown_role_400(self):
        target = self._make_user("target@x.com", "viewer")
        admin = self._make_user("admin@x.com", "administrator")
        client = self._app_for(admin)
        resp = client.post(f"/api/rbac/users/{target}/roles", json={"role": "wizard"})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
