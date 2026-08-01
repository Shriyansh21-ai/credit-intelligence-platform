""" tests: primitives + FinancialStatement DTO + adapters."""

import unittest

from backend.app.services.financial_analysis.primitives import (
    UNAVAILABLE,
    as_float,
    divide,
    mean_ignoring_missing,
    pct_change,
    scale,
    score_status,
    status_from_thresholds,
)
from backend.app.services.financial_analysis.statement import (
    FinancialStatement,
    from_document_fields,
    from_engine_input,
    from_mapping,
)


class PrimitivesTest(unittest.TestCase):
    def test_as_float_coercions(self):
        self.assertEqual(as_float("1,234.50"), 1234.50)
        self.assertEqual(as_float("₹ 2,00,000"), 200000.0)
        self.assertEqual(as_float("(500)"), -500.0)
        self.assertEqual(as_float("45%"), 45.0)
        self.assertEqual(as_float(10), 10.0)
        self.assertIsNone(as_float(""))
        self.assertIsNone(as_float(None))
        self.assertIsNone(as_float("n/a"))
        self.assertIsNone(as_float(True))  # bool is not a number here

    def test_divide_guards_zero_and_missing(self):
        self.assertEqual(divide(10, 2), 5.0)
        self.assertIsNone(divide(10, 0))
        self.assertIsNone(divide(None, 2))
        self.assertIsNone(divide(10, None))

    def test_scale_bidirectional_and_missing(self):
        self.assertEqual(scale(1.5, 1.0, 2.0), 50.0)
        self.assertEqual(scale(0.0, 1.0, 2.0), 0.0)      # clamped
        self.assertEqual(scale(3.0, 1.0, 2.0), 100.0)    # clamped
        # lower-is-better: lo > hi
        self.assertEqual(scale(1.0, 6.0, 1.0), 100.0)
        self.assertIsNone(scale(None, 1.0, 2.0))

    def test_score_status_bands(self):
        self.assertEqual(score_status(90), "excellent")
        self.assertEqual(score_status(70), "good")
        self.assertEqual(score_status(50), "moderate")
        self.assertEqual(score_status(30), "weak")
        self.assertEqual(score_status(10), "critical")
        self.assertEqual(score_status(None), UNAVAILABLE)

    def test_status_from_thresholds(self):
        higher = [(2.0, "excellent"), (1.5, "good"), (1.0, "moderate"), (0, "critical")]
        self.assertEqual(status_from_thresholds(2.5, higher, higher_is_better=True), "excellent")
        self.assertEqual(status_from_thresholds(1.2, higher, higher_is_better=True), "moderate")
        self.assertEqual(status_from_thresholds(0.5, higher, higher_is_better=True), "critical")
        self.assertEqual(status_from_thresholds(None, higher), UNAVAILABLE)

    def test_mean_and_pct_change(self):
        self.assertEqual(mean_ignoring_missing([2.0, None, 4.0]), 3.0)
        self.assertIsNone(mean_ignoring_missing([None, None]))
        self.assertEqual(pct_change(110, 100), 0.1)
        self.assertIsNone(pct_change(110, 0))
        self.assertIsNone(pct_change(None, 100))


class DerivedFieldsTest(unittest.TestCase):
    def test_derived_relationships(self):
        s = FinancialStatement(
            revenue=1000, gross_profit=400, current_assets=800, current_liabilities=500,
            short_term_debt=100, long_term_debt=300, total_equity=600,
            interest_expense=50, existing_emi=10, operating_cash_flow=200,
            capital_expenditure=60,
        )
        self.assertEqual(s.total_debt, 400)
        self.assertEqual(s.working_capital, 300)
        self.assertEqual(s.cost_of_goods_sold, 600)          # revenue - gross_profit
        self.assertEqual(s.annual_debt_service, 50 + 120)    # interest + EMI*12
        self.assertEqual(s.free_cash_flow_value, 140)        # OCF - capex
        # estimated assets = equity + CL + LTD
        self.assertEqual(s.estimated_total_assets, 600 + 500 + 300)
        self.assertTrue(s.total_assets_is_estimated)

    def test_missing_inputs_stay_none(self):
        s = FinancialStatement(current_assets=800)  # no CL
        self.assertIsNone(s.working_capital)
        self.assertIsNone(s.total_debt)
        self.assertIsNone(s.annual_debt_service)
        self.assertIsNone(s.cost_of_goods_sold)


class AdaptersTest(unittest.TestCase):
    def test_from_engine_input(self):
        data = {
            "annual_revenue": 20000000,
            "gross_profit": 7000000,
            "net_profit": 2500000,
            "ebitda": 3500000,
            "cash_and_cash_equivalents": 5000000,
            "current_assets": 8000000,
            "current_liabilities": 2500000,
            "long_term_debt": 1500000,
            "short_term_debt": 500000,
            "net_worth": 8000000,
            "existing_emi": 50000,
            "financial_year": 2024,
        }
        s = from_engine_input(data)
        self.assertEqual(s.revenue, 20000000)
        self.assertEqual(s.cash, 5000000)
        self.assertEqual(s.total_equity, 8000000)
        self.assertEqual(s.total_debt, 2000000)
        self.assertEqual(s.period.fiscal_year, 2024)
        self.assertEqual(s.period.label, "FY2024")

    def test_from_document_fields_list(self):
        fields = [
            {"key": "revenue", "value": "1,000,000"},
            {"key": "cost_of_goods_sold", "value": "600000"},
            {"key": "current_assets", "value": 500000},
            {"key": "financial_year", "value": "FY2023-24"},
            {"key": "gst_number", "value": "27AAECS1234F1Z5"},  # ignored (not financial)
        ]
        s = from_document_fields(fields)
        self.assertEqual(s.revenue, 1000000)
        self.assertEqual(s.cogs, 600000)
        self.assertEqual(s.current_assets, 500000)
        self.assertEqual(s.gross_profit_value, 400000)  # revenue - cogs
        self.assertEqual(s.period.fiscal_year, 2023)

    def test_from_document_fields_mapping(self):
        s = from_document_fields({"revenue": "500", "net_profit": "50"})
        self.assertEqual(s.revenue, 500)
        self.assertEqual(s.net_profit, 50)

    def test_from_mapping_roundtrip(self):
        s = from_mapping({"revenue": 100, "unknown_key": 5, "period": {"fiscal_year": 2022}})
        self.assertEqual(s.revenue, 100)
        self.assertEqual(s.period.fiscal_year, 2022)
        self.assertNotIn("unknown_key", s.as_dict())


if __name__ == "__main__":
    unittest.main()
