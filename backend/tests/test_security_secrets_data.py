import unittest

from backend.app.services.security_compliance import data_protection, secrets


class SecretInventoryTest(unittest.TestCase):
    def test_inventory_lists_managed_secrets(self):
        res = secrets.secret_inventory()
        names = {i["name"] for i in res["inventory"]}
        for expected in ("SECRET_KEY", "JWT_SECRET_KEY", "ENCRYPTION_KEY",
                         "CONNECTOR_MASTER_KEY", "DATABASE_URL"):
            self.assertIn(expected, names)

    def test_never_returns_values(self):
        res = secrets.secret_inventory()
        for item in res["inventory"]:
            # only metadata keys, never a raw value
            self.assertNotIn("value", item)
            self.assertIn("status", item)
            self.assertIn(item["status"], ("configured", "weak", "default", "missing"))

    def test_dev_default_secret_flagged_critical(self):
        res = secrets.secret_inventory()
        codes = [f["code"] for f in res["findings"]]
        self.assertIn("SECRET-SECRET_KEY", codes)
        self.assertTrue(any(f["severity"] == "critical" for f in res["findings"]))

    def test_rotation_documented(self):
        res = secrets.secret_inventory()
        self.assertTrue(res["key_rotation_supported"])
        self.assertIn("field_encryption", res["rotation"])
        self.assertIn("jwt", res["rotation"])

    def test_provider_options(self):
        res = secrets.secret_inventory()
        self.assertIn(res["provider"], res["provider_options"])


class DataProtectionTest(unittest.TestCase):
    def test_classifications(self):
        levels = {c["level"] for c in data_protection.data_classification()}
        self.assertEqual(levels, {"public", "internal", "confidential", "restricted"})

    def test_pii_catalog_covers_sensitive_fields(self):
        fields = {p["field"] for p in data_protection.pii_catalog()}
        for expected in ("email", "phone", "password", "pan", "aadhaar",
                         "bank_account", "card_number"):
            self.assertIn(expected, fields)

    def test_restricted_fields_require_encryption(self):
        for p in data_protection.pii_catalog():
            if p["classification"] == "restricted":
                self.assertIn(p["encryption"], ("required", "hashed (bcrypt)"))

    def test_masking_demo_masks(self):
        demo = data_protection.masking_demo()
        self.assertNotIn("jane.doe@example.com", demo["email"])
        self.assertIn("***", demo["email"])
        self.assertTrue(demo["pan"].startswith("AB"))
        self.assertNotIn("ABCDE1234F", demo["pan"])
        self.assertNotIn("jane.doe@example.com", demo["free_text"])

    def test_encryption_controls_present(self):
        controls = data_protection.encryption_controls()
        self.assertIn("field_encryption", controls)
        self.assertIn("key_hierarchy", controls)
        self.assertGreaterEqual(len(controls["key_hierarchy"]), 3)

    def test_retention_catalog(self):
        retention = data_protection.retention_catalog()
        cats = {r["category"] for r in retention}
        self.assertIn("audit_log", cats)
        self.assertIn("kyc_document", cats)

    def test_report_score_bounded(self):
        res = data_protection.data_protection_report()
        self.assertGreaterEqual(res["score"], 0)
        self.assertLessEqual(res["score"], 100)
        self.assertGreater(res["restricted_field_count"], 0)


if __name__ == "__main__":
    unittest.main()
