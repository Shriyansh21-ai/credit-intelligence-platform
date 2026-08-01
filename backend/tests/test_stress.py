""" tests: enterprise stress testing."""

import unittest

from backend.app.services.ml.stress import available_scenarios, run_stress_test

BASE = {
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
    "years_in_business": 15, "employee_count": 300, "working_capital": 5_500_000,
}

_REQUIRED = {
    "economic_recession", "high_inflation", "interest_rate_shock", "pandemic",
    "supply_chain_collapse", "commodity_crisis", "sector_slowdown",
    "currency_crisis", "demand_reduction",
}


class StressScenarioTest(unittest.TestCase):
    def test_all_required_scenarios(self):
        names = {s["name"] for s in available_scenarios()}
        self.assertTrue(_REQUIRED.issubset(names))


class StressTestEngineTest(unittest.TestCase):
    def setUp(self):
        self.result = run_stress_test(BASE)

    def test_four_regulatory_cases(self):
        for case in ("base_case", "optimistic_case", "expected_case", "worst_case"):
            self.assertIn(case, self.result)
            self.assertIn("snapshot", self.result[case])

    def test_case_ordering_by_severity(self):
        base = self.result["base_case"]["snapshot"]["enterprise_credit_score"]
        opt = self.result["optimistic_case"]["snapshot"]["enterprise_credit_score"]
        exp = self.result["expected_case"]["snapshot"]["enterprise_credit_score"]
        worst = self.result["worst_case"]["snapshot"]["enterprise_credit_score"]
        # Worse cases should not score better than milder ones.
        self.assertLessEqual(worst, exp)
        self.assertLessEqual(exp, opt)
        self.assertLessEqual(exp, base)

    def test_worst_case_raises_expected_loss(self):
        base_el = self.result["base_case"]["snapshot"]["expected_loss"]
        worst_el = self.result["worst_case"]["snapshot"]["expected_loss"]
        self.assertGreaterEqual(worst_el, base_el)

    def test_comparison_series_present(self):
        comp = self.result["comparison"]
        self.assertIn("by_case", comp)
        self.assertIn("by_scenario", comp)
        self.assertIn("probability_of_default", comp["by_case"])
        # by_scenario is ranked by worst-case expected loss (descending).
        els = [s["worst_expected_loss"] for s in comp["by_scenario"]]
        self.assertEqual(els, sorted(els, reverse=True))

    def test_per_scenario_detail(self):
        self.assertTrue(self.result["scenarios"])
        for scn in self.result["scenarios"]:
            self.assertIn("cases", scn)
            self.assertEqual(set(scn["cases"]), {"optimistic", "expected", "worst"})

    def test_subset_selection(self):
        result = run_stress_test(BASE, ["high_inflation"])
        self.assertEqual(len(result["scenarios"]), 1)
        self.assertEqual(result["scenarios"][0]["name"], "high_inflation")

    def test_unknown_scenario_falls_back_to_all(self):
        result = run_stress_test(BASE, ["not_a_scenario"])
        self.assertEqual(len(result["scenarios"]), len(available_scenarios()))


if __name__ == "__main__":
    unittest.main()
