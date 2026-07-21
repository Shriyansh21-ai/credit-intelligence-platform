"""Enterprise AI Risk Intelligence API (Phase 4, Milestone 10).

Versioned under ``/api/ml``. Routes are intentionally thin: they validate input,
delegate to services and stores, and shape the response. No business logic lives
here.

    GET  /api/ml/models                      registered risk models + metadata
    GET  /api/ml/features/{assessment_id}    stored feature vector for an assessment
    GET  /api/ml/features                     latest feature vector for the user
    POST /api/ml/features/compute             ad-hoc feature vector (optional persist)
    GET  /api/ml/predict/{assessment_id}     prediction from the stored vector
    POST /api/ml/predict                      ad-hoc prediction
    GET  /api/ml/explain/{assessment_id}     explanation (stored or computed)
    POST /api/ml/explain                      ad-hoc explanation (optional persist)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.enterprise_assessment import EnterpriseAssessment
from backend.app.models.user import User
from backend.app.schemas.ml import (
    AlertScanRequest,
    ExplainRequest,
    FeatureComputeRequest,
    PredictRequest,
    ReportRequest,
    ScenarioRequest,
    StressTestRequest,
)
from backend.app.services.ml import facade, inference
from backend.app.services.ml.explainability import explanation_store, service as explain_service
from backend.app.services.ml.features import feature_serializer, feature_store
from backend.app.services.ml.models import available_models
from backend.app.services.ml.scenario import scenario_engine
from backend.app.services.ml.stress import (
    available_scenarios,
    run_stress_test,
)
from backend.app.services.ml.portfolio import analyze as analyze_portfolio_positions
from backend.app.services.ml.portfolio import repository as portfolio_repository
from backend.app.services.ml.alerts import alert_engine, alert_store
from backend.app.services.ml.report import build_report_from_engine_input

router = APIRouter(prefix="/api/ml", tags=["AI Risk Intelligence"])

_FEATURES_NOT_FOUND = (
    "No feature vector found for this assessment. Vectors are generated when an "
    "assessment is created; older assessments may predate this feature."
)


def _owned_vector(db: Session, assessment_id: int, user: User):
    record = feature_store.get_current_for_assessment(db, assessment_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_FEATURES_NOT_FOUND)
    return record


def _assessment_engine_input(db: Session, assessment_id: int, user: User) -> dict:
    """Load the saved engine input for an owned assessment (404 if missing)."""
    record = (
        db.query(EnterpriseAssessment)
        .filter(EnterpriseAssessment.id == assessment_id,
                EnterpriseAssessment.user_id == user.id)
        .first()
    )
    if record is None or not record.engine_input:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found or has no saved input to drive this analysis.",
        )
    return dict(record.engine_input)


def _resolve_source(request, db: Session, user: User) -> dict:
    """Resolve an ML request into a concrete financial source.

    Explicit inputs win; otherwise the persisted assessment's saved engine input
    is used, so any endpoint can be driven by ``assessment_id`` alone.
    """
    src = {
        "engine_input": request.engine_input,
        "financials": request.financials,
        "context": request.context,
        "previous": request.previous,
        "features": request.features,
    }
    has_explicit = request.engine_input or request.financials or request.features
    if not has_explicit and getattr(request, "assessment_id", None):
        src["engine_input"] = _assessment_engine_input(db, request.assessment_id, user)
    return src


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@router.get("/models")
async def list_models(current_user: User = Depends(get_current_user)):
    return {"models": available_models()}


# ---------------------------------------------------------------------------
# Features (Milestone 1)
# ---------------------------------------------------------------------------

@router.post("/features/compute")
async def compute_features(
    request: FeatureComputeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vector = facade.vector_from_source(**_resolve_source(request, db, current_user))
    if request.persist:
        record = feature_store.save_feature_vector(
            db, user_id=current_user.id, assessment_id=request.assessment_id, vector=vector
        )
        vector = {**vector, "id": record.id, "version": record.version}
    return vector


@router.get("/features")
async def latest_features(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = feature_store.latest_for_user(db, current_user.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No feature vector yet. Run an enterprise assessment to generate one.",
        )
    return feature_serializer.serialize_record(record)


@router.get("/features/{assessment_id}")
async def get_features(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _owned_vector(db, assessment_id, current_user)
    return feature_serializer.serialize_record(record)


# ---------------------------------------------------------------------------
# Predict (Milestone 2)
# ---------------------------------------------------------------------------

@router.post("/predict")
async def predict(
    request: PredictRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vector = facade.vector_from_source(**_resolve_source(request, db, current_user))
    return inference.predict_from_vector(vector, model_type=request.model_type)


@router.get("/predict/{assessment_id}")
async def predict_for_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _owned_vector(db, assessment_id, current_user)
    return inference.predict_from_vector({"features": record.features or []})


# ---------------------------------------------------------------------------
# Explain (Milestone 3)
# ---------------------------------------------------------------------------

@router.post("/explain")
async def explain(
    request: ExplainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vector = facade.vector_from_source(**_resolve_source(request, db, current_user))
    explanation = explain_service.explain_vector(
        vector, model_type=request.model_type, method=request.method
    )
    if request.persist:
        record = explanation_store.save_explanation(
            db, user_id=current_user.id, assessment_id=request.assessment_id,
            explanation=explanation,
        )
        explanation = {**explanation, "id": record.id, "version": record.version}
    return explanation


@router.get("/explain/{assessment_id}")
async def explain_for_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _owned_vector(db, assessment_id, current_user)
    return explain_service.explain_vector({"features": record.features or []})


# ---------------------------------------------------------------------------
# Scenario simulation (Milestone 4)
# ---------------------------------------------------------------------------

@router.get("/scenario/factors")
async def scenario_factors(current_user: User = Depends(get_current_user)):
    return {"factors": scenario_engine.available_factors()}


@router.post("/scenario")
async def run_scenario(
    request: ScenarioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # The scorecard consumes an assessment engine-input; prefer it, else fall
    # back to the raw financials mapping (resolving a saved assessment if given).
    src = _resolve_source(request, db, current_user)
    base_input = src["engine_input"] or src["financials"] or {}
    return scenario_engine.simulate(
        base_input, request.adjustments, model_type=request.model_type
    )


# ---------------------------------------------------------------------------
# Stress testing (Milestone 5)
# ---------------------------------------------------------------------------

@router.get("/stress-test/scenarios")
async def stress_scenarios(current_user: User = Depends(get_current_user)):
    return {"scenarios": available_scenarios()}


@router.post("/stress-test")
async def stress_test(
    request: StressTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    src = _resolve_source(request, db, current_user)
    base_input = src["engine_input"] or src["financials"] or {}
    return run_stress_test(base_input, request.scenarios, model_type=request.model_type)


# ---------------------------------------------------------------------------
# Portfolio intelligence (Milestone 6)
# ---------------------------------------------------------------------------

@router.get("/portfolio")
async def portfolio(
    industry: str | None = None,
    rating: str | None = None,
    region: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Portfolio-level risk intelligence across the user's enterprise
    assessments. Optional query filters enable drill-down by industry, rating or
    region."""
    positions = portfolio_repository.positions_for_user(
        db, current_user.id, industry=industry, rating=rating, region=region
    )
    result = analyze_portfolio_positions(positions)
    result["filters"] = {"industry": industry, "rating": rating, "region": region}
    return result


