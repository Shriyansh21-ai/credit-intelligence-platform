""" tests: the scenario simulator."""

import unittest

from backend.app.services.ml.scenario import (
    available_factors,
    simulate,
    simulate_many,
)
from backend.app.services.ml.scenario.factors import apply_adjustments

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


class FactorTest(unittest.TestCase):
    def test_all_required_factors_available(self):
        names = {f["factor"] for f in available_factors()}
        for required in (
            "revenue_change", "debt_change", "add_collateral", "ebitda_change",
            "interest_rate_increase", "inflation_increase", "working_capital_reduction",
            "customer_loss", "currency_fluctuation", "commodity_price_change",
            "supply_chain_delay",
        ):
            self.assertIn(required, names)

    def test_adjustments_do_not_mutate_input(self):
        before = dict(BASE)
        apply_adjustments(BASE, [{"factor": "revenue_change", "value": -20}])
        self.assertEqual(BASE, before)

    def test_revenue_drop_scales_linked_lines(self):
        adjusted = apply_adjustments(BASE, [{"factor": "revenue_change", "value": -25}])
        self.assertAlmostEqual(adjusted["annual_revenue"], 15_000_000, places=2)
        self.assertAlmostEqual(adjusted["ebitda"], 2_625_000, places=2)

    def test_unknown_factor_ignored(self):
        adjusted = apply_adjustments(BASE, [{"factor": "does_not_exist", "value": 5}])
        self.assertEqual(adjusted["annual_revenue"], BASE["annual_revenue"])


class SimulateTest(unittest.TestCase):
    def test_baseline_scenario_delta_shape(self):
        result = simulate(BASE, [{"factor": "revenue_change", "value": -30}])
        self.assertIn("baseline", result)
        self.assertIn("scenario", result)
        self.assertIn("delta", result)
        for key in ("enterprise_credit_score", "probability_of_default", "expected_loss"):
            self.assertIn(key, result["baseline"])

    def test_adverse_scenario_worsens_risk(self):
        result = simulate(BASE, [
            {"factor": "revenue_change", "value": -40},
            {"factor": "interest_rate_increase", "value": 4},
            {"factor": "debt_change", "value": 50},
        ])
        d = result["delta"]
        self.assertLess(result["scenario"]["enterprise_credit_score"],
                        result["baseline"]["enterprise_credit_score"])
        self.assertGreaterEqual(d["probability_of_default"], 0)
        self.assertLessEqual(d["enterprise_credit_score"], 0)

    def test_favourable_scenario_improves_risk(self):
        result = simulate(BASE, [
            {"factor": "add_collateral", "value": 5_000_000},
            {"factor": "debt_change", "value": -40},
        ])
        self.assertGreaterEqual(
            result["scenario"]["enterprise_credit_score"],
            result["baseline"]["enterprise_credit_score"],
        )

    def test_delta_flags(self):
        result = simulate(BASE, [{"factor": "revenue_change", "value": 0}])
        # A no-op change leaves grade and decision unchanged.
        self.assertFalse(result["delta"]["risk_grade_changed"])
        self.assertFalse(result["delta"]["decision_changed"])

    def test_simulate_many_shares_baseline(self):
        out = simulate_many(BASE, [
            [{"factor": "revenue_change", "value": -10}],
            [{"factor": "revenue_change", "value": -50}],
        ])
        self.assertEqual(len(out["scenarios"]), 2)
        # Deeper revenue cut -> lower score than the milder cut.
        self.assertLess(
            out["scenarios"][1]["scenario"]["enterprise_credit_score"],
            out["scenarios"][0]["scenario"]["enterprise_credit_score"],
        )


if __name__ == "__main__":
    unittest.main()
