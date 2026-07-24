"""Phase 8 — Multi-tenant architecture + organization management (M1, M2)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.models.user import User
from backend.app.services.saas import tenancy as tsvc
from backend.tests._saas_helpers import fresh_session, seed_all


class TenancyServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)

    def tearDown(self):
        self.db.close()

    def test_seed_creates_default_org_and_tenant(self):
        orgs = tsvc.list_organizations(self.db)
        self.assertEqual(len(orgs), 1)
        self.assertEqual(orgs[0].slug, "platform")
        dt = tsvc.default_tenant(self.db, orgs[0].id)
        self.assertIsNotNone(dt)
        self.assertTrue(dt.is_default)

    def test_create_organization_provisions_default_tenant(self):
        org = tsvc.create_organization(self.db, slug="hdfc", name="HDFC Bank", org_type="bank")
        tenants = tsvc.list_tenants(self.db, org.id)
        self.assertEqual(len(tenants), 1)
        self.assertTrue(tenants[0].is_default)

    def test_duplicate_org_slug_rejected(self):
        tsvc.create_organization(self.db, slug="acme", name="Acme")
        with self.assertRaises(ValueError):
            tsvc.create_organization(self.db, slug="acme", name="Acme 2")

    def test_invalid_org_type_rejected(self):
        with self.assertRaises(ValueError):
            tsvc.create_organization(self.db, slug="x", name="X", org_type="casino")

    def test_multiple_tenants_per_org(self):
        org = tsvc.create_organization(self.db, slug="icici", name="ICICI")
        t2 = tsvc.create_tenant(self.db, org.id, slug="retail", name="Retail")
        self.db.commit()
        self.assertEqual(len(tsvc.list_tenants(self.db, org.id)), 2)
        self.assertFalse(t2.is_default)

    def test_duplicate_tenant_slug_in_org_rejected(self):
        org = tsvc.create_organization(self.db, slug="sbi", name="SBI")
        with self.assertRaises(ValueError):
            tsvc.create_tenant(self.db, org.id, slug="default", name="Dup")

    def test_hierarchy_nesting(self):
        org = tsvc.create_organization(self.db, slug="axis", name="Axis")
        tid = tsvc.default_tenant(self.db, org.id).id
        bu = tsvc.create_business_unit(self.db, tid, "Corporate Banking", code="CB")
        dept = tsvc.create_department(self.db, tid, "Underwriting", business_unit_id=bu.id)
        tsvc.create_team(self.db, tid, "Team A", department_id=dept.id)
        ws = tsvc.create_workspace(self.db, tid, "WS1")
        tsvc.create_project(self.db, tid, "P1", workspace_id=ws.id)
        h = tsvc.get_hierarchy(self.db, tid)
        self.assertEqual(len(h["business_units"]), 1)
        self.assertEqual(len(h["business_units"][0]["departments"]), 1)
        self.assertEqual(len(h["business_units"][0]["departments"][0]["teams"]), 1)
        self.assertEqual(len(h["workspaces"][0]["projects"]), 1)

    def test_add_member_and_membership(self):
        org = tsvc.create_organization(self.db, slug="kotak", name="Kotak")
        tid = tsvc.default_tenant(self.db, org.id).id
        u = User(email="a@kotak.com", password="x")
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        m = tsvc.add_member(self.db, tid, u.id, org_role="admin")
        self.assertEqual(m.org_role, "admin")
        self.assertTrue(tsvc.is_member(self.db, tid, u.id))
        # Re-adding updates, does not duplicate.
        m2 = tsvc.add_member(self.db, tid, u.id, org_role="member")
        self.assertEqual(m2.id, m.id)
        self.assertEqual(len(tsvc.list_members(self.db, tid)), 1)

    def test_invitation_lifecycle(self):
        org = tsvc.create_organization(self.db, slug="yes", name="Yes Bank")
        tid = tsvc.default_tenant(self.db, org.id).id
        inv = tsvc.create_invitation(self.db, tid, "new@yes.com", org_role="member",
                                     rbac_role="credit_analyst")
        self.assertEqual(inv.status, "pending")
        u = User(email="new@yes.com", password="x")
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        m = tsvc.accept_invitation(self.db, inv.token, u)
        self.assertEqual(m.tenant_id, tid)
        self.db.refresh(inv)
        self.assertEqual(inv.status, "accepted")
        # RBAC role granted.
        self.assertIn("credit_analyst", [r.name for r in u.roles])

    def test_invitation_double_accept_rejected(self):
        org = tsvc.create_organization(self.db, slug="idfc", name="IDFC")
        tid = tsvc.default_tenant(self.db, org.id).id
        inv = tsvc.create_invitation(self.db, tid, "x@idfc.com")
        u = User(email="x@idfc.com", password="x")
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        tsvc.accept_invitation(self.db, inv.token, u)
        with self.assertRaises(ValueError):
            tsvc.accept_invitation(self.db, inv.token, u)

    def test_revoke_invitation(self):
        org = tsvc.create_organization(self.db, slug="rbl", name="RBL")
        tid = tsvc.default_tenant(self.db, org.id).id
        inv = tsvc.create_invitation(self.db, tid, "y@rbl.com")
        tsvc.revoke_invitation(self.db, tid, inv.id)
        self.db.refresh(inv)
        self.assertEqual(inv.status, "revoked")

    def test_custom_domain_resolution(self):
        org = tsvc.create_organization(self.db, slug="fed", name="Federal")
        tid = tsvc.default_tenant(self.db, org.id).id
        cd = tsvc.add_custom_domain(self.db, tid, "credit.federal.com")
        self.assertEqual(cd.status, "pending")
        tsvc.verify_custom_domain(self.db, tid, cd.id)
        resolved = tsvc.resolve_tenant_by_domain(self.db, "credit.federal.com")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, tid)

    def test_set_tenant_status(self):
        org = tsvc.create_organization(self.db, slug="bob", name="BoB")
        tid = tsvc.default_tenant(self.db, org.id).id
        t = tsvc.set_tenant_status(self.db, tid, "suspended")
        self.assertEqual(t.status, "suspended")


if __name__ == "__main__":
    unittest.main()