# ---------------------------------------------------------------------------
# Early warning alerts (Milestone 7)
# ---------------------------------------------------------------------------

@router.post("/alerts/scan")
async def scan_alerts(
    request: AlertScanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    src = _resolve_source(request, db, current_user)
    vector = facade.vector_from_source(**src)
    result = alert_engine.scan(vector, engine_input=src["engine_input"])
    if request.persist:
        alert_store.save_alerts(
            db, user_id=current_user.id, assessment_id=request.assessment_id,
            scan_result=result,
        )
    return result


@router.get("/alerts")
async def list_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"alerts": alert_store.current_for_user(db, current_user.id)}


@router.get("/alerts/{assessment_id}")
async def alerts_for_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_vector(db, assessment_id, current_user)
    return {
        "assessment_id": assessment_id,
        "alerts": alert_store.current_for_assessment(db, assessment_id),
    }


# ---------------------------------------------------------------------------
# Analyst Copilot credit memo (Milestone 8)
# ---------------------------------------------------------------------------

@router.post("/report")
async def analyst_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    src = _resolve_source(request, db, current_user)
    engine_input = src["engine_input"] or src["financials"] or {}
    return build_report_from_engine_input(engine_input, model_type=request.model_type)


@router.get("/report/{assessment_id}")
async def report_for_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engine_input = _assessment_engine_input(db, assessment_id, current_user)
    return build_report_from_engine_input(engine_input)


@router.get("/stress-test/{assessment_id}")
async def stress_test_for_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engine_input = _assessment_engine_input(db, assessment_id, current_user)
    return run_stress_test(engine_input)
