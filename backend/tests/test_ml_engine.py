"""Phase 4 Milestone 2 tests: the ML engine architecture (interface,
registry, deterministic estimator, inference service)."""

import unittest

from backend.app.services.ml import inference
from backend.app.services.ml.features import feature_pipeline
from backend.app.services.ml.models import (
    available_models,
    default_model_type,
    get_model,
)
from backend.app.services.ml.models.base import BaseRiskModel, ModelPrediction
from backend.app.services.ml.models.catalog import CATALOG

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


def _mapping(engine_input):
    return inference.features_to_mapping(feature_pipeline.build_from_engine_input(engine_input))


class RegistryTest(unittest.TestCase):
    def test_all_six_algorithms_plus_scorecard_registered(self):
        types = {m["model_type"] for m in available_models()}
        self.assertEqual(types, {
            "scorecard", "logistic_regression", "random_forest",
            "xgboost", "lightgbm", "catboost", "neural_network",
        })

    def test_default_is_scorecard(self):
        self.assertEqual(default_model_type(), "scorecard")
        self.assertTrue(any(m["is_default"] for m in available_models()))

    def test_every_model_implements_the_interface(self):
        for cls in CATALOG:
            model = cls()
            self.assertIsInstance(model, BaseRiskModel)
            meta = model.model_metadata()
            self.assertFalse(meta.trained)  # nothing trained yet
            self.assertEqual(meta.inference_mode, "deterministic_fallback")
            self.assertIsInstance(meta.backend_available, bool)

    def test_unknown_model_type_raises(self):
        with self.assertRaises(KeyError):
            get_model("nonexistent_model")

    def test_save_untrained_model_raises(self):
        with self.assertRaises(RuntimeError):
            get_model("scorecard").save_model()


class PredictionTest(unittest.TestCase):
    def test_proba_is_a_valid_distribution(self):
        model = get_model()
        proba = model.predict_proba(_mapping(STRONG_INPUT))
        self.assertEqual(len(proba), 2)
        self.assertAlmostEqual(sum(proba), 1.0, places=9)
        self.assertTrue(all(0.0 <= p <= 1.0 for p in proba))

    def test_strong_beats_distressed(self):
        strong = inference.run_inference(feature_pipeline.build_from_engine_input(STRONG_INPUT))
        weak = inference.run_inference(feature_pipeline.build_from_engine_input(DISTRESSED_INPUT))
        self.assertIsInstance(strong, ModelPrediction)
        self.assertLess(strong.probability_of_default, weak.probability_of_default)
        self.assertGreater(strong.risk_score, weak.risk_score)
        self.assertTrue(strong.approval)
        self.assertFalse(weak.approval)

    def test_contributions_have_correct_sign(self):
        weak = inference.run_inference(feature_pipeline.build_from_engine_input(DISTRESSED_INPUT))
        # Prior defaults are risk-increasing -> positive log-odds contribution.
        self.assertGreater(weak.contributions.get("prior_defaults_flag", 0), 0)
        strong = inference.run_inference(feature_pipeline.build_from_engine_input(STRONG_INPUT))
        # Strong current ratio is risk-reducing -> negative contribution.
        self.assertLess(strong.contributions.get("current_ratio", 0), 0)

    def test_determinism(self):
        a = inference.run_inference(feature_pipeline.build_from_engine_input(STRONG_INPUT))
        b = inference.run_inference(feature_pipeline.build_from_engine_input(STRONG_INPUT))
        self.assertEqual(a.probability_of_default, b.probability_of_default)
        self.assertEqual(a.risk_score, b.risk_score)

    def test_monotonic_in_leverage(self):
        model = get_model()
        base = _mapping(STRONG_INPUT)
        worse = dict(base)
        worse["debt_to_equity"] = (base.get("debt_to_equity") or 0) + 4.0
        self.assertGreater(
            model.predict_proba(worse)[1], model.predict_proba(base)[1]
        )

    def test_feature_importance_normalised(self):
        importance = get_model().feature_importance()
        self.assertTrue(importance)
        self.assertAlmostEqual(sum(importance.values()), 1.0, places=6)
        self.assertTrue(all(v >= 0 for v in importance.values()))

    def test_missing_features_contribute_zero(self):
        # An empty feature set collapses to the intercept PD, not an error.
        model = get_model()
        pd = model.predict_proba({})[1]
        self.assertTrue(0.0 < pd < 1.0)


class InferenceServiceTest(unittest.TestCase):
    def test_predict_from_vector_payload(self):
        vector = feature_pipeline.build_from_engine_input(STRONG_INPUT)
        payload = inference.predict_from_vector(vector)
        self.assertIn("probability_of_default", payload)
        self.assertIn("model_metadata", payload)
        self.assertIn("feature_importance", payload)
        self.assertEqual(payload["model_metadata"]["model_type"], "scorecard")

    def test_model_selection_is_configurable(self):
        payload = inference.predict_from_vector(
            feature_pipeline.build_from_engine_input(STRONG_INPUT),
            model_type="random_forest",
        )
        self.assertEqual(payload["model_metadata"]["model_type"], "random_forest")


if __name__ == "__main__":
    unittest.main()
