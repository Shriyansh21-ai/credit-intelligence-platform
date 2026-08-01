""" tests: the trend engine."""

import unittest

from backend.app.services.financial_analysis.statement import FinancialStatement, Period
from backend.app.services.financial_analysis.trend_engine import (
    DECLINING, IMPROVING, INSUFFICIENT, compute_trends,
)


def _stmt(year, revenue, net_profit, total_debt=None):
    return FinancialStatement(
        revenue=revenue, net_profit=net_profit,
        short_term_debt=total_debt, long_term_debt=0 if total_debt is not None else None,
        period=Period(label=f"FY{year}", period_type="annual", fiscal_year=year),
    )


class TrendEngineTest(unittest.TestCase):
    def test_single_period_is_insufficient(self):
        t = compute_trends([_stmt(2024, 1_000_000, 100_000)])
        self.assertEqual(t["period_count"], 1)
        self.assertFalse(t["sufficient_data"])
        self.assertEqual(t["metrics"]["revenue"]["direction"], INSUFFICIENT)
        self.assertIsNone(t["metrics"]["revenue"]["cagr"])

    def test_growing_revenue_trend(self):
        t = compute_trends([
            _stmt(2022, 1_000_000, 80_000),
            _stmt(2023, 1_200_000, 110_000),
            _stmt(2024, 1_500_000, 150_000),
        ])
        rev = t["metrics"]["revenue"]
        self.assertEqual(rev["direction"], IMPROVING)
        self.assertEqual(len(rev["series"]), 3)
        self.assertEqual(len(rev["changes"]), 2)
        # CAGR over 2 intervals: (1.5M/1.0M)^(1/2) - 1 ~ 0.2247
        self.assertAlmostEqual(rev["cagr"], (1_500_000 / 1_000_000) ** 0.5 - 1, places=3)

    def test_orders_unsorted_input_by_year(self):
        t = compute_trends([
            _stmt(2024, 1_500_000, 150_000),
            _stmt(2022, 1_000_000, 80_000),
            _stmt(2023, 1_200_000, 110_000),
        ])
        self.assertEqual(t["periods"], ["FY2022", "FY2023", "FY2024"])

    def test_rising_debt_reads_as_declining(self):
        t = compute_trends([
            _stmt(2023, 1_000_000, 100_000, total_debt=200_000),
            _stmt(2024, 1_100_000, 90_000, total_debt=400_000),
        ])
        # total_debt is lower-is-better, so a rise is "declining" health.
        self.assertEqual(t["metrics"]["total_debt"]["direction"], DECLINING)

    def test_missing_base_yields_no_growth(self):
        t = compute_trends([
            _stmt(2023, 0, 100_000),          # zero base -> undefined growth
            _stmt(2024, 1_100_000, 90_000),
        ])
        self.assertIsNone(t["metrics"]["revenue"]["changes"][0]["change"])


if __name__ == "__main__":
    unittest.main()
