""" Enterprise security (M14)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.models.user import User
from backend.app.services.saas import security as sec
from backend.app.services.saas import tenancy as tsvc
from backend.tests._saas_helpers import fresh_session, seed_all


class SecurityTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)
        self.org = tsvc.create_organization(self.db, slug="sec", name="Sec")
        self.tid = tsvc.default_tenant(self.db, self.org.id).id
        self.user = User(email="u@sec.com", password="x")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()

    def test_secret_store_and_reveal(self):
        sec.store_secret(self.db, "api_key", "s3cr3t", tenant_id=self.tid)
        self.assertEqual(sec.get_secret(self.db, "api_key", tenant_id=self.tid), "s3cr3t")

    def test_secret_rotation_increments_version(self):
        r1 = sec.store_secret(self.db, "k", "v1", tenant_id=self.tid)
        r2 = sec.rotate_secret(self.db, "k", "v2", tenant_id=self.tid)
        self.assertEqual(r2.version, r1.version + 1)
        self.assertEqual(sec.get_secret(self.db, "k", tenant_id=self.tid), "v2")

    def test_encrypted_at_rest(self):
        ref = sec.store_secret(self.db, "k", "plaintext", tenant_id=self.tid)
        self.assertNotIn("plaintext", ref.value_encrypted or "")

    def test_tenant_encryption_roundtrip(self):
        ct = sec.tenant_encrypt("data", self.tid)
        self.assertEqual(sec.tenant_decrypt(ct, self.tid), "data")

    def test_tenant_encryption_cross_tenant_fails(self):
        ct = sec.tenant_encrypt("data", self.tid)
        with self.assertRaises(ValueError):
            sec.tenant_decrypt(ct, self.tid + 1)

    def test_rate_limiter(self):
        limiter = sec.RateLimiter(clock=lambda: 0.0)
        for _ in range(3):
            r = limiter.check("ip:1", limit=3, window_seconds=60)
            self.assertTrue(r["allowed"])
        blocked = limiter.check("ip:1", limit=3, window_seconds=60)
        self.assertFalse(blocked["allowed"])

    def test_ip_allow_list(self):
        # No entries = open.
        self.assertTrue(sec.ip_allowed(self.db, self.tid, "1.2.3.4"))
        sec.add_ip_allow(self.db, self.tid, "10.0.0.0/8")
        self.assertTrue(sec.ip_allowed(self.db, self.tid, "10.1.2.3"))
        self.assertFalse(sec.ip_allowed(self.db, self.tid, "192.168.0.1"))

    def test_invalid_cidr_rejected(self):
        with self.assertRaises(ValueError):
            sec.add_ip_allow(self.db, self.tid, "not-a-cidr")

    def test_session_lifecycle(self):
        s = sec.create_session(self.db, self.user.id, tenant_id=self.tid, ip="1.1.1.1")
        self.assertEqual(s.status, "active")
        sec.revoke_session(self.db, s.id)
        self.db.refresh(s)
        self.assertEqual(s.status, "revoked")
        self.assertEqual(len(sec.list_sessions(self.db, self.user.id)), 1)

    def test_device_registration_idempotent(self):
        d1 = sec.register_device(self.db, self.user.id, "fp-123", tenant_id=self.tid)
        d2 = sec.register_device(self.db, self.user.id, "fp-123", tenant_id=self.tid)
        self.assertEqual(d1.id, d2.id)
        sec.trust_device(self.db, d1.id, True)
        self.db.refresh(d1)
        self.assertTrue(d1.trusted)

    def test_idp_configuration_with_secret(self):
        row = sec.configure_idp(self.db, self.tid, "oidc", display_name="Okta",
                                config={"issuer": "https://okta"}, client_secret="cs",
                                enabled=True, mfa_required=True)
        self.assertTrue(row.enabled)
        self.assertTrue(row.mfa_required)
        self.assertIsNotNone(row.client_secret_ref)
        self.assertEqual(len(sec.list_idps(self.db, self.tid)), 1)

    def test_idp_invalid_protocol(self):
        with self.assertRaises(ValueError):
            sec.configure_idp(self.db, self.tid, "ldap")

    def test_saml_and_scip_protocols(self):
        sec.configure_idp(self.db, self.tid, "saml")
        sec.configure_idp(self.db, self.tid, "scim")
        protocols = {i.protocol for i in sec.list_idps(self.db, self.tid)}
        self.assertEqual(protocols, {"saml", "scim"})


if __name__ == "__main__":
    unittest.main()
