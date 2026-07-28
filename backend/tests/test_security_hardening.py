"""Phase 11, M8 — security hardening tests.

Covers field-level encryption + key rotation, signed URLs, PII masking,
retention + secure deletion, JWT key rotation, refresh-token rotation with reuse
detection, password policy, account lockout, TOTP MFA, risk-based auth, and the
security-headers middleware.
"""

import os
import unittest
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core import authn, crypto
from backend.app.core.security_middleware import SecurityHeadersMiddleware
from backend.app.core.settings import reload_settings


class FieldCipherTest(unittest.TestCase):
    def test_roundtrip(self):
        c = crypto.FieldCipher("unit-test-key", version=1)
        token = c.encrypt("sensitive-value")
        self.assertNotIn("sensitive-value", token)
        self.assertEqual(c.decrypt(token), "sensitive-value")

    def test_tamper_detected(self):
        c = crypto.FieldCipher("unit-test-key")
        token = c.encrypt("hello world")
        parts = token.split(".")
        parts[3] = parts[3][:-2] + ("aa" if not parts[3].endswith("aa") else "bb")
        with self.assertRaises(crypto.DecryptionError):
            c.decrypt(".".join(parts))

    def test_malformed_token(self):
        with self.assertRaises(crypto.DecryptionError):
            crypto.FieldCipher("k").decrypt("not-a-valid-token")


class KeyRingTest(unittest.TestCase):
    def test_rotation_keeps_old_readable(self):
        ring = crypto.KeyRing()
        ring.add_key(1, "key-one")
        old_token = ring.encrypt("v1-data")
        ring.rotate(2, "key-two")
        self.assertEqual(ring.active_version, 2)
        # New writes use v2; old v1 ciphertext still decrypts.
        self.assertEqual(ring.decrypt(old_token), "v1-data")
        new_token = ring.encrypt("v2-data")
        self.assertEqual(ring.decrypt(new_token), "v2-data")

    def test_crypto_shred(self):
        ring = crypto.KeyRing()
        ring.add_key(1, "key-one")
        token = ring.encrypt("secret")
        ring.rotate(2, "key-two")
        ring.shred(1)
        with self.assertRaises(crypto.DecryptionError):
            ring.decrypt(token)


class SignedUrlTest(unittest.TestCase):
    def test_valid_and_expired(self):
        now = datetime(2026, 1, 1, tzinfo=UTC)
        url = crypto.sign_url("/files/report.pdf", expires_in=60, secret="s", now=lambda: now)
        exp = int(url.split("exp=")[1].split("&")[0])
        sig = url.split("sig=")[1]
        self.assertTrue(
            crypto.verify_signed_url("/files/report.pdf", exp, sig, secret="s", now=lambda: now)
        )
        later = now + timedelta(seconds=120)
        self.assertFalse(
            crypto.verify_signed_url("/files/report.pdf", exp, sig, secret="s", now=lambda: later)
        )

    def test_tampered_path_fails(self):
        now = datetime(2026, 1, 1, tzinfo=UTC)
        url = crypto.sign_url("/a", expires_in=60, secret="s", now=lambda: now)
        exp = int(url.split("exp=")[1].split("&")[0])
        sig = url.split("sig=")[1]
        self.assertFalse(crypto.verify_signed_url("/b", exp, sig, secret="s", now=lambda: now))


class PiiMaskingTest(unittest.TestCase):
    def test_masks(self):
        self.assertEqual(crypto.PiiMasker.mask_email("john.doe@example.com"), "j***@example.com")
        self.assertIn("***", crypto.PiiMasker.mask_pan("ABCDE1234F"))
        self.assertTrue(crypto.PiiMasker.mask_aadhaar("1234 5678 9012").endswith("9012"))
        masked_card = crypto.PiiMasker.mask_card("4111 1111 1111 1234")
        self.assertTrue(masked_card.endswith("1234") and "*" in masked_card)

    def test_mask_text_and_mapping(self):
        text = "contact john@x.com or 9876543210"
        out = crypto.mask_pii(text)
        self.assertNotIn("john@x.com", out)
        self.assertNotIn("9876543210", out)
        rec = crypto.mask_mapping({"name": "Jane", "ssn": "123"}, {"ssn"})
        self.assertEqual(rec, {"name": "Jane", "ssn": "***"})


class RetentionTest(unittest.TestCase):
    def test_expiry_and_legal_hold(self):
        p = crypto.RetentionPolicy("logs", retention_days=30)
        created = datetime(2026, 1, 1, tzinfo=UTC)
        self.assertFalse(p.is_expired(created, now=created + timedelta(days=10)))
        self.assertTrue(p.is_expired(created, now=created + timedelta(days=31)))
        held = crypto.RetentionPolicy("logs", retention_days=1, legal_hold=True)
        self.assertFalse(held.is_expired(created, now=created + timedelta(days=999)))

    def test_default_registry(self):
        self.assertIsNotNone(crypto.default_retention.get("audit_log"))
        self.assertGreater(crypto.default_retention.get("audit_log").retention_days, 2000)

    def test_secure_overwrite(self):
        import tempfile

        fd, path = tempfile.mkstemp()
        os.write(fd, b"secret data")
        os.close(fd)
        self.assertTrue(crypto.secure_overwrite_file(path, passes=2))
        self.assertFalse(os.path.exists(path))
        self.assertFalse(crypto.secure_overwrite_file(path))


