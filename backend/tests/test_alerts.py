""" tests: the Early Warning System."""

import unittest

from backend.app.services.ml.alerts import scan
from backend.app.services.ml.features import feature_pipeline

HEALTHY = {
    "annual_revenue": 20_000_000, "gross_profit": 7_000_000, "net_profit": 2_500_000,
    "ebitda": 3_500_000, "operating_expenses": 3_000_000, "cash_and_cash_equivalents": 5_000_000,
    "current_assets": 8_000_000, "current_liabilities": 2_500_000, "inventory": 700_000,
    "accounts_receivable": 1_500_000, "accounts_payable": 900_000,
    "long_term_debt": 1_500_000, "short_term_debt": 500_000, "operating_cash_flow": 3_000_000,
    "interest_expense": 120_000, "free_cash_flow": 1_800_000, "net_worth": 8_000_000,
    "average_monthly_balance": 2_000_000, "average_monthly_inflow": 3_000_000,
    "average_monthly_outflow": 2_400_000, "existing_emi": 100_000, "credit_utilization": 30.0,
    "cheque_bounce_count": 0, "industry_risk": "low", "geographical_risk": "low",
    "supplier_concentration": "diversified", "customer_concentration": "diversified",
    "business_expansion_stage": "mature", "tax_compliance": "compliant",
    "gst_compliance": "compliant", "previous_defaults": "none",
    "years_in_business": 15, "employee_count": 300,
}

DISTRESSED = {
    "annual_revenue": 5_000_000, "gross_profit": 400_000, "net_profit": -300_000,
    "ebitda": 150_000, "operating_expenses": 3_500_000, "cash_and_cash_equivalents": 50_000,
    "current_assets": 2_000_000, "current_liabilities": 3_200_000, "inventory": 1_800_000,
    "accounts_receivable": 2_000_000, "accounts_payable": 1_500_000,
    "long_term_debt": 3_000_000, "short_term_debt": 2_000_000, "operating_cash_flow": -200_000,
    "interest_expense": 600_000, "free_cash_flow": -450_000, "net_worth": 800_000,
    "average_monthly_balance": 100_000, "average_monthly_inflow": 400_000,
    "average_monthly_outflow": 500_000, "existing_emi": 200_000, "credit_utilization": 90.0,
    "cheque_bounce_count": 4, "industry_risk": "high", "geographical_risk": "high",
    "supplier_concentration": "concentrated", "customer_concentration": "concentrated",
    "business_expansion_stage": "decline", "tax_compliance": "non_compliant",
    "gst_compliance": "partial", "previous_defaults": "present",
    "years_in_business": 2, "employee_count": 20,
}


def _scan(engine_input):
    return scan(feature_pipeline.build_from_engine_input(engine_input), engine_input=engine_input)


class AlertEngineTest(unittest.TestCase):
    def test_healthy_borrower_has_few_or_no_alerts(self):
        result = _scan(HEALTHY)
        # A strong profile should not trip critical/high alerts.
        highs = [a for a in result["alerts"] if a["severity"] in ("critical", "high")]
        self.assertEqual(highs, [])

    def test_distressed_borrower_raises_multiple_alerts(self):
        result = _scan(DISTRESSED)
        self.assertGreater(result["alert_count"], 3)
        self.assertEqual(result["highest_severity"], "critical")

    def test_alerts_sorted_by_priority(self):
        result = _scan(DISTRESSED)
        priorities = [a["priority"] for a in result["alerts"]]
        self.assertEqual(priorities, sorted(priorities))

    def test_alert_fields_complete(self):
        result = _scan(DISTRESSED)
        a = result["alerts"][0]
        for key in ("alert_type", "category", "severity", "priority", "title",
                    "business_impact", "suggested_action", "timeline", "evidence"):
            self.assertIn(key, a)

    def test_prior_default_is_critical(self):
        result = _scan(DISTRESSED)
        types = {a["alert_type"]: a for a in result["alerts"]}
        self.assertIn("prior_defaults", types)
        self.assertEqual(types["prior_defaults"]["severity"], "critical")

    def test_cheque_bounce_fraud_indicator(self):
        result = _scan(DISTRESSED)
        types = {a["alert_type"] for a in result["alerts"]}
        self.assertIn("fraud_indicators", types)

    def test_by_severity_counts(self):
        result = _scan(DISTRESSED)
        self.assertEqual(
            sum(result["by_severity"].values()), result["alert_count"]
        )

    def test_missing_data_does_not_fabricate_alerts(self):
        # Empty feature set -> no signals present -> no alerts.
        result = scan({}, engine_input={})
        self.assertEqual(result["alert_count"], 0)


if __name__ == "__main__":
    unittest.main()
