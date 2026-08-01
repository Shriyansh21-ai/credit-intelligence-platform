"""Enterprise ML Platform persistence models.

These tables give the MLOps layer durable, auditable, reproducible state

* :class:`MLDataset` — reproducible training-dataset snapshots (by spec).
* :class:`MLModel` — the model registry: one row per trained version.
* :class:`MLDeploymentEvent`— append-only deployment/approval/rollback history.
* :class:`MLPredictionLog` — every inference, with latency and outcome.
* :class:`MLExplanation` — stored explainability outputs (SHAP / reason codes).
* :class:`MLDriftReport` — drift-detection runs and their verdicts.
* :class:`MLPerformanceRecord` — model performance evaluated over time.
* :class:`MLFraudResult` — ML fraud/anomaly scoring outputs.

Everything is additive: no existing table is touched. Schema is created by an
Alembic migration (never ``create_all`` in the app), matching the platform
convention.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
)

from backend.app.db.database import Base


class MLDataset(Base):
    """A reproducible training-dataset snapshot.

    Synthetic datasets are fully determined by their ``spec`` + ``content_hash``
    so a model can be retrained on byte-identical data years later.
    """

    __tablename__ = "ml_datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    generator = Column(String, nullable=False, default="synthetic_v1")
    spec = Column(JSON, nullable=False, default=dict)
    feature_names = Column(JSON, nullable=False, default=list)
    n_rows = Column(Integer, nullable=False, default=0)
    n_features = Column(Integer, nullable=False, default=0)
    positive_rate = Column(Float, nullable=False, default=0.0)
    content_hash = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class MLModel(Base):
    """A registered, versioned model — the heart of the model registry."""

    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    # Logical model identity (e.g. "xgboost"); many versions share a key.
    model_key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    algorithm = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)

    dataset_id = Column(Integer, ForeignKey("ml_datasets.id"), nullable=True, index=True)
    parent_model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=True, index=True)

    hyperparameters = Column(JSON, nullable=False, default=dict)
    metrics = Column(JSON, nullable=False, default=dict)
    feature_names = Column(JSON, nullable=False, default=list)
    feature_set_version = Column(String, nullable=False, default="1.0")
    report = Column(JSON, nullable=False, default=dict)

    training_time_seconds = Column(Float, nullable=True)
    author = Column(String, nullable=True)
    artifact_path = Column(String, nullable=True)

    # Governance state machines.
    approval_status = Column(String, nullable=False, default="draft", index=True)
    # draft -> pending -> approved / rejected
    production_status = Column(String, nullable=False, default="none", index=True)
    # none / staging / production / archived / rolled_back

    trained_at = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MLDeploymentEvent(Base):
    """Append-only history of registry lifecycle actions (audit + rollback)."""

    __tablename__ = "ml_deployment_history"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    # register / submit_for_approval / approve / reject / promote / rollback / archive
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=True)
    actor = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class MLPredictionLog(Base):
    """One row per inference — powers serving history and model monitoring."""

    __tablename__ = "ml_prediction_logs"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=True, index=True)
    model_key = Column(String, nullable=True, index=True)
    model_version = Column(Integer, nullable=True)

    inference_type = Column(String, nullable=False, default="realtime", index=True)
    # realtime / batch / portfolio / async
    request_id = Column(String, nullable=True, index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(Integer, nullable=True, index=True)

    input_features = Column(JSON, nullable=True)
    probability_of_default = Column(Float, nullable=True)
    risk_score = Column(Integer, nullable=True)
    risk_grade = Column(String, nullable=True)
    approval = Column(Boolean, nullable=True)
    inference_mode = Column(String, nullable=True)

    latency_ms = Column(Float, nullable=True, index=True)
    cached = Column(Boolean, nullable=False, default=False)
    success = Column(Boolean, nullable=False, default=True, index=True)
    error = Column(Text, nullable=True)

    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class MLExplanation(Base):
    """A stored explanation for a prediction (SHAP / reason codes / narratives)."""

    __tablename__ = "ml_explanations"

    id = Column(Integer, primary_key=True, index=True)
    prediction_log_id = Column(Integer, ForeignKey("ml_prediction_logs.id"), nullable=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=True, index=True)
    model_key = Column(String, nullable=True, index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(Integer, nullable=True, index=True)

    method = Column(String, nullable=False, default="contribution")  # shap / contribution
    base_value = Column(Float, nullable=True)
    predicted_value = Column(Float, nullable=True)

    top_positive = Column(JSON, nullable=False, default=list)
    top_negative = Column(JSON, nullable=False, default=list)
    reason_codes = Column(JSON, nullable=False, default=list)
    waterfall = Column(JSON, nullable=False, default=list)
    feature_importance = Column(JSON, nullable=False, default=dict)

    business_summary = Column(Text, nullable=True)
    executive_summary = Column(Text, nullable=True)
    analyst_explanation = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class MLDriftReport(Base):
    """A drift-detection run comparing live features to a reference distribution."""

    __tablename__ = "ml_drift_reports"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=True, index=True)
    model_key = Column(String, nullable=True, index=True)
    report_type = Column(String, nullable=False, default="overall", index=True)
    # feature / target / schema / overall
    reference_dataset_id = Column(Integer, ForeignKey("ml_datasets.id"), nullable=True)

    psi_overall = Column(Float, nullable=True)
    drift_score = Column(Float, nullable=True)
    n_features = Column(Integer, nullable=True)
    n_drifted = Column(Integer, nullable=True)
    missing_feature_rate = Column(Float, nullable=True)

    drifted_features = Column(JSON, nullable=False, default=list)
    schema_changes = Column(JSON, nullable=False, default=dict)
    detail = Column(JSON, nullable=False, default=dict)

    threshold = Column(Float, nullable=True)
    breached = Column(Boolean, nullable=False, default=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class MLPerformanceRecord(Base):
    """A point-in-time evaluation of a model against realised outcomes."""

    __tablename__ = "ml_performance_records"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=True, index=True)
    model_key = Column(String, nullable=True, index=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow, index=True)
    n_samples = Column(Integer, nullable=False, default=0)
    metrics = Column(JSON, nullable=False, default=dict)
    business_kpis = Column(JSON, nullable=False, default=dict)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class MLFraudResult(Base):
    """An ML fraud / anomaly scoring result for an entity."""

    __tablename__ = "ml_fraud_results"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    method = Column(String, nullable=False, default="ensemble", index=True)
    # isolation_forest / lof / autoencoder / ensemble

    anomaly_score = Column(Float, nullable=True)
    fraud_probability = Column(Float, nullable=True)
    is_anomaly = Column(Boolean, nullable=False, default=False, index=True)
    cluster = Column(Integer, nullable=True)

    contributing_factors = Column(JSON, nullable=False, default=list)
    method_scores = Column(JSON, nullable=False, default=dict)

    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
