""" Enterprise ML Platform service-level tests.

Covers the training pipeline, model registry, serving engine, explainability
monitoring, performance, drift detection, retraining, fraud ML, portfolio ML
stress testing and the enterprise feature store.
"""

import unittest
import warnings

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

warnings.filterwarnings("ignore")

from backend.app.db.database import Base
from backend.app.models import ml_platform as mlp  # noqa: F401
from backend.app.models.feature_vector import FeatureVector  # noqa: F401
from backend.app.services.ml import drift, fraud, registry, retraining, serving
from backend.app.services.ml.data import (
    dataset_from_spec, make_synthetic_dataset, train_test_split,
)
from backend.app.services.ml.data.synthetic import generate, signal_feature_names
from backend.app.services.ml.explainability import ml_service as explain_svc
from backend.app.services.ml.explainability.enterprise import (
    business_summary, executive_summary, explain_model, reason_codes,
)
from backend.app.services.ml.features import lineage as feature_lineage
from backend.app.services.ml.monitoring import performance as perf_svc
from backend.app.services.ml.monitoring import service as mon_svc
from backend.app.services.ml.portfolio import ml_portfolio
from backend.app.services.ml.stress import ml_stress
from backend.app.services.ml.training import estimators, train
from backend.app.services.ml.training.evaluation import evaluate, ks_statistic, roc_auc
from backend.app.services.ml.training.trained_model import TrainedRiskModel

_ML_TABLES = [
    mlp.MLDataset.__table__, mlp.MLModel.__table__, mlp.MLDeploymentEvent.__table__,
    mlp.MLPredictionLog.__table__, mlp.MLExplanation.__table__, mlp.MLDriftReport.__table__,
    mlp.MLPerformanceRecord.__table__, mlp.MLFraudResult.__table__,
]

# Module-level dataset + trained model, reused to keep the suite fast.
_DATASET = make_synthetic_dataset(seed=42, n_rows=1500)
_ROWS = _DATASET.rows_as_dicts()


def _fresh_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=_ML_TABLES)
    return sessionmaker(bind=engine)()


def _promote(db, algorithm="logistic_regression", author="a@bank"):
    result = train(_DATASET, algorithm, cv_folds=3)
    model = registry.register_model(db, result, author=author)
    registry.submit_for_approval(db, model.id, actor=author)
    registry.approve(db, model.id, actor=author)
    registry.promote(db, model.id, actor=author)
    serving.clear_caches()
    return model, result


# ---------------------------------------------------------------------------
# Synthetic data
# ---------------------------------------------------------------------------
class SyntheticDataTest(unittest.TestCase):
    def test_reproducible(self):
        a = generate(seed=7, n_rows=500)
        b = generate(seed=7, n_rows=500)
        self.assertTrue((a.X == b.X).all())
        self.assertTrue((a.y == b.y).all())

    def test_different_seed_differs(self):
        a = generate(seed=1, n_rows=500)
        b = generate(seed=2, n_rows=500)
        self.assertFalse((a.X == b.X).all())

    def test_signal_features_nonempty(self):
        self.assertGreater(len(signal_feature_names()), 10)

    def test_labels_binary(self):
        ds = generate(seed=3, n_rows=400)
        self.assertEqual(set(np.unique(ds.y).tolist()), {0, 1})

    def test_positive_rate_reasonable(self):
        ds = make_synthetic_dataset(seed=42, n_rows=2000)
        self.assertTrue(0.1 < ds.positive_rate < 0.6)

    def test_content_hash_stable(self):
        a = make_synthetic_dataset(seed=42, n_rows=1000)
        b = make_synthetic_dataset(seed=42, n_rows=1000)
        self.assertEqual(a.content_hash(), b.content_hash())

    def test_reproduce_from_spec(self):
        a = make_synthetic_dataset(seed=42, n_rows=1000)
        b = dataset_from_spec(a.spec)
        self.assertEqual(a.content_hash(), b.content_hash())

    def test_drift_shifts_distribution(self):
        base = generate(seed=5, n_rows=1000)
        shifted = generate(seed=5, n_rows=1000, drift={"debt_to_ebitda": 2.0})
        j = base.feature_names.index("debt_to_ebitda")
        self.assertGreater(shifted.X[:, j].mean(), base.X[:, j].mean())

    def test_train_test_split_stratified(self):
        Xtr, Xte, ytr, yte = train_test_split(_DATASET, test_size=0.25)
        self.assertAlmostEqual(ytr.mean(), yte.mean(), delta=0.05)
        self.assertEqual(len(Xtr) + len(Xte), _DATASET.n_rows)


