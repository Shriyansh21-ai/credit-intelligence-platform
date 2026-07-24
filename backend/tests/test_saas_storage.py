"""Phase 8 — Cloud storage platform (M7)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from datetime import datetime, timedelta

from backend.app.services.saas import storage
from backend.app.services.saas import tenancy as tsvc
from backend.tests._saas_helpers import fresh_session, seed_all


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)
        storage.set_active_backend("memory")
        storage._BACKENDS["memory"] = storage.MemoryBackend()  # fresh per test
        self.org = tsvc.create_organization(self.db, slug="st", name="ST")
        self.tid = tsvc.default_tenant(self.db, self.org.id).id

    def tearDown(self):
        self.db.close()

    def test_put_and_get(self):
        storage.put_object(self.db, self.tid, "docs/a.txt", b"hello")
        data = storage.get_object(self.db, self.tid, "docs/a.txt")
        self.assertEqual(data, b"hello")

    def test_versioning(self):
        storage.put_object(self.db, self.tid, "f.txt", b"v1")
        obj = storage.put_object(self.db, self.tid, "f.txt", b"v2")
        self.assertEqual(obj.current_version, 2)
        self.assertEqual(storage.get_object(self.db, self.tid, "f.txt"), b"v2")
        self.assertEqual(storage.get_object(self.db, self.tid, "f.txt", version=1), b"v1")
        self.assertEqual(len(storage.list_versions(self.db, obj.id)), 2)

    def test_encryption_roundtrip(self):
        obj = storage.put_object(self.db, self.tid, "sec.txt", b"secret", encrypt=True)
        self.assertTrue(obj.encrypted)
        # ciphertext on backend differs from plaintext
        ver = storage.list_versions(self.db, obj.id)[0]
        raw = storage._backend().get(ver.physical_uri)
        self.assertNotEqual(raw, b"secret")
        # decrypts correctly on read
        self.assertEqual(storage.get_object(self.db, self.tid, "sec.txt"), b"secret")

    def test_tenant_isolation(self):
        org2 = tsvc.create_organization(self.db, slug="st2", name="ST2")
        tid2 = tsvc.default_tenant(self.db, org2.id).id
        storage.put_object(self.db, self.tid, "shared.txt", b"a")
        storage.put_object(self.db, tid2, "shared.txt", b"b")
        self.assertEqual(storage.get_object(self.db, self.tid, "shared.txt"), b"a")
        self.assertEqual(storage.get_object(self.db, tid2, "shared.txt"), b"b")
        self.assertEqual(len(storage.list_objects(self.db, self.tid)), 1)

    def test_list_with_prefix(self):
        storage.put_object(self.db, self.tid, "reports/2024.pdf", b"x")
        storage.put_object(self.db, self.tid, "reports/2025.pdf", b"y")
        storage.put_object(self.db, self.tid, "misc/z.txt", b"z")
        self.assertEqual(len(storage.list_objects(self.db, self.tid, prefix="reports/")), 2)

    def test_signed_url_roundtrip(self):
        signed = storage.sign_url(self.tid, "default", "a.txt", expires_in=60)
        verified = storage.verify_signed_url(signed["token"])
        self.assertEqual(verified["tenant_id"], self.tid)
        self.assertEqual(verified["key"], "a.txt")

    def test_signed_url_tamper_rejected(self):
        import base64
        signed = storage.sign_url(self.tid, "default", "a.txt")
        decoded = base64.urlsafe_b64decode(signed["token"].encode()).decode()
        payload = decoded.rsplit(":", 1)[0]
        forged = base64.urlsafe_b64encode(f"{payload}:deadbeef".encode()).decode()
        with self.assertRaises(ValueError):
            storage.verify_signed_url(forged)

    def test_multipart_upload(self):
        up = storage.start_multipart(self.tid, "default", "big.bin")
        storage.upload_part(up, 1, b"AAA")
        storage.upload_part(up, 2, b"BBB")
        obj = storage.complete_multipart(self.db, up, self.tid, "big.bin")
        self.assertEqual(obj.size_bytes, 6)
        self.assertEqual(storage.get_object(self.db, self.tid, "big.bin"), b"AAABBB")

    def test_delete_object(self):
        storage.put_object(self.db, self.tid, "gone.txt", b"x")
        storage.delete_object(self.db, self.tid, "gone.txt")
        with self.assertRaises(FileNotFoundError):
            storage.get_object(self.db, self.tid, "gone.txt")

    def test_lifecycle_sweep(self):
        obj = storage.put_object(self.db, self.tid, "temp.txt", b"x", lifecycle_policy="ephemeral")
        obj.expires_at = datetime.utcnow() - timedelta(days=2)
        self.db.commit()
        removed = storage.run_lifecycle_sweep(self.db, tenant_id=self.tid)
        self.assertEqual(removed, 1)
        self.assertEqual(len(storage.list_objects(self.db, self.tid)), 0)

    def test_storage_usage_gb(self):
        storage.put_object(self.db, self.tid, "a", b"x" * 1024)
        gb = storage.storage_usage_gb(self.db, self.tid)
        self.assertGreater(gb, 0)


if __name__ == "__main__":
    unittest.main()
