""" tests: the enterprise feature engine (registry
builder, pipeline) — no database involved."""

import unittest

from backend.app.services.ml.features import feature_pipeline
from backend.app.services.ml.features.feature_registry import (
    CATEGORIES,
    FEATURE_SET_VERSION,
    feature_names,
    get_registry,
)

STRONG = {
    "revenue": 20_000_000, "gross_profit": 7_000_000, "net_profit": 2_500_000,
    "ebitda": 3_500_000, "operating_income": 3_000_000, "operating_expenses": 3_000_000,
    "cash": 5_000_000, "inventory": 700_000, "accounts_receivable": 1_500_000,
    "accounts_payable": 900_000, "current_assets": 8_000_000, "current_liabilities": 2_500_000,
    "short_term_debt": 500_000, "long_term_debt": 1_500_000, "total_equity": 8_000_000,
    "interest_expense": 120_000, "operating_cash_flow": 3_000_000, "free_cash_flow": 1_800_000,
}

PRIOR = {**STRONG, "revenue": 16_000_000, "net_profit": 1_800_000, "ebitda": 2_800_000}

# A full assessment-style context with banking + qualitative fields.
ENGINE_INPUT = {
    "annual_revenue": 20_000_000, "gross_profit": 7_000_000, "net_profit": 2_500_000,
    "ebitda": 3_500_000, "operating_expenses": 3_000_000, "cash_and_cash_equivalents": 5_000_000,
    "current_assets": 8_000_000, "current_liabilities": 2_500_000, "inventory": 700_000,
    "accounts_receivable": 1_500_000, "accounts_payable": 900_000,
    "long_term_debt": 1_500_000, "short_term_debt": 500_000, "operating_cash_flow": 3_000_000,
    "interest_expense": 120_000, "free_cash_flow": 1_800_000, "net_worth": 8_000_000,
    "average_monthly_balance": 2_000_000, "average_monthly_inflow": 3_000_000,
    "average_monthly_outflow": 2_400_000, "existing_emi": 100_000, "credit_utilization": 35.0,
    "cheque_bounce_count": 0, "existing_bank_loans": 1,
    "industry_risk": "low", "geographical_risk": "low",
    "supplier_concentration": "diversified", "customer_concentration": "balanced",
    "business_expansion_stage": "mature", "tax_compliance": "compliant",
    "gst_compliance": "compliant", "previous_defaults": "none",
    "years_in_business": 12, "employee_count": 200,
}

_FEATURE_KEYS = {
    "feature_name", "category", "description", "value", "unit",
    "version", "source", "confidence", "generated_time",
}


class FeatureContractTest(unittest.TestCase):
    def test_every_feature_carries_full_provenance(self):
        vector = feature_pipeline.build_from_mapping(STRONG)
        self.assertEqual(vector["feature_set_version"], FEATURE_SET_VERSION)
        self.assertEqual(vector["feature_count"], len(get_registry()))
        self.assertTrue(vector["features"])
        for feature in vector["features"]:
            self.assertEqual(set(feature), _FEATURE_KEYS)
            self.assertEqual(feature["version"], FEATURE_SET_VERSION)
            self.assertIsInstance(feature["confidence"], float)
            self.assertIsNotNone(feature["generated_time"])

    def test_all_sixteen_categories_present(self):
        vector = feature_pipeline.build_from_mapping(STRONG)
        self.assertEqual(len(CATEGORIES), 16)
        self.assertEqual(set(vector["features_by_category"]), set(CATEGORIES))
        for cat in CATEGORIES:
            self.assertGreater(len(vector["features_by_category"][cat]), 0, cat)

    def test_registry_names_are_unique(self):
        names = feature_names()
        self.assertEqual(len(names), len(set(names)))

    def test_registry_snapshot_is_embedded(self):
        vector = feature_pipeline.build_from_mapping(STRONG)
        registry = vector["registry"]
        self.assertEqual(registry["feature_count"], len(get_registry()))
        self.assertEqual(registry["feature_set_version"], FEATURE_SET_VERSION)


class FeatureValueTest(unittest.TestCase):
    def _by_name(self, vector):
        return {f["feature_name"]: f for f in vector["features"]}

    def test_ratio_values_match_ratio_engine(self):
        feats = self._by_name(feature_pipeline.build_from_mapping(STRONG))
        # current ratio = 8.0M / 2.5M = 3.2
        self.assertAlmostEqual(feats["current_ratio"]["value"], 3.2, places=3)
        # net margin = 2.5M / 20M = 0.125
        self.assertAlmostEqual(feats["net_margin"]["value"], 0.125, places=4)
        self.assertGreater(feats["current_ratio"]["confidence"], 0.0)

    def test_missing_inputs_are_honest_not_fabricated(self):
        feats = self._by_name(feature_pipeline.build_from_mapping(STRONG))
        # No banking context supplied -> banking features are None @ 0 confidence.
        self.assertIsNone(feats["avg_monthly_balance"]["value"])
        self.assertEqual(feats["avg_monthly_balance"]["confidence"], 0.0)
        # No prior period -> growth / trend features are unavailable.
        self.assertIsNone(feats["revenue_growth"]["value"])
        self.assertEqual(feats["revenue_growth"]["confidence"], 0.0)

    def test_growth_features_use_prior_period(self):
        feats = self._by_name(feature_pipeline.build_from_mapping(STRONG, previous=PRIOR))
        # (20M - 16M) / 16M = 0.25
        self.assertAlmostEqual(feats["revenue_growth"]["value"], 0.25, places=4)
        self.assertGreater(feats["revenue_growth"]["confidence"], 0.0)
        self.assertIsNotNone(feats["previous_revenue"]["value"])

    def test_engine_input_populates_banking_and_qualitative(self):
        feats = self._by_name(feature_pipeline.build_from_engine_input(ENGINE_INPUT))
        self.assertEqual(feats["avg_monthly_balance"]["value"], 2_000_000)
        self.assertAlmostEqual(feats["inflow_outflow_ratio"]["value"], 1.25, places=3)
        self.assertEqual(feats["industry_risk_score"]["value"], 0.20)
        self.assertEqual(feats["expansion_stage_score"]["value"], 0.90)
        self.assertEqual(feats["prior_defaults_flag"]["value"], 0.0)
        self.assertEqual(feats["compliance_score"]["value"], 1.0)

    def test_estimated_assets_discount_confidence(self):
        # No total_assets given -> asset-based features rely on the estimate and
        # are discounted, but still computed.
        feats = self._by_name(feature_pipeline.build_from_mapping(STRONG))
        roa = feats["return_on_assets"]
        self.assertIsNotNone(roa["value"])
        self.assertLess(roa["confidence"], 0.9)

    def test_coverage_summary_is_consistent(self):
        vector = feature_pipeline.build_from_engine_input(ENGINE_INPUT, previous=None)
        populated = sum(1 for f in vector["features"] if f["value"] is not None)
        self.assertEqual(vector["populated_count"], populated)
        self.assertAlmostEqual(
            vector["coverage"], populated / vector["feature_count"], places=4
        )


if __name__ == "__main__":
    unittest.main()
