import unittest

from backend.app.services.credit_analyst_report import build_credit_analyst_report


class CreditAnalystReportTests(unittest.TestCase):
    def test_builds_personal_report(self):
        payload = {
            "Age": 32,
            "Sex": "male",
            "Job": 2,
            "Housing": "own",
            "Saving accounts": "little",
            "Checking account": "moderate",
            "Credit amount": 5000,
            "Duration": 24,
            "Purpose": "car",
        }
        report = build_credit_analyst_report(payload, report_type="personal")
        self.assertEqual(report["report_type"], "personal")
        self.assertIn("summary", report)
        self.assertIn("recommendations", report)
        self.assertIn("ai_analysis", report)

    def test_builds_enterprise_report(self):
        payload = {
            "company_name": "Acme",
            "industry": "Manufacturing",
            "business_type": "Private Limited",
            "years_in_business": 8,
            "employee_count": 50,
            "annual_revenue": 12000000,
            "gross_profit": 3000000,
            "net_profit": 700000,
            "ebitda": 900000,
            "operating_expenses": 1500000,
            "cash_and_cash_equivalents": 600000,
            "accounts_receivable": 1200000,
            "accounts_payable": 700000,
            "inventory": 400000,
            "current_assets": 2000000,
            "current_liabilities": 1000000,
            "long_term_debt": 1800000,
            "short_term_debt": 600000,
            "net_worth": 2000000,
            "interest_expense": 100000,
            "operating_cash_flow": 800000,
            "free_cash_flow": 300000,
            "credit_utilization": 25,
            "cheque_bounce_count": 0,
            "existing_bank_loans": 1,
            "average_monthly_balance": 500000,
            "average_monthly_inflow": 1000000,
            "average_monthly_outflow": 800000,
            "gst_filing_consistency": "consistent",
            "tax_filing_status": "compliant",
            "past_defaults": "none",
            "legal_cases": "none",
            "wilful_default": "no",
            "director_credit_history": "good",
            "industry_risk": "low",
            "geographical_risk": "low",
            "political_risk": "low",
            "supplier_concentration": "diversified",
            "customer_concentration": "balanced",
        }
        report = build_credit_analyst_report(payload, report_type="enterprise")
        self.assertEqual(report["report_type"], "enterprise")
        self.assertIn("summary", report)
        self.assertIn("recommendations", report)


if __name__ == "__main__":
    unittest.main()
