""" tests: Financial Analysis API routes.

Uses an isolated FastAPI app mounting only the analysis router with overridden
DB and auth dependencies, so the suite stays fast and hermetic.
"""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import financial_analysis  # noqa: F401
from backend.app.models import user  # noqa: F401
from backend.app.routes import analysis as analysis_routes
from backend.app.services.financial_analysis import analysis_service, repository


class _FakeUser:
    def __init__(self, uid):
        self.id = uid


STRONG_FINANCIALS = {
    "revenue": 20_000_000, "gross_profit": 7_000_000, "net_profit": 2_500_000,
    "ebitda": 3_500_000, "operating_income": 3_000_000, "cash": 5_000_000,
    "inventory": 700_000, "accounts_receivable": 1_500_000, "accounts_payable": 900_000,
    "current_assets": 8_000_000, "current_liabilities": 2_500_000,
    "short_term_debt": 500_000, "long_term_debt": 1_500_000, "total_equity": 8_000_000,
    "interest_expense": 120_000, "operating_cash_flow": 3_000_000, "free_cash_flow": 1_800_000,
}


class AnalysisApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,  # one shared in-memory DB across all connections
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        app = FastAPI()
        app.include_router(analysis_routes.router)

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        self.user = _FakeUser(1)
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.app = app
        self.client = TestClient(app)

    def _seed(self, assessment_id=1, user_id=1):
        db = self.Session()
        try:
            analysis = analysis_service.analyze_mapping(STRONG_FINANCIALS)
            rec = repository.save_analysis(
                db, user_id=user_id, assessment_id=assessment_id, analysis=analysis
            )
            return rec.id
        finally:
            db.close()

    def test_compute_endpoint(self):
        resp = self.client.post("/analysis/compute", json={"financials": STRONG_FINANCIALS})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["ratios"]), 20)
        self.assertIn("overall_health", body)
        self.assertIn("health_scores", body)

    def test_compute_requires_a_source(self):
        resp = self.client.post("/analysis/compute", json={})
        self.assertEqual(resp.status_code, 422)

    def test_compute_persist(self):
        resp = self.client.post(
            "/analysis/compute",
            json={"financials": STRONG_FINANCIALS, "persist": True, "assessment_id": 7},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("id", resp.json())
        # Now retrievable via GET.
        self.assertEqual(self.client.get("/analysis/7").status_code, 200)

    def test_get_full_and_subsets(self):
        self._seed(assessment_id=1)
        full = self.client.get("/analysis/1").json()
        self.assertEqual(len(full["ratios"]), 20)

        self.assertEqual(len(self.client.get("/analysis/ratios/1").json()["ratios"]), 20)
        self.assertIn("health_scores", self.client.get("/analysis/health/1").json())
        self.assertIn("recommendations", self.client.get("/analysis/recommendations/1").json())
        self.assertIn("risk_flags", self.client.get("/analysis/risk-flags/1").json())

    def test_missing_returns_404(self):
        self.assertEqual(self.client.get("/analysis/999").status_code, 404)

    def test_ownership_enforced(self):
        self._seed(assessment_id=2, user_id=42)  # belongs to a different user
        self.assertEqual(self.client.get("/analysis/2").status_code, 404)

    def test_history(self):
        self._seed(assessment_id=3)
        self._seed(assessment_id=3)  # second version
        versions = self.client.get("/analysis/3/history").json()["versions"]
        self.assertEqual(len(versions), 2)


if __name__ == "__main__":
    unittest.main()
