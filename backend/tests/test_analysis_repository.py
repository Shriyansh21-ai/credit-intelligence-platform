""" tests: FinancialAnalysis persistence + versioning."""

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import Base
# Import model modules so their tables register on Base.metadata.
from backend.app.models import user  # noqa: F401
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import financial_analysis  # noqa: F401
from backend.app.services.financial_analysis import repository


def _payload(overall_score=72, flags=None):
    return {
        "period": {"label": "FY2024", "period_type": "annual", "fiscal_year": 2024},
        "statement": {"revenue": 1000},
        "overall_health": {"score": overall_score, "status": "good"},
        "health_scores": {
            "liquidity": {"score": 80, "status": "excellent"},
            "leverage": {"score": 60, "status": "moderate"},
            "growth": {"score": None, "status": "unavailable"},
        },
        "ratios": [{"key": "current_ratio", "value": 2.1}],
        "insights": [{"key": "x", "title": "t"}],
        "risk_flags": flags if flags is not None else [
            {"code": "low_dscr", "severity": "medium"},
            {"code": "operating_loss", "severity": "high"},
        ],
        "recommendations": [{"key": "reduce_debt"}],
        "engine_version": "1.0",
    }


class AnalysisRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_save_derives_headline_columns(self):
        rec = repository.save_analysis(
            self.db, user_id=1, assessment_id=10, analysis=_payload()
        )
        self.assertEqual(rec.version, 1)
        self.assertTrue(rec.is_current)
        self.assertEqual(rec.overall_health_score, 72)
        self.assertEqual(rec.liquidity_health, 80)
        self.assertIsNone(rec.growth_health)          # unavailable -> None
        self.assertEqual(rec.risk_flag_count, 2)
        self.assertEqual(rec.highest_severity, "high")  # most severe wins
        self.assertEqual(rec.fiscal_year, 2024)

    def test_versioning_supersedes_previous_current(self):
        repository.save_analysis(self.db, user_id=1, assessment_id=10, analysis=_payload(70))
        second = repository.save_analysis(self.db, user_id=1, assessment_id=10, analysis=_payload(75))
        self.assertEqual(second.version, 2)

        current = repository.get_current_for_assessment(self.db, 10)
        self.assertEqual(current.id, second.id)
        self.assertEqual(current.overall_health_score, 75)

        history = repository.history_for_assessment(self.db, 10)
        self.assertEqual(len(history), 2)
        self.assertEqual(sum(1 for h in history if h.is_current), 1)

    def test_ad_hoc_analysis_without_assessment(self):
        rec = repository.save_analysis(
            self.db, user_id=1, assessment_id=None, analysis=_payload()
        )
        self.assertIsNone(rec.assessment_id)
        self.assertEqual(rec.version, 1)

    def test_no_flags_leaves_severity_null(self):
        rec = repository.save_analysis(
            self.db, user_id=1, assessment_id=5, analysis=_payload(flags=[])
        )
        self.assertEqual(rec.risk_flag_count, 0)
        self.assertIsNone(rec.highest_severity)


if __name__ == "__main__":
    unittest.main()