class JwtKeyRingTest(unittest.TestCase):
    def test_sign_verify_and_rotation(self):
        ring = authn.JwtKeyRing()
        ring.add_key("v1", "secret-one")
        token1 = ring.sign({"sub": "u1"})
        ring.rotate("v2", "secret-two")
        token2 = ring.sign({"sub": "u2"})
        # Both verify: v1 token against retained key, v2 against active.
        self.assertEqual(ring.verify(token1)["sub"], "u1")
        self.assertEqual(ring.verify(token2)["sub"], "u2")
        ring.retire("v1")
        from jose import JWTError

        with self.assertRaises(JWTError):
            ring.verify(token1)


class RefreshTokenTest(unittest.TestCase):
    def setUp(self):
        self.clock = [1000.0]
        self.svc = authn.RefreshTokenService(clock=lambda: self.clock[0])

    def test_issue_and_rotate(self):
        t1 = self.svc.issue(42)
        t2 = self.svc.rotate(t1)
        self.assertNotEqual(t1, t2)
        t3 = self.svc.rotate(t2)
        self.assertNotEqual(t2, t3)

    def test_reuse_detection_revokes_family(self):
        t1 = self.svc.issue(42)
        self.svc.rotate(t1)  # consumes t1
        with self.assertRaises(authn.RefreshReuseError):
            self.svc.rotate(t1)  # replay -> family revoked

    def test_expired(self):
        t1 = self.svc.issue(42, ttl_days=1)
        self.clock[0] += 2 * 86400
        with self.assertRaises(authn.RefreshReuseError):
            self.svc.rotate(t1)


class PasswordPolicyTest(unittest.TestCase):
    def setUp(self):
        self.p = authn.PasswordPolicy(min_length=12, require_complexity=True)

    def test_rejects_weak(self):
        self.assertFalse(self.p.is_valid("short"))
        self.assertFalse(self.p.is_valid("password"))
        self.assertFalse(self.p.is_valid("aaaaaaaaaaaa"))

    def test_accepts_strong(self):
        chk = self.p.check("Str0ng&Passw0rd!")
        self.assertTrue(chk.ok, chk.violations)
        self.assertGreater(chk.score, 60)

    def test_rejects_username_in_password(self):
        self.assertFalse(self.p.is_valid("Alice-Str0ng!!", username="alice"))


class AccountLockoutTest(unittest.TestCase):
    def test_locks_after_threshold(self):
        clock = [0.0]
        lock = authn.AccountLockout(
            threshold=3, window_seconds=60, duration_seconds=300, clock=lambda: clock[0]
        )
        self.assertFalse(lock.record_failure("u"))
        self.assertFalse(lock.record_failure("u"))
        self.assertTrue(lock.record_failure("u"))
        self.assertTrue(lock.is_locked("u"))
        clock[0] += 301
        self.assertFalse(lock.is_locked("u"))

    def test_success_resets(self):
        lock = authn.AccountLockout(threshold=3, window_seconds=60)
        lock.record_failure("u")
        lock.record_success("u")
        self.assertEqual(lock.seconds_remaining("u"), 0)


class TotpTest(unittest.TestCase):
    def test_generate_verify(self):
        totp = authn.Totp()
        secret = totp.generate_secret()
        code = totp.now_code(secret, at=1_700_000_000)
        self.assertTrue(totp.verify(secret, code, at=1_700_000_000))
        self.assertFalse(totp.verify(secret, "000000", at=1_700_000_000 + 100))

    def test_provisioning_uri(self):
        uri = authn.Totp().provisioning_uri("ABCDEF", "user@x.com", issuer="Acme")
        self.assertTrue(uri.startswith("otpauth://totp/"))
        self.assertIn("secret=ABCDEF", uri)


class RiskEngineTest(unittest.TestCase):
    def test_levels(self):
        eng = authn.RiskEngine()
        low = eng.assess(authn.RiskSignals())
        self.assertEqual(low.level, "low")
        self.assertFalse(low.require_mfa)
        med = eng.assess(authn.RiskSignals(known_device=False, known_ip=False))
        self.assertEqual(med.level, "medium")
        self.assertTrue(med.require_mfa)
        high = eng.assess(
            authn.RiskSignals(known_device=False, impossible_travel=True, new_country=True)
        )
        self.assertEqual(high.level, "high")
        self.assertTrue(high.deny)


class SecurityHeadersTest(unittest.TestCase):
    def _client(self):
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/x")
        def _x():
            return {"ok": True}

        return TestClient(app)

    def tearDown(self):
        os.environ.pop("SECURITY_HEADERS_ENABLED", None)
        reload_settings()

    def test_headers_present(self):
        reload_settings()
        r = self._client().get("/x")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertIn("Content-Security-Policy", r.headers)
        self.assertIn("Referrer-Policy", r.headers)
        self.assertIn("Permissions-Policy", r.headers)

    def test_toggle_off(self):
        os.environ["SECURITY_HEADERS_ENABLED"] = "false"
        reload_settings()
        r = self._client().get("/x")
        self.assertNotIn("X-Frame-Options", r.headers)


if __name__ == "__main__":
    unittest.main()
