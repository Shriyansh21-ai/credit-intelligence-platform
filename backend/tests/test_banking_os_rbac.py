import unittest

from backend.tests._banking_os_helpers import fresh_session, make_user, seed_rbac
from backend.app.services.rbac.catalog import (
    ALL_PERMISSION_CODES, ROLE_PERMISSIONS, resolved_role_permissions,
)

PHASE10_PERMS = [
    "policy.view", "policy.manage", "policy.evaluate",
    "committee.view", "committee.participate", "committee.manage",
    "prompt.view", "prompt.manage", "llm.view", "llm.manage",
    "fabric.view", "fabric.manage", "workflowstudio.view", "workflowstudio.manage",
    "marketplace.view", "marketplace.manage",
]


class Phase10CatalogTest(unittest.TestCase):
    def test_all_phase10_perms_registered(self):
        for code in PHASE10_PERMS:
            self.assertIn(code, ALL_PERMISSION_CODES, code)

    def test_no_duplicate_permission_codes(self):
        self.assertEqual(len(ALL_PERMISSION_CODES), len(set(ALL_PERMISSION_CODES)))

    def test_administrator_gets_everything(self):
        perms = resolved_role_permissions("administrator")
        for code in PHASE10_PERMS:
            self.assertIn(code, perms)

    def test_risk_manager_owns_os_governance(self):
        perms = resolved_role_permissions("risk_manager")
        for code in ("policy.manage", "llm.manage", "fabric.manage", "marketplace.manage"):
            self.assertIn(code, perms)

    def test_analyst_reads_but_does_not_author(self):
        perms = resolved_role_permissions("credit_analyst")
        self.assertIn("policy.view", perms)
        self.assertIn("policy.evaluate", perms)
        self.assertNotIn("policy.manage", perms)
        self.assertNotIn("llm.manage", perms)

    def test_grants_reference_real_permissions(self):
        # every granted code (except the "*" sentinel) must exist in the catalog
        for role, codes in ROLE_PERMISSIONS.items():
            for code in codes:
                if code == "*":
                    continue
                self.assertIn(code, ALL_PERMISSION_CODES, f"{role} -> {code}")


class Phase10SyncTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()

    def test_sync_persists_phase10_permissions(self):
        from backend.app.models.rbac import Permission
        db = self.Session()
        codes = {p.code for p in db.query(Permission).all()}
        for code in PHASE10_PERMS:
            self.assertIn(code, codes)
        db.close()

    def test_risk_manager_effective_permissions(self):
        from backend.app.services.rbac import has_permission
        from backend.app.models.user import User
        uid = make_user(self.Session, "rm@os.test", "risk_manager")
        db = self.Session()
        u = db.query(User).filter(User.id == uid).first()
        self.assertTrue(has_permission(db, u, "fabric.manage"))
        self.assertTrue(has_permission(db, u, "committee.manage"))
        db.close()


if __name__ == "__main__":
    unittest.main()
