"""Enterprise ML Platform tables

Revision ID: a7b8c9d0e1f2
Revises: d6f7a8b9c0e1
Create Date: 2026-07-22 09:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "d6f7a8b9c0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- ml_datasets --------------------------------------------------------
    op.create_table(
        "ml_datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("generator", sa.String(), nullable=False, server_default="synthetic_v1"),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("feature_names", sa.JSON(), nullable=False),
        sa.Column("n_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_features", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("positive_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ml_datasets_name", "ml_datasets", ["name"])
    op.create_index("ix_ml_datasets_content_hash", "ml_datasets", ["content_hash"])
    op.create_index("ix_ml_datasets_created_at", "ml_datasets", ["created_at"])

    # -- ml_models ----------------------------------------------------------
    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("algorithm", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("ml_datasets.id"), nullable=True),
        sa.Column("parent_model_id", sa.Integer(), sa.ForeignKey("ml_models.id"), nullable=True),
        sa.Column("hyperparameters", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("feature_names", sa.JSON(), nullable=False),
        sa.Column("feature_set_version", sa.String(), nullable=False, server_default="1.0"),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("training_time_seconds", sa.Float(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("artifact_path", sa.String(), nullable=True),
        sa.Column("approval_status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("production_status", sa.String(), nullable=False, server_default="none"),
        sa.Column("trained_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ml_models_model_key", "ml_models", ["model_key"])
    op.create_index("ix_ml_models_dataset_id", "ml_models", ["dataset_id"])
    op.create_index("ix_ml_models_parent_model_id", "ml_models", ["parent_model_id"])
    op.create_index("ix_ml_models_approval_status", "ml_models", ["approval_status"])
    op.create_index("ix_ml_models_production_status", "ml_models", ["production_status"])
    op.create_index("ix_ml_models_created_at", "ml_models", ["created_at"])

    # -- ml_deployment_history ---------------------------------------------
    op.create_table(
        "ml_deployment_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("ml_models.id"), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("from_status", sa.String(), nullable=True),
        sa.Column("to_status", sa.String(), nullable=True),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ml_deployment_history_model_id", "ml_deployment_history", ["model_id"])
    op.create_index("ix_ml_deployment_history_action", "ml_deployment_history", ["action"])
    op.create_index("ix_ml_deployment_history_created_at", "ml_deployment_history", ["created_at"])

    # -- ml_prediction_logs -------------------------------------------------
    op.create_table(
        "ml_prediction_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("ml_models.id"), nullable=True),
        sa.Column("model_key", sa.String(), nullable=True),
        sa.Column("model_version", sa.Integer(), nullable=True),
        sa.Column("inference_type", sa.String(), nullable=False, server_default="realtime"),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("input_features", sa.JSON(), nullable=True),
        sa.Column("probability_of_default", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_grade", sa.String(), nullable=True),
        sa.Column("approval", sa.Boolean(), nullable=True),
        sa.Column("inference_mode", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("model_id", "model_key", "inference_type", "request_id",
                "entity_type", "entity_id", "latency_ms", "success", "created_at"):
        op.create_index(f"ix_ml_prediction_logs_{col}", "ml_prediction_logs", [col])

    # -- ml_explanations ----------------------------------------------------
    op.create_table(
        "ml_explanations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prediction_log_id", sa.Integer(), sa.ForeignKey("ml_prediction_logs.id"), nullable=True),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("ml_models.id"), nullable=True),
        sa.Column("model_key", sa.String(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("method", sa.String(), nullable=False, server_default="contribution"),
        sa.Column("base_value", sa.Float(), nullable=True),
        sa.Column("predicted_value", sa.Float(), nullable=True),
        sa.Column("top_positive", sa.JSON(), nullable=False),
        sa.Column("top_negative", sa.JSON(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("waterfall", sa.JSON(), nullable=False),
        sa.Column("feature_importance", sa.JSON(), nullable=False),
        sa.Column("business_summary", sa.Text(), nullable=True),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("analyst_explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("prediction_log_id", "model_id", "model_key", "entity_type", "entity_id", "created_at"):
        op.create_index(f"ix_ml_explanations_{col}", "ml_explanations", [col])

    # -- ml_drift_reports ---------------------------------------------------
    op.create_table(
        "ml_drift_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("ml_models.id"), nullable=True),
        sa.Column("model_key", sa.String(), nullable=True),
        sa.Column("report_type", sa.String(), nullable=False, server_default="overall"),
        sa.Column("reference_dataset_id", sa.Integer(), sa.ForeignKey("ml_datasets.id"), nullable=True),
        sa.Column("psi_overall", sa.Float(), nullable=True),
        sa.Column("drift_score", sa.Float(), nullable=True),
        sa.Column("n_features", sa.Integer(), nullable=True),
        sa.Column("n_drifted", sa.Integer(), nullable=True),
        sa.Column("missing_feature_rate", sa.Float(), nullable=True),
        sa.Column("drifted_features", sa.JSON(), nullable=False),
        sa.Column("schema_changes", sa.JSON(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("breached", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("model_id", "model_key", "report_type", "breached", "created_at"):
        op.create_index(f"ix_ml_drift_reports_{col}", "ml_drift_reports", [col])

    # -- ml_performance_records --------------------------------------------
    op.create_table(
        "ml_performance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("ml_models.id"), nullable=True),
        sa.Column("model_key", sa.String(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
        sa.Column("n_samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("business_kpis", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("model_id", "model_key", "evaluated_at", "created_at"):
        op.create_index(f"ix_ml_performance_records_{col}", "ml_performance_records", [col])

    # -- ml_fraud_results ---------------------------------------------------
    op.create_table(
        "ml_fraud_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("method", sa.String(), nullable=False, server_default="ensemble"),
        sa.Column("anomaly_score", sa.Float(), nullable=True),
        sa.Column("fraud_probability", sa.Float(), nullable=True),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cluster", sa.Integer(), nullable=True),
        sa.Column("contributing_factors", sa.JSON(), nullable=False),
        sa.Column("method_scores", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("entity_type", "entity_id", "method", "is_anomaly", "created_at"):
        op.create_index(f"ix_ml_fraud_results_{col}", "ml_fraud_results", [col])


def downgrade() -> None:
    for table in ("ml_fraud_results", "ml_performance_records", "ml_drift_reports",
                  "ml_explanations", "ml_prediction_logs", "ml_deployment_history",
                  "ml_models", "ml_datasets"):
        op.drop_table(table)
