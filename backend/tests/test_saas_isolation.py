""" Tenant isolation via the tenant-aware repository (M1)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.models.tenancy import Workspace
from backend.app.services.saas import tenancy as tsvc
from backend.app.services.saas.context import (
    TenantContextError, current_tenant_id, use_tenant,
)
from backend.app.services.saas.repository import (
    CrossTenantAccessError, TenantRepository,
)
from backend.tests._saas_helpers import fresh_session, seed_all


class IsolationTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)
        self.org_a = tsvc.create_organization(self.db, slug="a", name="A")
        self.org_b = tsvc.create_organization(self.db, slug="b", name="B")
        self.t_a = tsvc.default_tenant(self.db, self.org_a.id).id
        self.t_b = tsvc.default_tenant(self.db, self.org_b.id).id

    def tearDown(self):
        self.db.close()

    def test_repository_scopes_queries_to_tenant(self):
        repo_a = TenantRepository(self.db, Workspace, tenant_id=self.t_a)
        repo_b = TenantRepository(self.db, Workspace, tenant_id=self.t_b)
        repo_a.add(Workspace(name="A-WS"))
        repo_b.add(Workspace(name="B-WS"))
        self.db.commit()
        self.assertEqual(repo_a.count(), 1)
        self.assertEqual(repo_b.count(), 1)
        self.assertEqual(repo_a.all()[0].name, "A-WS")

    def test_get_across_tenant_returns_none(self):
        repo_a = TenantRepository(self.db, Workspace, tenant_id=self.t_a)
        ws = repo_a.add(Workspace(name="secret"))
        self.db.commit()
        repo_b = TenantRepository(self.db, Workspace, tenant_id=self.t_b)
        self.assertIsNone(repo_b.get(ws.id))
        with self.assertRaises(CrossTenantAccessError):
            repo_b.get_or_403(ws.id)

    def test_add_wrong_tenant_rejected(self):
        repo_a = TenantRepository(self.db, Workspace, tenant_id=self.t_a)
        with self.assertRaises(CrossTenantAccessError):
            repo_a.add(Workspace(tenant_id=self.t_b, name="mislabelled"))

    def test_repository_requires_scope(self):
        repo = TenantRepository(self.db, Workspace, tenant_id=None)
        with self.assertRaises(TenantContextError):
            repo.all()

    def test_ambient_context_supplies_tenant(self):
        with use_tenant(self.t_a):
            self.assertEqual(current_tenant_id(), self.t_a)
            repo = TenantRepository(self.db, Workspace)  # no explicit tenant
            repo.add(Workspace(name="ambient"))
            self.db.commit()
            self.assertEqual(repo.count(), 1)
        self.assertIsNone(current_tenant_id())

    def test_delete_across_tenant_rejected(self):
        repo_a = TenantRepository(self.db, Workspace, tenant_id=self.t_a)
        ws = repo_a.add(Workspace(name="x"))
        self.db.commit()
        repo_b = TenantRepository(self.db, Workspace, tenant_id=self.t_b)
        with self.assertRaises(CrossTenantAccessError):
            repo_b.delete(ws)

    def test_context_is_reset_after_block(self):
        with use_tenant(self.t_a):
            pass
        self.assertIsNone(current_tenant_id())
        with use_tenant(self.t_b):
            self.assertEqual(current_tenant_id(), self.t_b)


if __name__ == "__main__":
    unittest.main()
