"""Phase 4 tests: the /api/ml router (features, predict, explain)."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import feature_vector  # noqa: F401
from backend.app.models import risk_alert  # noqa: F401
from backend.app.models import risk_explanation  # noqa: F401
from backend.app.models import user  # noqa: F401
from backend.app.models.enterprise_assessment import EnterpriseAssessment
from backend.app.routes import ml as ml_routes

ENGINE_INPUT = {
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


class _FakeUser:
    def __init__(self, uid):
        self.id = uid


class MlApiTest(unittest.TestCase):
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

        self.user = _FakeUser(1)
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def test_list_models(self):
        r = self.client.get("/api/ml/models")
        self.assertEqual(r.status_code, 200)
        types = {m["model_type"] for m in r.json()["models"]}
        self.assertIn("scorecard", types)

    def test_compute_and_persist_features_then_fetch(self):
        r = self.client.post(
            "/api/ml/features/compute",
            json={"engine_input": ENGINE_INPUT, "persist": True, "assessment_id": 7},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertGreater(body["feature_count"], 0)
        self.assertIn("id", body)

        r2 = self.client.get("/api/ml/features/7")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["assessment_id"], 7)

    def test_features_not_found(self):
        self.assertEqual(self.client.get("/api/ml/features/999").status_code, 404)

    def test_predict_endpoint(self):
        r = self.client.post("/api/ml/predict", json={"engine_input": ENGINE_INPUT})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("probability_of_default", body)
        self.assertIn("risk_grade", body)
        self.assertIn("model_metadata", body)

    def test_predict_requires_a_source(self):
        r = self.client.post("/api/ml/predict", json={})
        self.assertEqual(r.status_code, 422)

    def test_explain_endpoint_and_persist(self):
        r = self.client.post(
            "/api/ml/explain",
            json={"engine_input": ENGINE_INPUT, "persist": True, "assessment_id": 3},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("waterfall", body)
        self.assertIn("top_positive_contributors", body)
        self.assertIn("id", body)

    def test_predict_and_explain_from_stored_vector(self):
        # Seed a stored vector via compute+persist.
        self.client.post(
            "/api/ml/features/compute",
            json={"engine_input": ENGINE_INPUT, "persist": True, "assessment_id": 5},
        )
        rp = self.client.get("/api/ml/predict/5")
        self.assertEqual(rp.status_code, 200, rp.text)
        self.assertIn("risk_score", rp.json())

        re = self.client.get("/api/ml/explain/5")
        self.assertEqual(re.status_code, 200, re.text)
        self.assertIn("summary", re.json())

    def test_scenario_endpoint(self):
        r = self.client.post("/api/ml/scenario", json={
            "engine_input": ENGINE_INPUT,
            "adjustments": [{"factor": "revenue_change", "value": -30}],
        })
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("baseline", r.json())
        self.assertIn("delta", r.json())

    def test_stress_scenarios_and_report_endpoints(self):
        self.assertEqual(self.client.get("/api/ml/stress-test/scenarios").status_code, 200)
        r = self.client.post("/api/ml/report", json={"engine_input": ENGINE_INPUT})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("executive_summary", r.json())

    def test_alerts_scan_endpoint(self):
        r = self.client.post("/api/ml/alerts/scan", json={"engine_input": ENGINE_INPUT})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("alert_count", r.json())

    def _seed_assessment(self, aid=42):
        db = self.Session()
        try:
            db.add(EnterpriseAssessment(
                id=aid, user_id=1, company_name="Acme", industry="Manufacturing",
                business_type="private", years_in_business=10, employee_count=100,
                enterprise_credit_score=720, probability_of_default=0.03,
                loss_given_default=0.45, expected_loss=0.0135, risk_rating="A",
                recommended_loan_amount=1_000_000, recommended_interest_rate=10.0,
                loan_recommendation="ok", interest_rate_recommendation="10%",
                loan_tenure_recommendation="5y", collateral_recommendation="standard",
                ai_analysis="n/a", country="India", engine_input=ENGINE_INPUT,
            ))
            db.commit()
        finally:
            db.close()

    def test_assessment_driven_report_and_stress(self):
        self._seed_assessment(42)
        rr = self.client.get("/api/ml/report/42")
        self.assertEqual(rr.status_code, 200, rr.text)
        self.assertIn("final_recommendation", rr.json())

        rs = self.client.get("/api/ml/stress-test/42")
        self.assertEqual(rs.status_code, 200, rs.text)
        self.assertIn("worst_case", rs.json())

        # Scenario driven purely by assessment_id (resolves saved engine input).
        rsc = self.client.post("/api/ml/scenario", json={
            "assessment_id": 42, "adjustments": [{"factor": "debt_change", "value": 50}],
        })
        self.assertEqual(rsc.status_code, 200, rsc.text)

    def test_report_missing_assessment_404(self):
        self.assertEqual(self.client.get("/api/ml/report/999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
