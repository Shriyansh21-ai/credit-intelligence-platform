import unittest

from backend.app.services.rbac import catalog as rbac_catalog


SEC_PERMS = [
    "sec.dashboard.view", "sec.threat.view", "sec.owasp.view", "sec.authz.view",
    "sec.tenant.view", "sec.secrets.view", "sec.data.view", "sec.supplychain.view",
    "sec.container.view", "sec.aisec.view", "sec.mlsec.view", "sec.privacy.view",
    "sec.privacy.manage", "sec.compliance.view", "sec.compliance.manage",
    "sec.findings.view", "sec.findings.manage", "sec.risk.view", "sec.risk.manage",
    "sec.admin",
]


class SecurityRbacCatalogTest(unittest.TestCase):
    def test_all_sec_perms_registered(self):
        codes = set(rbac_catalog.ALL_PERMISSION_CODES)
        for code in SEC_PERMS:
            self.assertIn(code, codes, f"missing permission: {code}")

    def test_sec_perms_have_category(self):
        by_code = {c: cat for c, cat, _ in rbac_catalog.PERMISSIONS}
        for code in SEC_PERMS:
            self.assertEqual(by_code[code], "Security & Compliance")

    def test_no_duplicate_permission_codes(self):
        codes = [c for c, _cat, _d in rbac_catalog.PERMISSIONS]
        self.assertEqual(len(codes), len(set(codes)))

    def test_administrator_gets_all_sec(self):
        admin = set(rbac_catalog.resolved_role_permissions("administrator"))
        for code in SEC_PERMS:
            self.assertIn(code, admin)

    def test_oversight_roles_get_read(self):
        for role in ("compliance_officer", "risk_manager", "auditor"):
            perms = set(rbac_catalog.resolved_role_permissions(role))
            self.assertIn("sec.dashboard.view", perms)
            self.assertIn("sec.compliance.view", perms)
            self.assertIn("sec.threat.view", perms)

    def test_compliance_officer_can_manage_compliance(self):
        perms = set(rbac_catalog.resolved_role_permissions("compliance_officer"))
        self.assertIn("sec.compliance.manage", perms)
        self.assertIn("sec.privacy.manage", perms)

    def test_risk_manager_owns_findings_and_risk(self):
        perms = set(rbac_catalog.resolved_role_permissions("risk_manager"))
        self.assertIn("sec.findings.manage", perms)
        self.assertIn("sec.risk.manage", perms)

    def test_viewer_gets_no_sec_manage(self):
        perms = set(rbac_catalog.resolved_role_permissions("viewer"))
        for code in perms:
            self.assertFalse(code.startswith("sec.") and code.endswith((".manage", ".admin")))

    def test_auditor_read_only_on_sec(self):
        perms = set(rbac_catalog.resolved_role_permissions("auditor"))
        self.assertNotIn("sec.findings.manage", perms)
        self.assertNotIn("sec.risk.manage", perms)
        self.assertNotIn("sec.compliance.manage", perms)

    def test_no_dangling_grants(self):
        codes = set(rbac_catalog.ALL_PERMISSION_CODES)
        for role, granted in rbac_catalog.ROLE_PERMISSIONS.items():
            for code in granted:
                if code == "*":
                    continue
                self.assertIn(code, codes, f"{role} grants unknown {code}")


if __name__ == "__main__":
    unittest.main()
