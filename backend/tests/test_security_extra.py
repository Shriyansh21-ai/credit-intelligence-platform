""" expanded security tests (crypto, authn, PII, retention).

Deepens M8 coverage with edge cases, rotation matrices, and adversarial inputs.
"""

import unittest
from datetime import UTC, datetime, timedelta

from backend.app.core import authn, crypto


class CipherEdgeTest(unittest.TestCase):
    def test_empty_and_unicode(self):
        c = crypto.FieldCipher("k")
        for value in ["", "a", "unicode ✓ 你好 🚀", "x" * 5000]:
            self.assertEqual(c.decrypt(c.encrypt(value)), value)

    def test_distinct_nonce_per_encryption(self):
        c = crypto.FieldCipher("k")
        self.assertNotEqual(c.encrypt("same"), c.encrypt("same"))

    def test_wrong_key_fails(self):
        token = crypto.FieldCipher("key-a").encrypt("secret")
        with self.assertRaises(crypto.DecryptionError):
            crypto.FieldCipher("key-b").decrypt(token)

    def test_version_embedded(self):
        token = crypto.FieldCipher("k", version=7).encrypt("x")
        self.assertEqual(token.split(".")[1], "7")


class KeyRingMatrixTest(unittest.TestCase):
    def test_three_generation_rotation(self):
        ring = crypto.KeyRing()
        ring.add_key(1, "k1")
        t1 = ring.encrypt("gen1")
        ring.rotate(2, "k2")
        t2 = ring.encrypt("gen2")
        ring.rotate(3, "k3")
        t3 = ring.encrypt("gen3")
        self.assertEqual(ring.decrypt(t1), "gen1")
        self.assertEqual(ring.decrypt(t2), "gen2")
        self.assertEqual(ring.decrypt(t3), "gen3")
        self.assertEqual(ring.active_version, 3)

    def test_shred_active_promotes_remaining(self):
        ring = crypto.KeyRing()
        ring.add_key(1, "k1")
        ring.add_key(2, "k2")
        ring.shred(2)
        self.assertEqual(ring.active_version, 1)

    def test_no_active_key_raises(self):
        ring = crypto.KeyRing()
        with self.assertRaises(RuntimeError):
            ring.encrypt("x")

    def test_unknown_version_decrypt(self):
        ring = crypto.KeyRing()
        ring.add_key(1, "k1")
        with self.assertRaises(crypto.DecryptionError):
            ring.decrypt("s.9.a.b.c")


class SignedUrlEdgeTest(unittest.TestCase):
    def test_existing_query_string_appends(self):
        now = datetime(2026, 1, 1, tzinfo=UTC)
        url = crypto.sign_url("/f?a=1", expires_in=60, secret="s", now=lambda: now)
        self.assertIn("&exp=", url)
        self.assertIn("&sig=", url)

    def test_exact_expiry_boundary(self):
        now = datetime(2026, 1, 1, tzinfo=UTC)
        url = crypto.sign_url("/f", expires_in=60, secret="s", now=lambda: now)
        exp = int(url.split("exp=")[1].split("&")[0])
        sig = url.split("sig=")[1]
        at_exp = datetime.fromtimestamp(exp, UTC)
        self.assertTrue(crypto.verify_signed_url("/f", exp, sig, secret="s", now=lambda: at_exp))


class PiiExtraTest(unittest.TestCase):
    def test_multiple_emails(self):
        out = crypto.mask_pii("a@x.com and b@y.org")
        self.assertNotIn("a@x.com", out)
        self.assertNotIn("b@y.org", out)

    def test_no_pii_unchanged(self):
        self.assertEqual(crypto.mask_pii("nothing sensitive here"), "nothing sensitive here")

    def test_mapping_preserves_non_sensitive(self):
        rec = crypto.mask_mapping({"a": 1, "b": 2, "c": None}, {"b", "c"})
        self.assertEqual(rec["a"], 1)
        self.assertEqual(rec["b"], "***")
        self.assertIsNone(rec["c"])  # None is not masked


