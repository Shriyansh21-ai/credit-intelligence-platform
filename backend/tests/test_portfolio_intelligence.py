""" tests: portfolio risk intelligence."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import user  # noqa: F401
from backend.app.models.enterprise_assessment import EnterpriseAssessment
from backend.app.routes import ml as ml_routes
from backend.app.services.ml.portfolio import Position, analyze


def _pos(cid, industry, region, rating, score, pd, lgd, exposure, name=None):
    return Position(
        client_id=cid, company_name=name or f"Client {cid}", industry=industry,
        region=region, rating=rating, score=score, pd=pd, lgd=lgd, exposure=exposure,
    )


PORTFOLIO = [
    _pos(1, "Manufacturing", "India", "A", 720, 0.03, 0.45, 5_000_000),
    _pos(2, "Manufacturing", "India", "BBB", 660, 0.06, 0.50, 3_000_000),
    _pos(3, "Retail", "UAE", "BB", 590, 0.12, 0.55, 2_000_000),
    _pos(4, "Technology", "USA", "AA", 800, 0.01, 0.40, 8_000_000),
]


class AggregationTest(unittest.TestCase):
    def test_empty_portfolio(self):
        result = analyze([])
        self.assertEqual(result["summary"]["client_count"], 0)
        self.assertEqual(result["summary"]["portfolio_health"]["status"], "No Exposure")

    def test_summary_metrics(self):
        r = analyze(PORTFOLIO)
        s = r["summary"]
        self.assertEqual(s["client_count"], 4)
        self.assertEqual(s["total_exposure"], 18_000_000)
        # EL = Σ pd*lgd*ead
        expected_el = sum(p.pd * p.lgd * p.exposure for p in PORTFOLIO)
        self.assertAlmostEqual(s["expected_loss"], round(expected_el, 2), places=2)
        self.assertGreater(s["unexpected_loss"], 0)
        self.assertTrue(300 <= s["weighted_average_score"] <= 900)

    def test_distributions(self):
        r = analyze(PORTFOLIO)
        industries = {row["key"]: row for row in r["distributions"]["by_industry"]}
        self.assertEqual(industries["Manufacturing"]["client_count"], 2)
        self.assertEqual(industries["Manufacturing"]["exposure"], 8_000_000)
        # Sorted by exposure descending.
        exposures = [row["exposure"] for row in r["distributions"]["by_industry"]]
        self.assertEqual(exposures, sorted(exposures, reverse=True))

    def test_concentration_hhi(self):
        r = analyze(PORTFOLIO)
        conc = r["concentration"]
        self.assertGreater(conc["industry_hhi"], 0)
        self.assertIn(conc["assessment"], ("concentrated", "moderate", "diversified"))

    def test_top_risk_clients_ranked(self):
        r = analyze(PORTFOLIO)
        els = [c["expected_loss"] for c in r["top_risk_clients"]]
        self.assertEqual(els, sorted(els, reverse=True))


class _FakeUser:
    def __init__(self, uid):
        self.id = uid


class PortfolioApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        app = FastAPI()
        app.include_router(ml_routes.router)

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: _FakeUser(1)
        self.client = TestClient(app)
        self._seed()

    def _seed(self):
        db = self.Session()
        try:
            for i, (industry, rating, score, pd) in enumerate([
                ("Manufacturing", "A", 720, 0.03),
                ("Retail", "BB", 590, 0.12),
            ], start=1):
                db.add(EnterpriseAssessment(
                    user_id=1, company_name=f"Co {i}", industry=industry,
                    business_type="private", years_in_business=10, employee_count=100,
                    enterprise_credit_score=score, probability_of_default=pd,
                    loss_given_default=0.45, expected_loss=pd * 0.45,
                    risk_rating=rating, recommended_loan_amount=1_000_000 * i,
                    recommended_interest_rate=10.0, loan_recommendation="ok",
                    interest_rate_recommendation="10%", loan_tenure_recommendation="5y",
                    collateral_recommendation="standard", ai_analysis="n/a",
                    country="India",
                ))
            db.commit()
        finally:
            db.close()

    def test_portfolio_endpoint(self):
        r = self.client.get("/api/ml/portfolio")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["summary"]["client_count"], 2)
        self.assertIn("by_industry", body["distributions"])

    def test_portfolio_filter(self):
        r = self.client.get("/api/ml/portfolio", params={"industry": "Retail"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["summary"]["client_count"], 1)


if __name__ == "__main__":
    unittest.main()
