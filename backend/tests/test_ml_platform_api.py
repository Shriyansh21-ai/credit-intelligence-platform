""" Enterprise ML Platform API tests (HTTP + RBAC)."""

import unittest
import warnings

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

warnings.filterwarnings("ignore")

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import audit as audit_model  # noqa: F401
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import ml_platform  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.application import Application  # noqa: F401
from backend.app.models.feature_vector import FeatureVector  # noqa: F401
from backend.app.models.user import User
from backend.app.routes.ml_platform import ROUTERS
from backend.app.services.ml import serving
from backend.app.services.ml.data import make_synthetic_dataset
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role

_DATASET = make_synthetic_dataset(seed=42, n_rows=1200)
_ROWS = _DATASET.rows_as_dicts()


class MLPlatformApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
        db.close()
        serving.clear_caches()

    def _user(self, email, role):
        db = self.Session()
        try:
            u = User(email=email, password="x")
            db.add(u)
            db.commit()
            db.refresh(u)
            assign_role(db, u, role)
            return u.id
        finally:
            db.close()

    def _client(self, uid):
        app = FastAPI()
        for r in ROUTERS:
            app.include_router(r)

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        def override_user():
            db = self.Session()
            try:
                return db.query(User).filter(User.id == uid).first()
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        return TestClient(app)

    # -- helpers ---------------------------------------------------------
    def _train_and_register(self, client, algorithm="logistic_regression"):
        resp = client.post("/api/ml/training/train",
                           json={"algorithm": algorithm, "n_rows": 1200, "dataset_seed": 42})
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()["model"]["id"]

    def _promote(self, client, model_id):
        client.post(f"/api/ml/registry/models/{model_id}/submit")
        client.post(f"/api/ml/registry/models/{model_id}/approve")
        return client.post(f"/api/ml/registry/models/{model_id}/promote")

    # -- tests -----------------------------------------------------------
    def test_algorithms_endpoint(self):
        client = self._client(self._user("rm@x.com", "risk_manager"))
        resp = client.get("/api/ml/training/algorithms")
        self.assertEqual(resp.status_code, 200)
        algos = {a["algorithm"] for a in resp.json()["algorithms"]}
        self.assertIn("xgboost", algos)

    def test_train_requires_permission(self):
        client = self._client(self._user("viewer@x.com", "viewer"))
        resp = client.post("/api/ml/training/train", json={"algorithm": "logistic_regression"})
        self.assertEqual(resp.status_code, 403)

    def test_train_and_registry_flow(self):
        client = self._client(self._user("risk@x.com", "risk_manager"))
        model_id = self._train_and_register(client)
        detail = client.get(f"/api/ml/registry/models/{model_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["approval_status"], "draft")

    def test_governance_flow(self):
        # risk_manager can train but promotion needs mlops.deploy (admin/compliance).
        admin = self._client(self._user("admin@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        promote = self._promote(admin, model_id)
        self.assertEqual(promote.status_code, 200)
        self.assertEqual(promote.json()["production_status"], "production")

    def test_promote_requires_deploy_permission(self):
        # senior_analyst can train + submit but lacks mlops.deploy → approve is forbidden.
        sa = self._client(self._user("sa@x.com", "senior_analyst"))
        model_id = self._train_and_register(sa)
        sa.post(f"/api/ml/registry/models/{model_id}/submit")
        resp = sa.post(f"/api/ml/registry/models/{model_id}/approve")
        self.assertEqual(resp.status_code, 403)

    def test_serving_predict(self):
        admin = self._client(self._user("admin2@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        self._promote(admin, model_id)
        resp = admin.post("/api/ml/serving/predict", json={"features": _ROWS[0]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["model"]["inference_mode"], "trained_artifact")

    def test_serving_fallback_without_model(self):
        admin = self._client(self._user("admin3@x.com", "administrator"))
        resp = admin.post("/api/ml/serving/predict", json={"features": _ROWS[0]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["model"]["inference_mode"], "deterministic_fallback")

    def test_serving_batch(self):
        admin = self._client(self._user("admin4@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        self._promote(admin, model_id)
        items = [{"features": r} for r in _ROWS[:8]]
        resp = admin.post("/api/ml/serving/batch", json={"items": items})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 8)

    def test_explainability(self):
        admin = self._client(self._user("admin5@x.com", "administrator"))
        model_id = self._train_and_register(admin, "xgboost")
        self._promote(admin, model_id)
        resp = admin.post("/api/ml/explainability/explain",
                         json={"features": _ROWS[3], "entity_id": 3})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("reason_codes", body)
        self.assertIn("narratives", body)

    def test_monitoring_summary(self):
        admin = self._client(self._user("admin6@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        self._promote(admin, model_id)
        admin.post("/api/ml/serving/batch", json={"items": [{"features": r} for r in _ROWS[:5]]})
        resp = admin.get(f"/api/ml/monitoring/summary?model_id={model_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["prediction_volume"]["total"], 5)

    def test_performance_evaluate(self):
        admin = self._client(self._user("admin7@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        resp = admin.post(f"/api/ml/monitoring/performance/{model_id}/evaluate?n_rows=800")
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.json()["metrics"]["roc_auc"], 0.7)

    def test_drift_detect(self):
        admin = self._client(self._user("admin8@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        shifted = make_synthetic_dataset(
            seed=55, n_rows=400,
            drift={"debt_to_ebitda": 2.2, "interest_coverage": -1.8,
                   "collateral_coverage": -1.5, "debt_to_equity": 2.0}).rows_as_dicts()
        resp = admin.post("/api/ml/drift/detect",
                         json={"model_id": model_id, "current_rows": shifted})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["breached"])

    def test_retraining_run(self):
        admin = self._client(self._user("admin9@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        self._promote(admin, model_id)
        resp = admin.post("/api/ml/retraining/run",
                         json={"model_key": "logistic_regression", "n_rows": 1200})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["challenger_version"], 2)

    def test_fraud_score(self):
        admin = self._client(self._user("admin10@x.com", "administrator"))
        resp = admin.post("/api/ml/fraud/score", json={"features": _ROWS[0], "entity_id": 1})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("fraud_probability", resp.json())

    def test_fraud_requires_permission(self):
        client = self._client(self._user("viewer2@x.com", "viewer"))
        resp = client.post("/api/ml/fraud/score", json={"features": _ROWS[0]})
        self.assertEqual(resp.status_code, 403)

    def test_portfolio_analyze(self):
        admin = self._client(self._user("admin11@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        self._promote(admin, model_id)
        positions = [{"features": _ROWS[i], "entity_id": i, "sector": "mfg", "exposure": 1_000_000}
                     for i in range(15)]
        resp = admin.post("/api/ml/portfolio-ml/analyze", json={"positions": positions})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["metrics"]["positions"], 15)

    def test_stress_run(self):
        admin = self._client(self._user("admin12@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        self._promote(admin, model_id)
        positions = [{"features": _ROWS[i], "exposure": 1_000_000} for i in range(10)]
        resp = admin.post("/api/ml/stress-ml/run",
                         json={"positions": positions, "scenario": "interest_rate_hike"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("cases", resp.json())

    def test_stress_scenarios_listed(self):
        admin = self._client(self._user("admin13@x.com", "administrator"))
        resp = admin.get("/api/ml/stress-ml/scenarios")
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.json()["scenarios"]), 3)

    def test_feature_catalog(self):
        admin = self._client(self._user("admin14@x.com", "administrator"))
        resp = admin.get("/api/ml/feature-store/catalog")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("categories", resp.json())

    def test_feature_lineage(self):
        admin = self._client(self._user("admin15@x.com", "administrator"))
        resp = admin.get("/api/ml/feature-store/lineage/current_ratio")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["feature"], "current_ratio")

    def test_reproducibility_trail(self):
        admin = self._client(self._user("admin16@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        resp = admin.get(f"/api/ml/registry/models/{model_id}/reproducibility")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["reproducible"])
        self.assertIsNotNone(body["dataset"]["content_hash"])
        self.assertIn("hyperparameters", body)

    def test_deployment_history_endpoint(self):
        admin = self._client(self._user("admin17@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        self._promote(admin, model_id)
        resp = admin.get(f"/api/ml/registry/models/{model_id}/history")
        self.assertEqual(resp.status_code, 200)
        actions = [e["action"] for e in resp.json()["events"]]
        self.assertIn("promote", actions)

    def test_model_versions_endpoint(self):
        admin = self._client(self._user("admin18@x.com", "administrator"))
        self._train_and_register(admin)
        self._train_and_register(admin)
        resp = admin.get("/api/ml/registry/models/logistic_regression/versions")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["versions"]), 2)

    def test_rollback_endpoint(self):
        admin = self._client(self._user("admin19@x.com", "administrator"))
        m1 = self._train_and_register(admin)
        self._promote(admin, m1)
        m2 = self._train_and_register(admin)
        self._promote(admin, m2)
        resp = admin.post("/api/ml/registry/models/logistic_regression/rollback", json={})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], m1)

    def test_drift_history_endpoint(self):
        admin = self._client(self._user("admin20@x.com", "administrator"))
        model_id = self._train_and_register(admin)
        rows = make_synthetic_dataset(seed=99, n_rows=300).rows_as_dicts()
        admin.post("/api/ml/drift/detect", json={"model_id": model_id, "current_rows": rows})
        resp = admin.get("/api/ml/drift/history")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()["reports"]), 1)

    def test_fraud_clusters_endpoint(self):
        admin = self._client(self._user("admin21@x.com", "administrator"))
        resp = admin.get("/api/ml/fraud/clusters")
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.json()["clusters"]), 1)


if __name__ == "__main__":
    unittest.main()