class RetentionExtraTest(unittest.TestCase):
    def test_naive_datetime_treated_utc(self):
        p = crypto.RetentionPolicy("x", 10)
        created = datetime(2026, 1, 1)  # naive
        self.assertTrue(p.is_expired(created, now=datetime(2026, 2, 1, tzinfo=UTC)))

    def test_registry_expired_helper(self):
        reg = crypto.RetentionRegistry()
        reg.register(crypto.RetentionPolicy("logs", 1))
        old = datetime(2026, 1, 1, tzinfo=UTC)
        self.assertTrue(reg.expired("logs", old, now=old + timedelta(days=2)))
        self.assertFalse(reg.expired("unknown", old))

    def test_all_returns_copy(self):
        reg = crypto.RetentionRegistry()
        reg.register(crypto.RetentionPolicy("a", 1))
        reg.all()["a"] = None  # mutating the copy must not affect the registry
        self.assertIsNotNone(reg.get("a"))


class PasswordPolicyExtraTest(unittest.TestCase):
    def setUp(self):
        self.p = authn.PasswordPolicy(min_length=10, require_complexity=True)

    def test_score_monotonic_with_length(self):
        short = self.p.check("Aa1!aaaa").score
        longer = self.p.check("Aa1!aaaaaaaaaaaa").score
        self.assertGreater(longer, short)

    def test_missing_classes(self):
        self.assertFalse(self.p.is_valid("alllowercaseletters"))
        self.assertFalse(self.p.is_valid("ALLUPPERCASELETTERS"))

    def test_complexity_off(self):
        p = authn.PasswordPolicy(min_length=8, require_complexity=False)
        self.assertTrue(p.is_valid("simplelongpassword"))


class LockoutExtraTest(unittest.TestCase):
    def test_window_expiry_resets_counter(self):
        clock = [0.0]
        lock = authn.AccountLockout(
            threshold=3, window_seconds=10, duration_seconds=100, clock=lambda: clock[0]
        )
        lock.record_failure("u")
        clock[0] = 20  # beyond window
        lock.record_failure("u")
        lock.record_failure("u")
        self.assertFalse(lock.is_locked("u"))  # only 2 within window

    def test_seconds_remaining(self):
        clock = [0.0]
        lock = authn.AccountLockout(
            threshold=1, window_seconds=10, duration_seconds=50, clock=lambda: clock[0]
        )
        lock.record_failure("u")
        self.assertTrue(lock.is_locked("u"))
        clock[0] = 10
        self.assertEqual(lock.seconds_remaining("u"), 40)


class TotpExtraTest(unittest.TestCase):
    def test_drift_window(self):
        totp = authn.Totp(period=30)
        secret = totp.generate_secret()
        prev = totp.now_code(secret, at=1000 - 30)
        self.assertTrue(totp.verify(secret, prev, at=1000, window=1))
        self.assertFalse(totp.verify(secret, prev, at=1000, window=0))

    def test_eight_digit(self):
        totp = authn.Totp(digits=8)
        secret = totp.generate_secret()
        code = totp.now_code(secret, at=1000)
        self.assertEqual(len(code), 8)
        self.assertTrue(totp.verify(secret, code, at=1000))


class RiskExtraTest(unittest.TestCase):
    def test_tor_and_failures_escalate(self):
        eng = authn.RiskEngine()
        a = eng.assess(authn.RiskSignals(tor_or_proxy=True, recent_failures=3))
        self.assertIn(a.level, ("medium", "high"))
        self.assertTrue(a.require_mfa)

    def test_score_capped_at_100(self):
        eng = authn.RiskEngine()
        a = eng.assess(
            authn.RiskSignals(
                known_device=False,
                known_ip=False,
                new_country=True,
                impossible_travel=True,
                tor_or_proxy=True,
                recent_failures=9,
            )
        )
        self.assertLessEqual(a.score, 100)


class JwtRingExtraTest(unittest.TestCase):
    def test_expired_token_rejected(self):
        ring = authn.JwtKeyRing()
        ring.add_key("v1", "s")
        token = ring.sign({"sub": "u"}, expires_in=-10)  # already expired
        from jose import JWTError

        with self.assertRaises(JWTError):
            ring.verify(token)

    def test_active_kid_tracking(self):
        ring = authn.JwtKeyRing()
        ring.add_key("v1", "s1")
        ring.rotate("v2", "s2")
        self.assertEqual(ring.active_kid, "v2")


if __name__ == "__main__":
    unittest.main()
