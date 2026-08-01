""" tests: the deterministic Analyst Copilot credit memo."""

import unittest

from backend.app.services.ml.report import build_report_from_engine_input

STRONG = {
    "company_name": "Acme Manufacturing Ltd", "industry": "Manufacturing",
    "business_type": "private_limited", "years_in_business": 15, "employee_count": 300,
    "country": "India", "business_expansion_stage": "mature",
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
    "tax_compliance": "compliant", "gst_compliance": "compliant", "previous_defaults": "none",
}

DISTRESSED = {
    **STRONG,
    "company_name": "Struggle Retail Pvt", "industry": "Retail",
    "years_in_business": 2, "business_expansion_stage": "decline",
    "annual_revenue": 5_000_000, "gross_profit": 400_000, "net_profit": -300_000,
    "ebitda": 150_000, "cash_and_cash_equivalents": 50_000, "current_assets": 2_000_000,
    "current_liabilities": 3_200_000, "inventory": 1_800_000, "operating_cash_flow": -200_000,
    "interest_expense": 600_000, "free_cash_flow": -450_000, "net_worth": 800_000,
    "long_term_debt": 3_000_000, "short_term_debt": 2_000_000,
    "credit_utilization": 90.0, "cheque_bounce_count": 4, "industry_risk": "high",
    "tax_compliance": "non_compliant", "previous_defaults": "present",
}

_SECTIONS = (
    "executive_summary", "business_overview", "financial_summary", "credit_strengths",
    "weaknesses", "business_risks", "industry_risks", "financial_risks",
    "management_risks", "recommendation", "analyst_notes", "final_recommendation",
)


class AnalystReportTest(unittest.TestCase):
    def test_all_memo_sections_present(self):
        memo = build_report_from_engine_input(STRONG)
        for section in _SECTIONS:
            self.assertIn(section, memo)
        self.assertEqual(memo["report_type"], "enterprise_credit_memo")

    def test_business_overview_reflects_input(self):
        memo = build_report_from_engine_input(STRONG)
        bo = memo["business_overview"]
        self.assertEqual(bo["company_name"], "Acme Manufacturing Ltd")
        self.assertEqual(bo["industry"], "Manufacturing")

    def test_recommendation_block_complete(self):
        memo = build_report_from_engine_input(STRONG)
        rec = memo["recommendation"]
        for key in ("decision", "recommended_loan_amount", "recommended_interest_rate",
                    "recommended_tenure", "collateral", "monitoring_frequency"):
            self.assertIn(key, rec)

    def test_strong_borrower_has_strengths(self):
        memo = build_report_from_engine_input(STRONG)
        self.assertTrue(memo["credit_strengths"])

    def test_distressed_borrower_surfaces_risks_and_monitoring(self):
        memo = build_report_from_engine_input(DISTRESSED)
        self.assertTrue(memo["weaknesses"])
        total_risks = (len(memo["business_risks"]) + len(memo["industry_risks"])
                       + len(memo["financial_risks"]) + len(memo["management_risks"]))
        self.assertGreater(total_risks, 0)
        # Distress -> tighter monitoring than a strong name.
        self.assertIn(memo["recommendation"]["monitoring_frequency"], ("Monthly", "Quarterly"))
        self.assertGreater(memo["alerts_summary"]["alert_count"], 0)

    def test_executive_summary_is_narrative(self):
        memo = build_report_from_engine_input(STRONG)
        self.assertIn("probability of default", memo["executive_summary"])
        self.assertTrue(memo["final_recommendation"])


if __name__ == "__main__":
    unittest.main()