# ---------------------------------------------------------------------------
# Evaluation metrics
# ---------------------------------------------------------------------------
class EvaluationTest(unittest.TestCase):
    def test_perfect_separation_auc(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([0.1, 0.2, 0.8, 0.9])
        self.assertAlmostEqual(roc_auc(y, p), 1.0)

    def test_random_auc_half(self):
        y = np.array([0, 1, 0, 1])
        p = np.array([0.5, 0.5, 0.5, 0.5])
        self.assertAlmostEqual(roc_auc(y, p), 0.5, places=5)

    def test_ks_range(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([0.1, 0.2, 0.8, 0.9])
        self.assertTrue(0.0 <= ks_statistic(y, p) <= 1.0)

    def test_full_metric_suite(self):
        y = np.array([0, 0, 1, 1, 0, 1])
        p = np.array([0.2, 0.3, 0.7, 0.8, 0.4, 0.6])
        res = evaluate(y, p).as_dict()
        for k in ("accuracy", "precision", "recall", "f1", "roc_auc", "ks_statistic",
                  "gini", "brier_score", "log_loss", "confusion_matrix", "calibration"):
            self.assertIn(k, res)

    def test_gini_matches_auc(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([0.1, 0.4, 0.6, 0.9])
        res = evaluate(y, p)
        self.assertAlmostEqual(res.gini, 2 * res.roc_auc - 1, places=6)


# ---------------------------------------------------------------------------
# Training pipeline
# ---------------------------------------------------------------------------
class TrainingTest(unittest.TestCase):
    def test_available_algorithms(self):
        self.assertIn("logistic_regression", estimators.SUPPORTED_ALGORITHMS)
        self.assertTrue(estimators.backend_available("logistic_regression"))
        self.assertTrue(estimators.backend_available("xgboost"))

    def test_train_produces_signal(self):
        result = train(_DATASET, "logistic_regression", cv_folds=3)
        self.assertGreater(result.metrics.roc_auc, 0.7)

    def test_train_report_shape(self):
        result = train(_DATASET, "random_forest", cv_folds=3)
        report = result.report()
        self.assertIn("metrics", report)
        self.assertIn("cross_validation", report)
        self.assertIn("feature_importances", report)
        self.assertEqual(report["n_train"] + report["n_test"], _DATASET.n_rows)

    def test_xgboost_trains(self):
        result = train(_DATASET, "xgboost", cv_folds=3)
        self.assertGreater(result.metrics.roc_auc, 0.7)

    def test_lightgbm_trains(self):
        result = train(_DATASET, "lightgbm", cv_folds=3)
        self.assertGreater(result.metrics.roc_auc, 0.7)

    def test_unavailable_backend_raises(self):
        with self.assertRaises(estimators.BackendUnavailableError):
            train(_DATASET, "catboost", cv_folds=3)

    def test_prediction_envelope(self):
        result = train(_DATASET, "xgboost", cv_folds=3)
        pred = result.model.predict_risk(_ROWS[0]).as_dict()
        self.assertEqual(pred["inference_mode"], "trained_artifact")
        self.assertTrue(0.0 <= pred["probability_of_default"] <= 1.0)
        self.assertTrue(300 <= pred["risk_score"] <= 900)

    def test_artifact_roundtrip(self):
        import os
        import tempfile
        result = train(_DATASET, "logistic_regression", cv_folds=3)
        path = os.path.join(tempfile.mkdtemp(), "m.joblib")
        result.model.save_model(path)
        loaded = TrainedRiskModel.from_artifact(path)
        self.assertAlmostEqual(
            loaded.predict_proba(_ROWS[0])[1], result.model.predict_proba(_ROWS[0])[1], places=9)

    def test_importances_normalised(self):
        result = train(_DATASET, "random_forest", cv_folds=3)
        self.assertAlmostEqual(sum(result.feature_importances.values()), 1.0, places=5)


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------
class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()

    def tearDown(self):
        self.db.close()

    def test_register_creates_draft(self):
        result = train(_DATASET, "logistic_regression", cv_folds=3)
        model = registry.register_model(self.db, result, author="a@bank")
        self.assertEqual(model.approval_status, "draft")
        self.assertEqual(model.production_status, "none")
        self.assertEqual(model.version, 1)

    def test_versions_increment(self):
        for _ in range(3):
            registry.register_model(self.db, train(_DATASET, "logistic_regression", cv_folds=3))
        self.assertEqual(len(registry.versions(self.db, "logistic_regression")), 3)
        self.assertEqual(registry.versions(self.db, "logistic_regression")[0].version, 3)

    def test_approval_flow(self):
        result = train(_DATASET, "logistic_regression", cv_folds=3)
        model = registry.register_model(self.db, result)
        registry.submit_for_approval(self.db, model.id)
        registry.approve(self.db, model.id)
        self.db.refresh(model)
        self.assertEqual(model.approval_status, "approved")
        self.assertEqual(model.production_status, "staging")

    def test_cannot_promote_unapproved(self):
        model = registry.register_model(self.db, train(_DATASET, "logistic_regression", cv_folds=3))
        with self.assertRaises(registry.RegistryError):
            registry.promote(self.db, model.id)

    def test_promote_archives_incumbent(self):
        m1, _ = _promote(self.db)
        m2, _ = _promote(self.db)
        self.db.refresh(m1)
        self.assertEqual(m1.production_status, "archived")
        self.assertEqual(registry.production_model(self.db, "logistic_regression").id, m2.id)

    def test_rollback(self):
        m1, _ = _promote(self.db)
        m2, _ = _promote(self.db)
        restored = registry.rollback(self.db, "logistic_regression")
        self.assertEqual(restored.id, m1.id)
        self.assertEqual(registry.production_model(self.db, "logistic_regression").id, m1.id)

    def test_rollback_without_history_raises(self):
        _promote(self.db)
        with self.assertRaises(registry.RegistryError):
            registry.rollback(self.db, "logistic_regression")

    def test_deployment_history_recorded(self):
        model, _ = _promote(self.db)
        actions = [e.action for e in registry.deployment_history(self.db, model.id)]
        self.assertIn("register", actions)
        self.assertIn("approve", actions)
        self.assertIn("promote", actions)

    def test_dataset_reuse_by_hash(self):
        r = train(_DATASET, "logistic_regression", cv_folds=3)
        d1 = registry.register_dataset(self.db, r.dataset_snapshot)
        d2 = registry.register_dataset(self.db, r.dataset_snapshot)
        self.assertEqual(d1.id, d2.id)


# ---------------------------------------------------------------------------
# Serving
# ---------------------------------------------------------------------------
class ServingTest(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()
        serving.clear_caches()

    def tearDown(self):
        self.db.close()

    def test_fallback_before_training(self):
        res = serving.predict(self.db, _ROWS[0])
        self.assertEqual(res["model"]["inference_mode"], "deterministic_fallback")
        self.assertTrue(res["success"])

    def test_served_after_promote(self):
        _promote(self.db, "xgboost")
        res = serving.predict(self.db, _ROWS[0])
        self.assertEqual(res["model"]["inference_mode"], "trained_artifact")
        self.assertEqual(res["model"]["model_key"], "xgboost")

    def test_cache_hit(self):
        _promote(self.db, "xgboost")
        serving.predict(self.db, _ROWS[1])
        self.assertTrue(serving.predict(self.db, _ROWS[1])["cached"])

    def test_batch(self):
        _promote(self.db, "xgboost")
        out = serving.batch_predict(self.db, _ROWS[:10])
        self.assertEqual(out["count"], 10)
        self.assertEqual(out["summary"]["scored"], 10)

    def test_async(self):
        _promote(self.db, "xgboost")
        out = serving.async_submit(self.db, _ROWS[0])
        self.assertEqual(out["status"], "completed")
        self.assertEqual(len(serving.get_by_request(self.db, out["request_id"])), 1)

    def test_prediction_history_logged(self):
        _promote(self.db, "xgboost")
        serving.batch_predict(self.db, _ROWS[:5])
        self.assertGreaterEqual(len(serving.prediction_history(self.db, limit=100)), 5)

    def test_explicit_model_id(self):
        model, _ = _promote(self.db, "logistic_regression")
        res = serving.predict(self.db, _ROWS[0], model_id=model.id)
        self.assertEqual(res["model"]["id"], model.id)


# ---------------------------------------------------------------------------
# Explainability
# ---------------------------------------------------------------------------
class ExplainabilityTest(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()
        serving.clear_caches()

    def tearDown(self):
        self.db.close()

    def test_explain_trained_model(self):
        _promote(self.db, "lightgbm")
        payload = explain_svc.explain(self.db, _ROWS[5], persist=True)
        self.assertIn("reason_codes", payload)
        self.assertIn("narratives", payload)
        self.assertIn("waterfall", payload)
        self.assertIn("explanation_id", payload)

    def test_shap_method_for_tree_model(self):
        _promote(self.db, "xgboost")
        payload = explain_svc.explain(self.db, _ROWS[5], persist=False)
        self.assertEqual(payload["method"], "shap")
        self.assertIn("shap_values", payload)

    def test_reason_codes_from_explanation(self):
        result = train(_DATASET, "logistic_regression", cv_folds=3)
        explanation = explain_model(_ROWS[5], result.model)
        codes = reason_codes(explanation)
        self.assertTrue(all("code" in c for c in codes))

    def test_narratives_nonempty(self):
        result = train(_DATASET, "logistic_regression", cv_folds=3)
        explanation = explain_model(_ROWS[5], result.model)
        self.assertTrue(executive_summary(explanation))
        self.assertTrue(business_summary(explanation))

    def test_explanation_persisted_and_retrievable(self):
        _promote(self.db, "logistic_regression")
        payload = explain_svc.explain(self.db, _ROWS[3], entity_id=3, persist=True)
        rows = explain_svc.history(self.db, entity_id=3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, payload["explanation_id"])


# ---------------------------------------------------------------------------
# Monitoring & performance
# ---------------------------------------------------------------------------
class MonitoringTest(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()
        serving.clear_caches()
        self.model, _ = _promote(self.db, "xgboost")
        serving.batch_predict(self.db, _ROWS[:30], created_by="rm@bank")

    def tearDown(self):
        self.db.close()

    def test_summary_volume(self):
        s = mon_svc.summary(self.db, model_id=self.model.id)
        self.assertEqual(s["prediction_volume"]["total"], 30)
        self.assertEqual(s["success_rate"], 1.0)

    def test_latency_stats(self):
        s = mon_svc.latency_stats(self.db, model_id=self.model.id)
        self.assertEqual(s["count"], 30)
        self.assertIsNotNone(s["p95"])

    def test_usage_statistics(self):
        u = mon_svc.usage_statistics(self.db)
        self.assertEqual(u["total_predictions"], 30)
        self.assertIn("xgboost", u["by_model"])

    def test_class_distribution(self):
        s = mon_svc.summary(self.db, model_id=self.model.id)
        self.assertIn("approval_rate", s["class_distribution"])

    def test_performance_evaluate(self):
        rec = perf_svc.evaluate_reproduced(self.db, self.model)
        self.assertGreater(rec.metrics["roc_auc"], 0.7)
        self.assertIn("expected_loss", rec.business_kpis)

    def test_performance_trend(self):
        perf_svc.evaluate_reproduced(self.db, self.model, holdout_seed=1)
        perf_svc.evaluate_reproduced(self.db, self.model, holdout_seed=2)
        self.assertEqual(len(perf_svc.performance_trend(self.db, model_id=self.model.id)), 2)


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------
class DriftTest(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()
        self.model = registry.register_model(self.db, train(_DATASET, "logistic_regression", cv_folds=3))

    def tearDown(self):
        self.db.close()

    def test_no_drift_when_same_distribution(self):
        rows = make_synthetic_dataset(seed=99, n_rows=600).rows_as_dicts()
        report = drift.detect(self.db, self.model, rows)
        self.assertFalse(report.breached)
        self.assertEqual(report.detail["psi_band"], "stable")

    def test_drift_detected(self):
        shifted = make_synthetic_dataset(
            seed=55, n_rows=600,
            drift={"debt_to_ebitda": 2.2, "interest_coverage": -1.8,
                   "collateral_coverage": -1.5, "debt_to_equity": 2.0}).rows_as_dicts()
        report = drift.detect(self.db, self.model, shifted)
        self.assertTrue(report.breached)
        self.assertGreater(report.n_drifted, 0)

    def test_psi_zero_for_identical(self):
        ref = np.random.default_rng(1).normal(size=1000)
        self.assertLess(drift.population_stability_index(ref, ref), 0.01)

    def test_schema_changes(self):
        changes = drift.schema_changes([{"current_ratio": 1.0}], self.model.feature_names)
        self.assertGreater(len(changes["missing_features"]), 0)

    def test_history(self):
        rows = make_synthetic_dataset(seed=99, n_rows=300).rows_as_dicts()
        drift.detect(self.db, self.model, rows)
        drift.detect(self.db, self.model, rows)
        self.assertEqual(len(drift.history(self.db, model_id=self.model.id)), 2)

    def test_target_drift(self):
        report = drift.detect_target_drift(self.db, self.model, [0.5] * 100)
        self.assertEqual(report.report_type, "target")


# ---------------------------------------------------------------------------
# Retraining
# ---------------------------------------------------------------------------
class RetrainingTest(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()
        serving.clear_caches()

    def tearDown(self):
        self.db.close()

    def test_retrain_creates_new_version(self):
        _promote(self.db, "logistic_regression")
        out = retraining.run_retraining(self.db, "logistic_regression", n_rows=1500)
        self.assertEqual(out["challenger_version"], 2)
        self.assertIn(out["comparison"]["winner"], ("champion", "challenger"))

    def test_auto_promote_winner(self):
        # Champion trained on a tiny noisy set so the challenger is likely to win.
        weak = make_synthetic_dataset(seed=1, n_rows=400, label_noise=0.2)
        r = train(weak, "logistic_regression", cv_folds=3)
        m = registry.register_model(self.db, r)
        registry.submit_for_approval(self.db, m.id); registry.approve(self.db, m.id); registry.promote(self.db, m.id)
        out = retraining.run_retraining(self.db, "logistic_regression", n_rows=3000,
                                        auto_promote=True, dataset_seed=42)
        if out["comparison"]["winner"] == "challenger":
            self.assertTrue(out["auto_promoted"])
            self.assertEqual(
                registry.production_model(self.db, "logistic_regression").id, out["challenger_id"])

    def test_should_retrain_on_breach(self):
        model, _ = _promote(self.db, "logistic_regression")
        shifted = make_synthetic_dataset(
            seed=7, n_rows=500,
            drift={"debt_to_ebitda": 2.5, "interest_coverage": -2.0,
                   "collateral_coverage": -1.8, "debt_to_equity": 2.2}).rows_as_dicts()
        drift.detect(self.db, model, shifted)
        self.assertTrue(retraining.should_retrain(self.db, "logistic_regression")["should_retrain"])

    def test_scan_and_retrain(self):
        model, _ = _promote(self.db, "logistic_regression")
        shifted = make_synthetic_dataset(
            seed=7, n_rows=500,
            drift={"debt_to_ebitda": 2.5, "interest_coverage": -2.0,
                   "collateral_coverage": -1.8, "debt_to_equity": 2.2}).rows_as_dicts()
        drift.detect(self.db, model, shifted)
        outcomes = retraining.scan_and_retrain(self.db)
        self.assertEqual(len(outcomes), 1)

    def test_champion_challenger_compare(self):
        m1, _ = _promote(self.db, "logistic_regression")
        r2 = train(_DATASET, "logistic_regression", cv_folds=3)
        m2 = registry.register_model(self.db, r2, model_key="logistic_regression")
        cmp = retraining.champion_challenger(self.db, "logistic_regression", m2.id)
        self.assertIn("comparison", cmp)


# ---------------------------------------------------------------------------
# Fraud ML
# ---------------------------------------------------------------------------
class FraudTest(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()

    def tearDown(self):
        self.db.close()

    def test_normal_low_probability(self):
        res = fraud.score(self.db, _ROWS[0], entity_id=1)
        self.assertLess(res["fraud_probability"], 0.9)

    def test_extreme_flagged(self):
        weird = dict(_ROWS[0])
        weird.update({"debt_to_ebitda": 60, "credit_utilization": 400,
                      "interest_coverage": -30, "net_margin": -8})
        res = fraud.score(self.db, weird, entity_id=2)
        self.assertGreater(res["fraud_probability"], 0.9)
        self.assertTrue(res["is_anomaly"])

    def test_method_scores_present(self):
        res = fraud.score(self.db, _ROWS[0])
        for m in ("isolation_forest", "local_outlier_factor", "autoencoder"):
            self.assertIn(m, res["method_scores"])

    def test_dimension_anomalies(self):
        res = fraud.score(self.db, _ROWS[0])
        for d in ("behavioral", "transaction", "network"):
            self.assertIn(d, res["dimension_anomalies"])

    def test_batch(self):
        out = fraud.score_batch(self.db, _ROWS[:20])
        self.assertEqual(out["count"], 20)
        self.assertIn("flag_rate", out)

    def test_cluster_profiles(self):
        profiles = fraud.cluster_profiles()
        self.assertGreater(len(profiles), 1)

    def test_history_persisted(self):
        fraud.score(self.db, _ROWS[0], entity_id=5)
        self.assertGreaterEqual(len(fraud.history(self.db, entity_id=5)), 1)


# ---------------------------------------------------------------------------
# Portfolio ML
# ---------------------------------------------------------------------------
class PortfolioTest(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()
        serving.clear_caches()
        _promote(self.db, "xgboost")
        sectors = ["mfg", "retail", "it", "realty"]
        self.positions = [
            {"entity_id": i, "features": _ROWS[i], "sector": sectors[i % 4],
             "exposure": 1_000_000 * (1 + i % 5)}
            for i in range(40)
        ]

    def tearDown(self):
        self.db.close()

    def test_metrics(self):
        result = ml_portfolio.analyze(self.db, self.positions)
        m = result["metrics"]
        self.assertEqual(m["positions"], 40)
        self.assertGreater(m["expected_loss"], 0)
        self.assertTrue(0.0 <= m["portfolio_default_rate"] <= 1.0)

    def test_concentration(self):
        m = ml_portfolio.analyze(self.db, self.positions)["metrics"]
        self.assertIn(m["sector_concentration_band"],
                      ("diversified", "moderately_concentrated", "highly_concentrated"))

    def test_clusters(self):
        result = ml_portfolio.analyze(self.db, self.positions)
        self.assertTrue(len(result["risk_clusters"]) >= 1)

    def test_top_exposures(self):
        m = ml_portfolio.analyze(self.db, self.positions)["metrics"]
        self.assertTrue(len(m["top_exposures"]) > 0)


# ---------------------------------------------------------------------------
# Stress testing
# ---------------------------------------------------------------------------
class StressTest(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()
        serving.clear_caches()
        _promote(self.db, "xgboost")
        self.positions = [{"entity_id": i, "features": _ROWS[i], "exposure": 1_000_000}
                          for i in range(30)]

    def tearDown(self):
        self.db.close()

    def test_scenarios_listed(self):
        names = [s["name"] for s in ml_stress.available_scenarios()]
        self.assertIn("interest_rate_hike", names)
        self.assertIn("gdp_decline", names)

    def test_apply_scenario_shifts_features(self):
        shocked = ml_stress.apply_scenario(_ROWS[0], "interest_rate_hike", "worst")
        self.assertLess(shocked["interest_coverage"], _ROWS[0]["interest_coverage"])

    def test_stress_increases_risk(self):
        out = ml_stress.stress_portfolio(self.db, self.positions, "gdp_decline")
        baseline = out["baseline"]["portfolio_default_rate"]
        worst = [c for c in out["cases"] if c["severity"] == "worst"][0]
        self.assertGreaterEqual(worst["metrics"]["portfolio_default_rate"], baseline)

    def test_severity_monotonic(self):
        out = ml_stress.stress_portfolio(self.db, self.positions, "interest_rate_hike")
        by_sev = {c["severity"]: c["metrics"]["portfolio_default_rate"] for c in out["cases"]}
        self.assertLessEqual(by_sev["optimistic"], by_sev["worst"])

    def test_unknown_scenario_raises(self):
        with self.assertRaises(ValueError):
            ml_stress.apply_scenario(_ROWS[0], "no_such_scenario")

    def test_stress_all_ranks(self):
        out = ml_stress.stress_all(self.db, self.positions, severity="worst")
        self.assertEqual(len(out["scenarios"]), len(ml_stress.MACRO_SCENARIOS))


# ---------------------------------------------------------------------------
# Feature store (M1)
# ---------------------------------------------------------------------------
class FeatureStoreTest(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()

    def tearDown(self):
        self.db.close()

    def test_catalog(self):
        catalog = feature_lineage.feature_catalog()
        self.assertIn("categories", catalog)
        self.assertGreater(catalog["feature_count"], 10)

    def test_lineage_known_feature(self):
        lineage = feature_lineage.feature_lineage(self.db, "current_ratio")
        self.assertEqual(lineage["feature"], "current_ratio")
        self.assertIn("source", lineage)

    def test_lineage_unknown_raises(self):
        with self.assertRaises(KeyError):
            feature_lineage.feature_lineage(self.db, "not_a_feature")

    def test_lineage_lists_consuming_models(self):
        result = train(_DATASET, "logistic_regression", cv_folds=3)
        registry.register_model(self.db, result)
        lineage = feature_lineage.feature_lineage(self.db, result.feature_names[0])
        self.assertGreaterEqual(len(lineage["consumed_by_models"]), 1)


if __name__ == "__main__":
    unittest.main()
