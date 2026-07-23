"""Enterprise ML Platform APIs (Phase 6).

One module exposing the full MLOps surface as a set of focused routers, all under
``/api/ml/*`` and additive to the existing AI Risk Intelligence router:

    /api/ml/feature-store   feature catalog, lineage, point-in-time (M1)
    /api/ml/training        training + algorithms (M2)
    /api/ml/registry        model registry + governance (M3, M14)
    /api/ml/serving         real-time / batch / portfolio / async inference (M4)
    /api/ml/explainability  SHAP, reason codes, narratives (M5)
    /api/ml/monitoring      operational + performance monitoring (M6, M8)
    /api/ml/drift           data & target drift detection (M7)
    /api/ml/retraining      champion/challenger retraining (M9)
    /api/ml/fraud           ML fraud / anomaly scoring (M10)
    /api/ml/portfolio-ml    portfolio ML analytics (M11)
    /api/ml/stress-ml       ML-driven macro stress testing (M12)

Permissions: ``mlops.view`` (read), ``mlops.train`` (train), ``mlops.deploy``
(governance/retrain), ``mlops.predict`` (inference), ``mlops.fraud`` (fraud).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.ml_platform import (
    ApprovalAction, BatchPredictRequest, DriftRequest, ExplainRequest,
    FraudBatchRequest, FraudScoreRequest, PortfolioRequest, PredictRequest,
    RetrainRequest, StressAllRequest, StressRequest, TargetDriftRequest, TrainRequest,
)
from backend.app.services.ml import drift as drift_svc
from backend.app.services.ml import fraud as fraud_svc
from backend.app.services.ml import registry
from backend.app.services.ml import retraining as retraining_svc
from backend.app.services.ml import serving
from backend.app.services.ml.data import make_synthetic_dataset
from backend.app.services.ml.explainability import ml_service as explain_svc
from backend.app.services.ml.features import lineage as feature_lineage
from backend.app.services.ml.monitoring import performance as perf_svc
from backend.app.services.ml.monitoring import service as mon_svc
from backend.app.services.ml.portfolio import ml_portfolio
from backend.app.services.ml.stress import ml_stress
from backend.app.services.ml.training import estimators, train
from backend.app.services.rbac import require_permission


def _actor_email(user: Optional[User]) -> Optional[str]:
    return getattr(user, "email", None) if user else None


def _require_model(db: Session, model_id: int):
    model = registry.service.get_model(db, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return model


# ===========================================================================
# M1 — Feature Store
# ===========================================================================
feature_store_router = APIRouter(prefix="/api/ml/feature-store", tags=["ML Feature Store"])


@feature_store_router.get("/catalog")
def feature_catalog(_user: User = Depends(require_permission("mlops.view"))):
    return feature_lineage.feature_catalog()


@feature_store_router.get("/lineage/{feature_name}")
def feature_lineage_view(feature_name: str, db: Session = Depends(get_db),
                         _user: User = Depends(require_permission("mlops.view"))):
    try:
        return feature_lineage.feature_lineage(db, feature_name)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown feature")


@feature_store_router.get("/point-in-time/{assessment_id}")
def point_in_time(assessment_id: int, as_of: Optional[str] = None,
                  db: Session = Depends(get_db),
                  _user: User = Depends(require_permission("mlops.view"))):
    vector = feature_lineage.point_in_time(db, assessment_id, as_of)
    if vector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No vector as of that time")
    return feature_lineage.lineage_for_vector(vector)


# ===========================================================================
# M2 — Training
# ===========================================================================
training_router = APIRouter(prefix="/api/ml/training", tags=["ML Training"])


@training_router.get("/algorithms")
def list_algorithms(_user: User = Depends(require_permission("mlops.view"))):
    return {
        "algorithms": [
            {"algorithm": algo, "backend_available": estimators.backend_available(algo),
             "default_hyperparameters": estimators.default_hyperparameters(algo)}
            for algo in estimators.SUPPORTED_ALGORITHMS
        ]
    }


@training_router.post("/train")
def train_model(payload: TrainRequest, db: Session = Depends(get_db),
                user: User = Depends(require_permission("mlops.train"))):
    if not estimators.backend_available(payload.algorithm):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Backend for '{payload.algorithm}' is not installed in this environment.",
        )
    dataset = make_synthetic_dataset(
        seed=payload.dataset_seed, n_rows=payload.n_rows, label_noise=payload.label_noise,
    )
    result = train(dataset, payload.algorithm, hyperparameters=payload.hyperparameters,
                   tune=payload.tune)
    response = {"training_report": result.report()}
    if payload.register:
        model = registry.register_model(
            db, result, model_key=payload.model_key, name=payload.name,
            author=_actor_email(user),
        )
        response["model"] = registry.model_as_dict(model)
    return response


# ===========================================================================
# M3 / M14 — Registry & governance
# ===========================================================================
registry_router = APIRouter(prefix="/api/ml/registry", tags=["ML Registry"])


@registry_router.get("/models")
def list_models(model_key: Optional[str] = None, approval_status: Optional[str] = None,
                production_status: Optional[str] = None, current_only: bool = False,
                db: Session = Depends(get_db),
                _user: User = Depends(require_permission("mlops.view"))):
    models = registry.list_models(db, model_key=model_key, approval_status=approval_status,
                                  production_status=production_status, current_only=current_only)
    return {"models": [registry.model_as_dict(m) for m in models]}


@registry_router.get("/models/{model_id}")
def get_model(model_id: int, db: Session = Depends(get_db),
              _user: User = Depends(require_permission("mlops.view"))):
    return registry.model_as_dict(_require_model(db, model_id), include_report=True)


@registry_router.get("/models/{model_id}/history")
def model_history(model_id: int, db: Session = Depends(get_db),
                  _user: User = Depends(require_permission("mlops.view"))):
    _require_model(db, model_id)
    return {"events": [registry.event_as_dict(e) for e in registry.deployment_history(db, model_id)]}


@registry_router.get("/models/{model_key}/versions")
def model_versions(model_key: str, db: Session = Depends(get_db),
                   _user: User = Depends(require_permission("mlops.view"))):
    return {"versions": [registry.model_as_dict(m) for m in registry.versions(db, model_key)]}


@registry_router.post("/models/{model_id}/submit")
def submit(model_id: int, payload: ApprovalAction = ApprovalAction(), db: Session = Depends(get_db),
           user: User = Depends(require_permission("mlops.train"))):
    return _governance(db, model_id, registry.submit_for_approval, user)


@registry_router.post("/models/{model_id}/approve")
def approve(model_id: int, payload: ApprovalAction = ApprovalAction(), db: Session = Depends(get_db),
            user: User = Depends(require_permission("mlops.deploy"))):
    return _governance(db, model_id, registry.approve, user, note=payload.note)


@registry_router.post("/models/{model_id}/reject")
def reject(model_id: int, payload: ApprovalAction = ApprovalAction(), db: Session = Depends(get_db),
           user: User = Depends(require_permission("mlops.deploy"))):
    return _governance(db, model_id, registry.reject, user, note=payload.note)


@registry_router.post("/models/{model_id}/promote")
def promote(model_id: int, payload: ApprovalAction = ApprovalAction(), db: Session = Depends(get_db),
            user: User = Depends(require_permission("mlops.deploy"))):
    return _governance(db, model_id, registry.promote, user, note=payload.note)


@registry_router.post("/models/{model_key}/rollback")
def rollback(model_key: str, payload: ApprovalAction = ApprovalAction(), db: Session = Depends(get_db),
             user: User = Depends(require_permission("mlops.deploy"))):
    try:
        model = registry.rollback(db, model_key, actor=_actor_email(user), note=payload.note)
    except registry.RegistryError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    serving.clear_caches()
    return registry.model_as_dict(model)


@registry_router.get("/datasets")
def list_datasets(db: Session = Depends(get_db),
                  _user: User = Depends(require_permission("mlops.view"))):
    from backend.app.models.ml_platform import MLDataset
    rows = db.query(MLDataset).order_by(MLDataset.created_at.desc()).limit(100).all()
    return {"datasets": [registry.dataset_as_dict(d) for d in rows]}


@registry_router.get("/models/{model_id}/reproducibility")
def model_reproducibility(model_id: int, db: Session = Depends(get_db),
                          _user: User = Depends(require_permission("mlops.view"))):
    """Governance (M14): the complete trail needed to reproduce a model exactly —
    dataset spec + content hash, hyperparameters, feature set and lineage."""
    from backend.app.models.ml_platform import MLDataset
    model = _require_model(db, model_id)
    dataset = (db.query(MLDataset).filter(MLDataset.id == model.dataset_id).first()
               if model.dataset_id else None)
    return {
        "model_id": model.id,
        "model_key": model.model_key,
        "version": model.version,
        "algorithm": model.algorithm,
        "feature_set_version": model.feature_set_version,
        "feature_names": model.feature_names,
        "hyperparameters": model.hyperparameters,
        "trained_at": model.trained_at,
        "author": model.author,
        "parent_model_id": model.parent_model_id,
        "dataset": registry.dataset_as_dict(dataset) if dataset else None,
        "reproducible": dataset is not None,
        "deployment_history": [registry.event_as_dict(e) for e in registry.deployment_history(db, model_id)],
    }


def _governance(db, model_id, fn, user, note=None):
    _require_model(db, model_id)
    try:
        model = fn(db, model_id, actor=_actor_email(user), **({"note": note} if note is not None else {}))
    except registry.RegistryError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    serving.clear_caches()
    return registry.model_as_dict(model)


# ===========================================================================
# M4 — Serving
# ===========================================================================
serving_router = APIRouter(prefix="/api/ml/serving", tags=["ML Serving"])


@serving_router.post("/predict")
def predict(payload: PredictRequest, db: Session = Depends(get_db),
            user: User = Depends(require_permission("mlops.predict"))):
    return serving.predict(db, payload.features, model_id=payload.model_id,
                           model_key=payload.model_key, entity_type=payload.entity_type,
                           entity_id=payload.entity_id, use_cache=payload.use_cache,
                           created_by=_actor_email(user))


@serving_router.post("/batch")
def batch(payload: BatchPredictRequest, db: Session = Depends(get_db),
          user: User = Depends(require_permission("mlops.predict"))):
    items = [{"features": i.features, "entity_id": i.entity_id} for i in payload.items]
    return serving.batch_predict(db, items, model_id=payload.model_id,
                                 model_key=payload.model_key, created_by=_actor_email(user))


@serving_router.post("/portfolio")
def portfolio(model_id: Optional[int] = None, model_key: Optional[str] = None,
              limit: int = 200, db: Session = Depends(get_db),
              user: User = Depends(require_permission("mlops.predict"))):
    return serving.portfolio_predict(db, model_id=model_id, model_key=model_key,
                                     limit=limit, created_by=_actor_email(user))


@serving_router.post("/async")
def async_predict(payload: PredictRequest, db: Session = Depends(get_db),
                  user: User = Depends(require_permission("mlops.predict"))):
    return serving.async_submit(db, payload.features, model_id=payload.model_id,
                                model_key=payload.model_key, entity_type=payload.entity_type,
                                entity_id=payload.entity_id, created_by=_actor_email(user))


@serving_router.get("/history")
def serving_history(model_id: Optional[int] = None, model_key: Optional[str] = None,
                    inference_type: Optional[str] = None, entity_id: Optional[int] = None,
                    limit: int = 100, db: Session = Depends(get_db),
                    _user: User = Depends(require_permission("mlops.view"))):
    rows = serving.prediction_history(db, model_id=model_id, model_key=model_key,
                                      inference_type=inference_type, entity_id=entity_id, limit=limit)
    return {"predictions": [serving.log_as_dict(r) for r in rows]}


@serving_router.get("/request/{request_id}")
def serving_request(request_id: str, db: Session = Depends(get_db),
                    _user: User = Depends(require_permission("mlops.view"))):
    rows = serving.get_by_request(db, request_id)
    return {"request_id": request_id, "predictions": [serving.log_as_dict(r) for r in rows]}


# ===========================================================================
# M5 — Explainability
# ===========================================================================
explain_router = APIRouter(prefix="/api/ml/explainability", tags=["ML Explainability"])


@explain_router.post("/explain")
def explain(payload: ExplainRequest, db: Session = Depends(get_db),
            _user: User = Depends(require_permission("mlops.view"))):
    return explain_svc.explain(db, payload.features, model_id=payload.model_id,
                               model_key=payload.model_key, entity_type=payload.entity_type,
                               entity_id=payload.entity_id, persist=payload.persist)


@explain_router.get("/history")
def explanation_history(model_id: Optional[int] = None, entity_id: Optional[int] = None,
                        limit: int = 50, db: Session = Depends(get_db),
                        _user: User = Depends(require_permission("mlops.view"))):
    rows = explain_svc.history(db, model_id=model_id, entity_id=entity_id, limit=limit)
    return {"explanations": [explain_svc.explanation_as_dict(r) for r in rows]}


@explain_router.get("/{explanation_id}")
def explanation_detail(explanation_id: int, db: Session = Depends(get_db),
                       _user: User = Depends(require_permission("mlops.view"))):
    row = explain_svc.get_explanation(db, explanation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Explanation not found")
    return explain_svc.explanation_as_dict(row)


# ===========================================================================
# M6 / M8 — Monitoring & performance
# ===========================================================================
monitoring_router = APIRouter(prefix="/api/ml/monitoring", tags=["ML Monitoring"])


@monitoring_router.get("/summary")
def monitoring_summary(model_id: Optional[int] = None, model_key: Optional[str] = None,
                       window_hours: Optional[int] = None, db: Session = Depends(get_db),
                       _user: User = Depends(require_permission("mlops.view"))):
    return mon_svc.summary(db, model_id=model_id, model_key=model_key, window_hours=window_hours)


@monitoring_router.get("/latency")
def monitoring_latency(model_id: Optional[int] = None, model_key: Optional[str] = None,
                       window_hours: Optional[int] = None, db: Session = Depends(get_db),
                       _user: User = Depends(require_permission("mlops.view"))):
    return mon_svc.latency_stats(db, model_id=model_id, model_key=model_key, window_hours=window_hours)


@monitoring_router.get("/failures")
def monitoring_failures(model_id: Optional[int] = None, model_key: Optional[str] = None,
                        limit: int = 50, db: Session = Depends(get_db),
                        _user: User = Depends(require_permission("mlops.view"))):
    return {"failures": mon_svc.failures(db, model_id=model_id, model_key=model_key, limit=limit)}


@monitoring_router.get("/usage")
def monitoring_usage(window_hours: Optional[int] = None, db: Session = Depends(get_db),
                     _user: User = Depends(require_permission("mlops.view"))):
    return mon_svc.usage_statistics(db, window_hours=window_hours)


@monitoring_router.get("/volume")
def monitoring_volume(model_id: Optional[int] = None, model_key: Optional[str] = None,
                      days: int = 14, db: Session = Depends(get_db),
                      _user: User = Depends(require_permission("mlops.view"))):
    return {"timeseries": mon_svc.volume_timeseries(db, model_id=model_id, model_key=model_key, days=days)}


@monitoring_router.post("/performance/{model_id}/evaluate")
def evaluate_performance(model_id: int, holdout_seed: int = 9999, n_rows: int = 1500,
                         db: Session = Depends(get_db),
                         _user: User = Depends(require_permission("mlops.train"))):
    model = _require_model(db, model_id)
    record = perf_svc.evaluate_reproduced(db, model, holdout_seed=holdout_seed, n_rows=n_rows)
    return perf_svc.record_as_dict(record)


@monitoring_router.get("/performance/{model_id}/trend")
def performance_trend(model_id: int, db: Session = Depends(get_db),
                      _user: User = Depends(require_permission("mlops.view"))):
    _require_model(db, model_id)
    rows = perf_svc.performance_trend(db, model_id=model_id)
    return {"trend": [perf_svc.record_as_dict(r) for r in rows]}


# ===========================================================================
# M7 — Drift
# ===========================================================================
drift_router = APIRouter(prefix="/api/ml/drift", tags=["ML Drift"])


@drift_router.post("/detect")
def detect_drift(payload: DriftRequest, db: Session = Depends(get_db),
                 _user: User = Depends(require_permission("mlops.view"))):
    model = _require_model(db, payload.model_id)
    report = drift_svc.detect(db, model, payload.current_rows, report_type=payload.report_type,
                              psi_threshold=payload.psi_threshold)
    return drift_svc.report_as_dict(report, include_detail=True)


@drift_router.post("/target")
def detect_target_drift(payload: TargetDriftRequest, db: Session = Depends(get_db),
                        _user: User = Depends(require_permission("mlops.view"))):
    model = _require_model(db, payload.model_id)
    report = drift_svc.detect_target_drift(db, model, payload.current_pds)
    return drift_svc.report_as_dict(report, include_detail=True)


@drift_router.get("/history")
def drift_history(model_id: Optional[int] = None, model_key: Optional[str] = None,
                  report_type: Optional[str] = None, limit: int = 50,
                  db: Session = Depends(get_db),
                  _user: User = Depends(require_permission("mlops.view"))):
    rows = drift_svc.history(db, model_id=model_id, model_key=model_key,
                             report_type=report_type, limit=limit)
    return {"reports": [drift_svc.report_as_dict(r) for r in rows]}


# ===========================================================================
# M9 — Retraining
# ===========================================================================
retraining_router = APIRouter(prefix="/api/ml/retraining", tags=["ML Retraining"])


@retraining_router.get("/should-retrain/{model_key}")
def should_retrain(model_key: str, db: Session = Depends(get_db),
                   _user: User = Depends(require_permission("mlops.view"))):
    return retraining_svc.should_retrain(db, model_key)


@retraining_router.post("/run")
def run_retraining(payload: RetrainRequest, db: Session = Depends(get_db),
                   user: User = Depends(require_permission("mlops.deploy"))):
    result = retraining_svc.run_retraining(
        db, payload.model_key, algorithm=payload.algorithm, trigger=payload.trigger,
        dataset_seed=payload.dataset_seed, n_rows=payload.n_rows, drift_shift=payload.drift_shift,
        author=_actor_email(user), auto_promote=payload.auto_promote, tune=payload.tune,
    )
    serving.clear_caches()
    return result


@retraining_router.get("/champion-challenger/{model_key}/{challenger_id}")
def champion_challenger(model_key: str, challenger_id: int, db: Session = Depends(get_db),
                        _user: User = Depends(require_permission("mlops.view"))):
    try:
        return retraining_svc.champion_challenger(db, model_key, challenger_id)
    except registry.RegistryError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ===========================================================================
# M10 — Fraud ML
# ===========================================================================
fraud_router = APIRouter(prefix="/api/ml/fraud", tags=["ML Fraud"])


@fraud_router.post("/score")
def fraud_score(payload: FraudScoreRequest, db: Session = Depends(get_db),
                user: User = Depends(require_permission("mlops.fraud"))):
    return fraud_svc.score(db, payload.features, entity_type=payload.entity_type,
                           entity_id=payload.entity_id, created_by=_actor_email(user))


@fraud_router.post("/batch")
def fraud_batch(payload: FraudBatchRequest, db: Session = Depends(get_db),
                user: User = Depends(require_permission("mlops.fraud"))):
    items = [{"features": i.features, "entity_id": i.entity_id} for i in payload.items]
    return fraud_svc.score_batch(db, items, created_by=_actor_email(user))


@fraud_router.get("/clusters")
def fraud_clusters(_user: User = Depends(require_permission("mlops.view"))):
    return {"clusters": fraud_svc.cluster_profiles()}


@fraud_router.get("/history")
def fraud_history(entity_id: Optional[int] = None, anomalies_only: bool = False,
                  limit: int = 100, db: Session = Depends(get_db),
                  _user: User = Depends(require_permission("mlops.view"))):
    rows = fraud_svc.history(db, entity_id=entity_id, anomalies_only=anomalies_only, limit=limit)
    return {"results": [fraud_svc.service.result_as_dict(r) for r in rows]}


# ===========================================================================
# M11 — Portfolio ML
# ===========================================================================
portfolio_router = APIRouter(prefix="/api/ml/portfolio-ml", tags=["ML Portfolio"])


@portfolio_router.post("/analyze")
def portfolio_analyze(payload: PortfolioRequest, db: Session = Depends(get_db),
                      _user: User = Depends(require_permission("mlops.view"))):
    positions = [p.model_dump() for p in payload.positions]
    return ml_portfolio.analyze(db, positions, model_id=payload.model_id, model_key=payload.model_key)


@portfolio_router.get("/current")
def portfolio_current(model_id: Optional[int] = None, model_key: Optional[str] = None,
                      limit: int = 300, db: Session = Depends(get_db),
                      _user: User = Depends(require_permission("mlops.view"))):
    return ml_portfolio.analyze_current(db, model_id=model_id, model_key=model_key, limit=limit)


# ===========================================================================
# M12 — Stress testing (ML)
# ===========================================================================
stress_router = APIRouter(prefix="/api/ml/stress-ml", tags=["ML Stress"])


@stress_router.get("/scenarios")
def stress_scenarios(_user: User = Depends(require_permission("mlops.view"))):
    return {"scenarios": ml_stress.available_scenarios()}


@stress_router.post("/run")
def stress_run(payload: StressRequest, db: Session = Depends(get_db),
               _user: User = Depends(require_permission("mlops.view"))):
    positions = [p.model_dump() for p in payload.positions]
    try:
        return ml_stress.stress_portfolio(db, positions, payload.scenario,
                                          severities=payload.severities,
                                          model_id=payload.model_id, model_key=payload.model_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@stress_router.post("/run-all")
def stress_run_all(payload: StressAllRequest, db: Session = Depends(get_db),
                   _user: User = Depends(require_permission("mlops.view"))):
    positions = [p.model_dump() for p in payload.positions]
    return ml_stress.stress_all(db, positions, severity=payload.severity,
                                model_id=payload.model_id, model_key=payload.model_key)


# All routers, wired into the app by main.py.
ROUTERS: List[APIRouter] = [
    feature_store_router, training_router, registry_router, serving_router,
    explain_router, monitoring_router, drift_router, retraining_router,
    fraud_router, portfolio_router, stress_router,
]
