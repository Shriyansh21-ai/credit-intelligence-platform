""" additional edge-case coverage across core modules."""

import tempfile
import unittest
from pathlib import Path

from backend.app.core import authn, compliance, crypto, dr, pagination


class DeriveKeyTest(unittest.TestCase):
    def test_deterministic(self):
        a = crypto.derive_key("secret", b"salt")
        b = crypto.derive_key("secret", b"salt")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 32)

    def test_salt_changes_key(self):
        self.assertNotEqual(crypto.derive_key("s", b"salt1"), crypto.derive_key("s", b"salt2"))

    def test_length_param(self):
        self.assertEqual(len(crypto.derive_key("s", b"x", length=16)), 16)


class SecureOverwriteTest(unittest.TestCase):
    def test_missing_file_false(self):
        self.assertFalse(crypto.secure_overwrite_file("/no/such/file"))

    def test_overwrite_and_remove(self):
        fd, path = tempfile.mkstemp()
        Path(path).write_bytes(b"sensitive")
        import os

        os.close(fd)
        self.assertTrue(crypto.secure_overwrite_file(path, passes=1))
        self.assertFalse(Path(path).exists())


class FileTreeEdgeTest(unittest.TestCase):
    def test_backup_nonexistent_source(self):
        tmp = Path(tempfile.mkdtemp())
        target = dr.FileTreeBackupTarget("empty", str(tmp / "does-not-exist"))
        artifact = target.backup(tmp)
        self.assertTrue(dr.validate_backup(artifact))  # empty archive still valid

    def test_config_restore_noop_true(self):
        tmp = Path(tempfile.mkdtemp())
        art = dr.ConfigBackupTarget().backup(tmp)
        self.assertTrue(dr.ConfigBackupTarget().restore(art))


class SecretRefRoundTripTest(unittest.TestCase):
    def test_encrypt_decrypt_manifest(self):
        tmp = Path(tempfile.mkdtemp())
        target = dr.SecretRefBackupTarget(lambda: [{"name": "a/b", "version": 2}])
        art = target.backup(tmp)
        self.assertTrue(dr.validate_backup(art))
        self.assertTrue(target.restore(art))


class PaginationClampTest(unittest.TestCase):
    def test_negative_size(self):
        self.assertEqual(pagination.clamp_page_size(-5), pagination.DEFAULT_PAGE_SIZE)

    def test_custom_default_and_max(self):
        self.assertEqual(pagination.clamp_page_size(None, default=10), 10)
        self.assertEqual(pagination.clamp_page_size(999, maximum=100), 100)


class KeysetPageDictTest(unittest.TestCase):
    def test_as_dict(self):
        kp = pagination.KeysetPage(items=[1, 2], next_cursor=2, page_size=2, has_next=True)
        d = kp.as_dict()
        self.assertEqual(d["items"], [1, 2])
        self.assertEqual(d["pagination"]["next_cursor"], 2)


class RiskLevelMatrixTest(unittest.TestCase):
    def test_new_ip_only_is_low(self):
        a = authn.RiskEngine().assess(authn.RiskSignals(known_ip=False))
        self.assertEqual(a.level, "low")

    def test_reasons_listed(self):
        a = authn.RiskEngine().assess(authn.RiskSignals(known_device=False, new_country=True))
        self.assertTrue(a.reasons)
        self.assertTrue(any("device" in r for r in a.reasons))


class PasswordScoreTest(unittest.TestCase):
    def test_common_password_low_score(self):
        chk = authn.PasswordPolicy(min_length=6).check("password")
        self.assertLessEqual(chk.score, 10)

    def test_run_detection(self):
        self.assertFalse(authn.PasswordPolicy(min_length=6).is_valid("Aaaaa1!bbbb"))


class ConsentPointInTimeTest(unittest.TestCase):
    def test_independent_subjects(self):
        ledger = compliance.ConsentLedger()
        ledger.grant("u1", "p")
        self.assertTrue(ledger.has_consent("u1", "p"))
        self.assertFalse(ledger.has_consent("u2", "p"))


class ControlCatalogTest(unittest.TestCase):
    def test_every_control_maps_something(self):
        for control in compliance.control_catalog:
            self.assertTrue(control.mappings, f"{control.id} maps to no framework")

    def test_encryption_control_covers_pci(self):
        enc = next(c for c in compliance.control_catalog if c.id == "encryption-at-rest")
        self.assertIn("3.4", enc.covers(compliance.Framework.PCI_DSS))


if __name__ == "__main__":
    unittest.main()
