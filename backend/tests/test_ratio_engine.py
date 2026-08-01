""" tests: the 20-ratio engine."""

import unittest

from backend.app.services.financial_analysis.ratio_engine import (
    compute_ratios,
    ratios_by_key,
)
from backend.app.services.financial_analysis.statement import FinancialStatement


def strong_statement() -> FinancialStatement:
    return FinancialStatement(
        revenue=20_000_000, gross_profit=7_000_000, net_profit=2_500_000,
        ebitda=3_500_000, operating_income=3_000_000, operating_expenses=3_000_000,
        cash=5_000_000, inventory=700_000, accounts_receivable=1_500_000,
        accounts_payable=900_000, current_assets=8_000_000, current_liabilities=2_500_000,
        short_term_debt=500_000, long_term_debt=1_500_000, total_equity=8_000_000,
        interest_expense=120_000, operating_cash_flow=3_000_000, free_cash_flow=1_800_000,
        existing_emi=50_000,
    )


class RatioEngineTest(unittest.TestCase):
    def test_computes_exactly_twenty_ratios(self):
        ratios = compute_ratios(strong_statement())
        self.assertEqual(len(ratios), 20)
        # Every ratio exposes the full contract.
        for r in ratios:
            d = r.as_dict()
            for field in ("value", "formula", "interpretation", "ideal_range", "status"):
                self.assertIn(field, d)

    def test_key_ratio_values(self):
        r = ratios_by_key(strong_statement())
        self.assertAlmostEqual(r["current_ratio"].value, 3.2, places=2)
        self.assertAlmostEqual(r["quick_ratio"].value, (8_000_000 - 700_000) / 2_500_000, places=4)
        self.assertAlmostEqual(r["debt_to_equity"].value, 2_000_000 / 8_000_000, places=4)
        self.assertAlmostEqual(r["net_margin"].value, 0.125, places=4)
        self.assertAlmostEqual(r["gross_margin"].value, 0.35, places=4)
        # DSCR = EBITDA / (interest + EMI*12) = 3.5M / (120k + 600k)
        self.assertAlmostEqual(r["dscr"].value, 3_500_000 / 720_000, places=4)

    def test_strong_statement_grades_well(self):
        r = ratios_by_key(strong_statement())
        self.assertEqual(r["current_ratio"].status, "excellent")
        self.assertIn(r["dscr"].status, ("excellent", "good"))
        self.assertEqual(r["working_capital"].status, "good")
        self.assertEqual(r["free_cash_flow"].status, "good")

    def test_missing_inputs_are_unavailable_not_fabricated(self):
        r = ratios_by_key(FinancialStatement(revenue=1_000_000))  # almost nothing
        self.assertIsNone(r["current_ratio"].value)
        self.assertEqual(r["current_ratio"].status, "unavailable")
        self.assertIsNone(r["dscr"].value)

    def test_zero_interest_is_excellent_coverage(self):
        s = FinancialStatement(ebitda=1_000_000, operating_income=900_000, interest_expense=0)
        r = ratios_by_key(s)
        # No interest obligation with positive earnings => excellent, not unavailable.
        self.assertEqual(r["interest_coverage"].status, "excellent")

    def test_negative_equity_suppresses_equity_ratios(self):
        s = FinancialStatement(net_profit=100_000, total_equity=-500_000, short_term_debt=300_000)
        r = ratios_by_key(s)
        self.assertIsNone(r["debt_to_equity"].value)
        self.assertIsNone(r["return_on_equity"].value)
        self.assertEqual(r["debt_to_equity"].status, "unavailable")

    def test_negative_working_capital_is_critical(self):
        s = FinancialStatement(current_assets=1_000_000, current_liabilities=1_800_000)
        r = ratios_by_key(s)
        self.assertEqual(r["working_capital"].value, -800_000)
        self.assertEqual(r["working_capital"].status, "critical")

    def test_negative_fcf_is_critical(self):
        s = FinancialStatement(free_cash_flow=-250_000)
        r = ratios_by_key(s)
        self.assertEqual(r["free_cash_flow"].status, "critical")


if __name__ == "__main__":
    unittest.main()
