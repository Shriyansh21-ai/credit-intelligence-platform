import unittest

from backend.app.services.statement_extraction import extract_financial_summary


class StatementExtractionTests(unittest.TestCase):
    def test_extracts_key_financial_metrics_from_text(self):
        sample_text = """
        ABC Industries Financial Statement
        Revenue 12,500,000
        Gross Profit 3,200,000
        Net Profit 860,000
        Operating Expenses 2,100,000
        Cash 1,250,000
        Accounts Receivable 800,000
        Accounts Payable 450,000
        Inventory 600,000
        Current Assets 2,900,000
        Current Liabilities 1,200,000
        Long Term Debt 4,500,000
        Short Term Debt 750,000
        """

        result = extract_financial_summary(sample_text)

        self.assertEqual(result["annual_revenue"], 12500000)
        self.assertEqual(result["gross_profit"], 3200000)
        self.assertEqual(result["net_profit"], 860000)
        self.assertEqual(result["operating_expenses"], 2100000)
        self.assertEqual(result["cash_and_cash_equivalents"], 1250000)
        self.assertEqual(result["accounts_receivable"], 800000)
        self.assertEqual(result["accounts_payable"], 450000)
        self.assertEqual(result["inventory"], 600000)
        self.assertEqual(result["current_assets"], 2900000)
        self.assertEqual(result["current_liabilities"], 1200000)
        self.assertEqual(result["long_term_debt"], 4500000)
        self.assertEqual(result["short_term_debt"], 750000)


if __name__ == "__main__":
    unittest.main()
