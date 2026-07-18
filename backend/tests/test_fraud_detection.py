import unittest

from backend.app.services.fraud_detection import detect_fraud


class FraudDetectionTests(unittest.TestCase):
    def test_marks_high_risk_transactions(self):
        result = detect_fraud({"amount": 12000, "frequency": 65, "account_age": 1})
        self.assertTrue(result["fraud_detected"])
        self.assertGreaterEqual(result["fraud_score"], 0.7)
        self.assertIn("risk_reasons", result)

    def test_marks_low_risk_transactions(self):
        result = detect_fraud({"amount": 120, "frequency": 4, "account_age": 48})
        self.assertFalse(result["fraud_detected"])
        self.assertLess(result["fraud_score"], 0.3)


if __name__ == "__main__":
    unittest.main()
