"""Phase 4 Milestone 1 tests: versioned persistence of feature vectors."""

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import feature_vector  # noqa: F401
from backend.app.models import user  # noqa: F401
from backend.app.services.ml.features import feature_pipeline, feature_store
from backend.app.services.ml.features.feature_serializer import serialize_record

STRONG = {
    "revenue": 20_000_000, "gross_profit": 7_000_000, "net_profit": 2_500_000,
    "ebitda": 3_500_000, "operating_income": 3_000_000, "cash": 5_000_000,
    "inventory": 700_000, "accounts_receivable": 1_500_000, "accounts_payable": 900_000,
    "current_assets": 8_000_000, "current_liabilities": 2_500_000,
    "short_term_debt": 500_000, "long_term_debt": 1_500_000, "total_equity": 8_000_000,
    "interest_expense": 120_000, "operating_cash_flow": 3_000_000, "free_cash_flow": 1_800_000,
}


class FeatureStoreTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _save(self, assessment_id=1, user_id=1):
        db = self.Session()
        try:
            vector = feature_pipeline.build_from_mapping(STRONG)
            return feature_store.save_feature_vector(
                db, user_id=user_id, assessment_id=assessment_id, vector=vector
            )
        finally:
            db.close()

    def test_save_and_read_back(self):
        rec = self._save()
        self.assertEqual(rec.version, 1)
        self.assertTrue(rec.is_current)
        self.assertGreater(rec.feature_count, 0)
        self.assertEqual(rec.populated_count, len([f for f in rec.features if f["value"] is not None]))

        db = self.Session()
        try:
            current = feature_store.get_current_for_assessment(db, 1)
            self.assertEqual(current.id, rec.id)
            payload = serialize_record(current)
            self.assertEqual(payload["feature_count"], rec.feature_count)
            self.assertIn("features_by_category", payload)
        finally:
            db.close()

    def test_versioning_supersedes_previous(self):
        self._save()
        self._save()  # recompute -> version 2

        db = self.Session()
        try:
            current = feature_store.get_current_for_assessment(db, 1)
            self.assertEqual(current.version, 2)
            self.assertTrue(current.is_current)

            history = feature_store.history_for_assessment(db, 1)
            self.assertEqual(len(history), 2)
            self.assertEqual(sum(1 for r in history if r.is_current), 1)
        finally:
            db.close()

    def test_latest_for_user(self):
        self._save(assessment_id=1)
        self._save(assessment_id=2)
        db = self.Session()
        try:
            latest = feature_store.latest_for_user(db, 1)
            self.assertIsNotNone(latest)
            self.assertEqual(latest.user_id, 1)
        finally:
            db.close()

    def test_ad_hoc_vector_without_assessment(self):
        db = self.Session()
        try:
            vector = feature_pipeline.build_from_mapping(STRONG)
            rec = feature_store.save_feature_vector(
                db, user_id=5, assessment_id=None, vector=vector
            )
            self.assertEqual(rec.version, 1)
            self.assertIsNone(rec.assessment_id)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
