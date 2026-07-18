import unittest

from pydantic import ValidationError

from backend.app.schemas.enterprise import EnterpriseAssessmentRequest
from backend.app.services.enterprise_assessment import (
    compute_ratios,
    evaluate_enterprise_assessment,
)


STRONG = {
    "company_name": "Acme Corp",
    "industry": "Manufacturing",
    "business_type": "Private Limited",
    "years_in_business": 10,
    "employee_count": 120,
    "annual_revenue": 20000000,
    "gross_profit": 7000000,
    "net_profit": 2500000,
    "ebitda": 3500000,
    "operating_expenses": 3000000,
    "cash_and_cash_equivalents": 5000000,
    "accounts_receivable": 1500000,
    "accounts_payable": 900000,
    "inventory": 700000,
    "current_assets": 8000000,
    "current_liabilities": 2500000,
    "long_term_debt": 1500000,
    "short_term_debt": 500000,
    "interest_expense": 120000,
    "operating_cash_flow": 3000000,
    "free_cash_flow": 1800000,
    "net_worth": 8000000,
    "existing_emi": 50000,
    "credit_utilization": 20,
    "average_collection_period": 30,
    "cheque_bounce_count": 0,
    "existing_bank_loans": 1,
    "tax_compliance": "compliant",
    "gst_compliance": "compliant",
    "previous_defaults": "none",
    "industry_risk": "low",
    "geographical_risk": "low",
    "supplier_concentration": "diversified",
    "customer_concentration": "balanced",
    "business_expansion_stage": "mature",
}

WEAK = {
    "company_name": "Fragile LLC",
    "industry": "Retail",
    "business_type": "Proprietorship",
    "years_in_business": 1,
    "employee_count": 8,
    "annual_revenue": 1500000,
    "gross_profit": 300000,
    "net_profit": 10000,
    "ebitda": 60000,
    "operating_expenses": 1200000,
    "cash_and_cash_equivalents": 40000,
    "accounts_receivable": 900000,
    "accounts_payable": 800000,
    "inventory": 600000,
    "current_assets": 700000,
    "current_liabilities": 900000,
    "long_term_debt": 2500000,
    "short_term_debt": 1200000,
    "interest_expense": 400000,
    "operating_cash_flow": -500000,
    "free_cash_flow": -450000,
    "net_worth": 200000,
    "existing_emi": 25000,
    "credit_utilization": 95,
    "average_collection_period": 90,
    "cheque_bounce_count": 4,
    "existing_bank_loans": 4,
    "tax_compliance": "non_compliant",
    "gst_compliance": "non_compliant",
    "previous_defaults": "present",
    "industry_risk": "high",
    "geographical_risk": "high",
    "supplier_concentration": "concentrated",
    "customer_concentration": "concentrated",
    "business_expansion_stage": "startup",
}


class RatioEngineTests(unittest.TestCase):
    def test_computes_dscr_and_core_ratios(self):
        r = compute_ratios(STRONG)
        # DSCR = EBITDA / (interest + emi*12) = 3.5M / (120k + 600k) ~= 4.86
        self.assertAlmostEqual(r["dscr"], 3500000 / (120000 + 50000 * 12), places=2)
        self.assertAlmostEqual(r["current_ratio"], 8000000 / 2500000, places=2)
        self.assertGreater(r["gross_margin"], 0.3)

    def test_working_capital_defaults_to_ca_minus_cl(self):
        r = compute_ratios(STRONG)
        self.assertEqual(r["working_capital"], 8000000 - 2500000)


class ScoringTests(unittest.TestCase):
    def test_strong_company_scores_investment_grade(self):
        result = evaluate_enterprise_assessment(STRONG)
        self.assertGreaterEqual(result["enterprise_credit_score"], 700)
        # Calibrated PD keeps strong grades well below 2%.
        self.assertLess(result["probability_of_default"], 0.02)
        self.assertEqual(result["recommendation"]["decision"], "Approve")
        self.assertGreater(result["summary"]["recommended_loan_amount"], 0)

    def test_weak_company_is_penalised_and_declined(self):
        result = evaluate_enterprise_assessment(WEAK)
        self.assertLess(result["enterprise_credit_score"], 600)
        self.assertGreater(result["probability_of_default"], 0.10)
        self.assertEqual(result["recommendation"]["decision"], "Decline")
        self.assertEqual(result["summary"]["recommended_loan_amount"], 0)

    def test_result_exposes_health_dimensions(self):
        result = evaluate_enterprise_assessment(STRONG)
        health = result["health_metrics"]
        for dim in ("liquidity_health", "debt_health", "working_capital_health", "business_stability"):
            self.assertIn(dim, health)
            self.assertIn("score", health[dim])
            self.assertIn("label", health[dim])

    def test_backward_compatible_flat_keys_present(self):
        result = evaluate_enterprise_assessment(STRONG)
        for key in ("enterprise_credit_score", "risk_rating", "expected_loss", "explanations"):
            self.assertIn(key, result)


class ValidationTests(unittest.TestCase):
    def _nested_payload(self, **overrides):
        payload = {
            "business_profile": {
                "company_name": "Acme",
                "industry": "Manufacturing",
                "business_type": "Private Limited",
                "years_in_business": 10,
                "employee_count": 120,
                "head_office": "Mumbai",
                "country": "India",
            },
            "financials": {
                "annual_revenue": 20000000,
                "gross_profit": 7000000,
                "net_profit": 2500000,
                "ebitda": 3500000,
                "operating_expenses": 3000000,
                "cash_and_cash_equivalents": 5000000,
                "current_assets": 8000000,
                "current_liabilities": 2500000,
                "inventory": 700000,
                "accounts_receivable": 1500000,
                "accounts_payable": 900000,
                "long_term_debt": 1500000,
                "short_term_debt": 500000,
                "operating_cash_flow": 3000000,
            },
            "banking": {
                "average_monthly_balance": 620000,
                "average_monthly_inflow": 1450000,
                "average_monthly_outflow": 1300000,
                "existing_loans": 1,
                "credit_utilization": 20,
                "cheque_bounce_count": 0,
            },
            "risk_profile": {},
        }
        payload.update(overrides)
        return payload

    def test_valid_payload_flattens(self):
        req = EnterpriseAssessmentRequest(**self._nested_payload())
        flat = req.to_engine_input()
        self.assertEqual(flat["annual_revenue"], 20000000)
        self.assertEqual(flat["working_capital"], 8000000 - 2500000)

    def test_negative_revenue_rejected(self):
        payload = self._nested_payload()
        payload["financials"]["annual_revenue"] = -1
        with self.assertRaises(ValidationError):
            EnterpriseAssessmentRequest(**payload)

    def test_credit_utilization_above_100_rejected(self):
        payload = self._nested_payload()
        payload["banking"]["credit_utilization"] = 150
        with self.assertRaises(ValidationError):
            EnterpriseAssessmentRequest(**payload)

    def test_unrealistic_business_age_rejected(self):
        payload = self._nested_payload()
        payload["business_profile"]["years_in_business"] = 500
        with self.assertRaises(ValidationError):
            EnterpriseAssessmentRequest(**payload)


if __name__ == "__main__":
    unittest.main()
