"""Milestone 3 tests: health, insight, risk-flag and recommendation engines."""

import unittest

from backend.app.services.financial_analysis.health_engine import (
    BUSINESS_STABILITY, GROWTH, LIQUIDITY, compute_health, overall_health,
)
from backend.app.services.financial_analysis.insight_engine import generate_insights
from backend.app.services.financial_analysis.ratio_engine import (
    compute_ratios, ratios_by_key,
)
from backend.app.services.financial_analysis.recommendation_engine import (
    generate_recommendations,
)
from backend.app.services.financial_analysis.risk_flag_engine import detect_risk_flags
from backend.app.services.financial_analysis.statement import FinancialStatement


def strong() -> FinancialStatement:
    return FinancialStatement(
        revenue=20_000_000, gross_profit=7_000_000, net_profit=2_500_000,
        ebitda=3_500_000, operating_income=3_000_000, operating_expenses=3_000_000,
        cash=5_000_000, inventory=700_000, accounts_receivable=1_500_000,
        accounts_payable=900_000, current_assets=8_000_000, current_liabilities=2_500_000,
        short_term_debt=500_000, long_term_debt=1_500_000, total_equity=8_000_000,
        interest_expense=120_000, operating_cash_flow=3_000_000, free_cash_flow=1_800_000,
        existing_emi=50_000,
    )


def distressed() -> FinancialStatement:
    return FinancialStatement(
        revenue=5_000_000, gross_profit=400_000, net_profit=-300_000,
        ebitda=150_000, operating_income=-100_000, operating_expenses=3_500_000,
        cash=50_000, inventory=1_800_000, accounts_receivable=2_000_000,
        accounts_payable=1_500_000, current_assets=2_000_000, current_liabilities=3_200_000,
        short_term_debt=2_000_000, long_term_debt=3_000_000, total_equity=800_000,
        interest_expense=600_000, operating_cash_flow=-200_000, free_cash_flow=-450_000,
        existing_emi=80_000,
    )


class HealthEngineTest(unittest.TestCase):
    def test_seven_dimensions_and_statuses(self):
        h = compute_health(strong())
        self.assertEqual(set(h), {
            "liquidity", "profitability", "leverage", "efficiency",
            "cash_flow", "business_stability", "growth",
        })
        self.assertIn(h[LIQUIDITY].status, ("excellent", "good"))
        # No context / no prior period => unavailable, not fabricated.
        self.assertEqual(h[BUSINESS_STABILITY].status, "unavailable")
        self.assertEqual(h[GROWTH].status, "unavailable")

    def test_stability_and_growth_with_inputs(self):
        h = compute_health(
            strong(),
            context={"years_in_business": 12, "employee_count": 200,
                     "business_expansion_stage": "mature"},
            previous=FinancialStatement(revenue=16_000_000, net_profit=1_800_000, ebitda=2_800_000),
        )
        self.assertIsNotNone(h[BUSINESS_STABILITY].score)
        self.assertIsNotNone(h[GROWTH].score)
        self.assertIn(h[GROWTH].status, ("excellent", "good"))

    def test_overall_health_ranks_strong_above_distressed(self):
        strong_overall = overall_health(compute_health(strong()))
        weak_overall = overall_health(compute_health(distressed()))
        self.assertGreater(strong_overall.score, weak_overall.score)
        self.assertIn(weak_overall.status, ("weak", "critical", "moderate"))


class InsightEngineTest(unittest.TestCase):
    def test_insights_have_why_and_sentiment(self):
        ratios = compute_ratios(distressed())
        insights = generate_insights(ratios, compute_health(distressed()))
        self.assertTrue(insights)
        self.assertTrue(any(i.sentiment == "negative" for i in insights))
        for i in insights:
            self.assertTrue(i.detail)  # the "why"

    def test_strong_business_surfaces_positive_insights(self):
        ratios = compute_ratios(strong())
        insights = generate_insights(ratios, compute_health(strong()))
        self.assertTrue(any(i.sentiment == "positive" for i in insights))


class RiskFlagEngineTest(unittest.TestCase):
    def test_distressed_raises_expected_flags(self):
        r = ratios_by_key(distressed())
        codes = {f.code for f in detect_risk_flags(distressed(), r)}
        self.assertIn("negative_working_capital", codes)
        self.assertIn("low_liquidity", codes)
        self.assertIn("cash_flow_deficit", codes)
        self.assertIn("operating_loss", codes)
        self.assertIn("low_interest_coverage", codes)

    def test_flags_carry_reason_and_recommendation(self):
        r = ratios_by_key(distressed())
        for flag in detect_risk_flags(distressed(), r):
            self.assertTrue(flag.reason)
            self.assertTrue(flag.recommendation)
            self.assertIn(flag.severity, ("critical", "high", "medium", "low"))

    def test_strong_business_has_few_flags(self):
        r = ratios_by_key(strong())
        self.assertEqual(detect_risk_flags(strong(), r), [])


class RecommendationEngineTest(unittest.TestCase):
    def test_distressed_recommendations(self):
        r = ratios_by_key(distressed())
        h = compute_health(distressed())
        keys = {rec.key for rec in generate_recommendations(r, h)}
        self.assertIn("reduce_debt", keys)
        self.assertIn("increase_operating_cash_flow", keys)

    def test_healthy_business_gets_maintain(self):
        r = ratios_by_key(strong())
        h = compute_health(strong())
        recs = generate_recommendations(r, h)
        self.assertEqual([rec.key for rec in recs], ["maintain"])


if __name__ == "__main__":
    unittest.main()
