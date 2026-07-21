"""Phase 4 Milestone 3 tests: the Explainable AI layer."""

import unittest

from backend.app.services.ml.explainability import explain_features
from backend.app.services.ml.explainability.registry import (
    get_explainer,
    registered_methods,
)
from backend.app.services.ml.features import feature_pipeline

STRONG_INPUT = {
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

DISTRESSED_INPUT = {
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


def _explain(engine_input, **kw):
    return explain_features(feature_pipeline.build_from_engine_input(engine_input), **kw)


class ExplanationShapeTest(unittest.TestCase):
    def test_full_explanation_payload(self):
        exp = _explain(STRONG_INPUT)
        for key in (
            "probability_of_default", "base_probability", "risk_score", "risk_grade",
            "summary", "contributions", "top_positive_contributors",
            "top_negative_contributors", "waterfall", "global_importance",
        ):
            self.assertIn(key, exp)
        self.assertTrue(exp["contributions"])
        self.assertTrue(exp["summary"])

    def test_methods_registered(self):
        methods = registered_methods()
        for m in ("contribution", "shap", "lime", "auto"):
            self.assertIn(m, methods)

    def test_contribution_fields(self):
        exp = _explain(DISTRESSED_INPUT)
        c = exp["contributions"][0]
        for key in ("feature", "label", "value", "contribution", "impact_pp",
                    "direction", "narrative"):
            self.assertIn(key, c)
        self.assertIn(c["direction"], ("increases_risk", "reduces_risk", "neutral"))


class ExplanationSemanticsTest(unittest.TestCase):
    def test_top_positive_are_risk_increasing(self):
        exp = _explain(DISTRESSED_INPUT)
        for c in exp["top_positive_contributors"]:
            self.assertEqual(c["direction"], "increases_risk")
            self.assertGreater(c["contribution"], 0)
        for c in exp["top_negative_contributors"]:
            self.assertEqual(c["direction"], "reduces_risk")
            self.assertLess(c["contribution"], 0)

    def test_prior_default_is_a_top_risk_driver(self):
        exp = _explain(DISTRESSED_INPUT)
        labels = [c["label"] for c in exp["top_positive_contributors"]]
        self.assertIn("Prior Defaults", labels)

    def test_narrative_language_is_business_readable(self):
        exp = _explain(STRONG_INPUT)
        joined = " ".join(c["narrative"] for c in exp["contributions"])
        self.assertTrue(
            "reduced overall risk" in joined or "increased overall risk" in joined
        )

    def test_waterfall_starts_at_base_and_ends_at_pd(self):
        exp = _explain(DISTRESSED_INPUT)
        wf = exp["waterfall"]
        self.assertEqual(wf[0]["label"], "Base rate")
        self.assertAlmostEqual(wf[0]["cumulative_pd"], exp["base_probability"], places=6)
        self.assertAlmostEqual(wf[-1]["cumulative_pd"], exp["probability_of_default"], places=6)

    def test_global_importance_ranked(self):
        exp = _explain(STRONG_INPUT)
        gi = exp["global_importance"]
        self.assertTrue(gi)
        importances = [g["importance"] for g in gi]
        self.assertEqual(importances, sorted(importances, reverse=True))

    def test_shap_and_lime_abstractions_resolve(self):
        shap_exp = _explain(STRONG_INPUT, method="shap")
        lime_exp = _explain(STRONG_INPUT, method="lime")
        # No trained model yet -> SHAP resolves to the additive-equivalent method.
        self.assertEqual(shap_exp["method"], "shap_additive_equivalent")
        self.assertEqual(lime_exp["method"], "lime_local_surrogate")
        # Same underlying additive attribution -> same PD.
        self.assertAlmostEqual(
            shap_exp["probability_of_default"], lime_exp["probability_of_default"], places=9
        )

    def test_auto_falls_back_to_contribution_when_untrained(self):
        explainer = get_explainer("auto", model_trained=False)
        self.assertEqual(explainer.method, "contribution")


if __name__ == "__main__":
    unittest.main()
