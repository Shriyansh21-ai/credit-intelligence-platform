"""Autonomous AI Banking Intelligence Platform tables (Phase 9)

Fully additive: creates the knowledge-graph, real-time monitoring, early-warning,
AI copilot, scenario, stress-testing, portfolio-optimization, RM-workspace,
NL-analytics, recommendation, workflow-intelligence, model-governance and
data-lake tables. Nothing from Phases 1-8 is altered or dropped.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-24 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- kg_entities --------------------------------------------------------
    op.create_table(
        "kg_entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("ref", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "entity_type", "ref", name="uq_kg_entity_ref"),
    )
    op.create_index("ix_kg_entities_tenant_id", "kg_entities", ["tenant_id"])
    op.create_index("ix_kg_entities_entity_type", "kg_entities", ["entity_type"])
    op.create_index("ix_kg_entities_ref", "kg_entities", ["ref"])

    # -- kg_relationships ---------------------------------------------------
    op.create_table(
        "kg_relationships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("kg_entities.id"), nullable=False),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("kg_entities.id"), nullable=False),
        sa.Column("rel_type", sa.String(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("exposure", sa.Float(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("source_id", "target_id", "rel_type", name="uq_kg_edge"),
    )
    op.create_index("ix_kg_relationships_tenant_id", "kg_relationships", ["tenant_id"])
    op.create_index("ix_kg_relationships_source_id", "kg_relationships", ["source_id"])
    op.create_index("ix_kg_relationships_target_id", "kg_relationships", ["target_id"])
    op.create_index("ix_kg_relationships_rel_type", "kg_relationships", ["rel_type"])

    # -- monitoring_signals -------------------------------------------------
    op.create_table(
        "monitoring_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("company_ref", sa.String(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False, server_default="neutral"),
        sa.Column("magnitude", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(), nullable=False, server_default="info"),
        sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_monitoring_signals_tenant_id", "monitoring_signals", ["tenant_id"])
    op.create_index("ix_monitoring_signals_company_ref", "monitoring_signals", ["company_ref"])
    op.create_index("ix_monitoring_signals_source", "monitoring_signals", ["source"])
    op.create_index("ix_monitoring_signals_severity", "monitoring_signals", ["severity"])
    op.create_index("ix_monitoring_signals_detected_at", "monitoring_signals", ["detected_at"])

    # -- intelligence_alerts ------------------------------------------------
    op.create_table(
        "intelligence_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("company_ref", sa.String(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("alert_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False, server_default="medium"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("business_impact", sa.Text(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("dedup_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    for col in ("tenant_id", "company_ref", "assessment_id", "category", "severity",
                "priority_score", "status", "dedup_key", "created_at"):
        op.create_index(f"ix_intelligence_alerts_{col}", "intelligence_alerts", [col])

    # -- ews_assessments ----------------------------------------------------
    op.create_table(
        "ews_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("company_ref", sa.String(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=True),
        sa.Column("ews_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ews_band", sa.String(), nullable=False, server_default="green"),
        sa.Column("signal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ews_assessments_tenant_id", "ews_assessments", ["tenant_id"])
    op.create_index("ix_ews_assessments_company_ref", "ews_assessments", ["company_ref"])
    op.create_index("ix_ews_assessments_created_at", "ews_assessments", ["created_at"])

    # -- copilot_conversations ----------------------------------------------
    op.create_table(
        "copilot_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("context_ref", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_copilot_conversations_tenant_id", "copilot_conversations", ["tenant_id"])
    op.create_index("ix_copilot_conversations_user_id", "copilot_conversations", ["user_id"])

    # -- copilot_messages ---------------------------------------------------
    op.create_table(
        "copilot_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("copilot_conversations.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("grounding", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_copilot_messages_conversation_id", "copilot_messages", ["conversation_id"])
    op.create_index("ix_copilot_messages_created_at", "copilot_messages", ["created_at"])

    # -- simulation_runs ----------------------------------------------------
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("company_ref", sa.String(), nullable=True),
        sa.Column("assessment_id", sa.Integer(), nullable=True),
        sa.Column("scenario_types", sa.JSON(), nullable=False),
        sa.Column("shocks", sa.JSON(), nullable=False),
        sa.Column("baseline", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("delta", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_simulation_runs_tenant_id", "simulation_runs", ["tenant_id"])
    op.create_index("ix_simulation_runs_company_ref", "simulation_runs", ["company_ref"])
    op.create_index("ix_simulation_runs_created_at", "simulation_runs", ["created_at"])

    # -- stress_test_runs ---------------------------------------------------
    op.create_table(
        "stress_test_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("scope", sa.String(), nullable=False, server_default="portfolio"),
        sa.Column("scope_ref", sa.String(), nullable=True),
        sa.Column("scenario", sa.String(), nullable=False, server_default="severe"),
        sa.Column("custom_shocks", sa.JSON(), nullable=True),
        sa.Column("positions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_stress_test_runs_tenant_id", "stress_test_runs", ["tenant_id"])
    op.create_index("ix_stress_test_runs_created_at", "stress_test_runs", ["created_at"])

    # -- portfolio_optimizations --------------------------------------------
    op.create_table(
        "portfolio_optimizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("objective", sa.String(), nullable=False, server_default="risk_adjusted_return"),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_portfolio_optimizations_tenant_id", "portfolio_optimizations", ["tenant_id"])
    op.create_index("ix_portfolio_optimizations_created_at", "portfolio_optimizations", ["created_at"])

    # -- rm_interactions ----------------------------------------------------
    op.create_table(
        "rm_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("company_ref", sa.String(), nullable=False),
        sa.Column("rm_user_id", sa.Integer(), nullable=True),
        sa.Column("interaction_type", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_rm_interactions_tenant_id", "rm_interactions", ["tenant_id"])
    op.create_index("ix_rm_interactions_company_ref", "rm_interactions", ["company_ref"])
    op.create_index("ix_rm_interactions_occurred_at", "rm_interactions", ["occurred_at"])

    # -- rm_opportunities ---------------------------------------------------
    op.create_table(
        "rm_opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("company_ref", sa.String(), nullable=False),
        sa.Column("product", sa.String(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("estimated_value", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("status", sa.String(), nullable=False, server_default="identified"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_rm_opportunities_tenant_id", "rm_opportunities", ["tenant_id"])
    op.create_index("ix_rm_opportunities_company_ref", "rm_opportunities", ["company_ref"])

    # -- nl_query_logs ------------------------------------------------------
    op.create_table(
        "nl_query_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(), nullable=True),
        sa.Column("structured_query", sa.JSON(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_nl_query_logs_tenant_id", "nl_query_logs", ["tenant_id"])
    op.create_index("ix_nl_query_logs_intent", "nl_query_logs", ["intent"])
    op.create_index("ix_nl_query_logs_created_at", "nl_query_logs", ["created_at"])

    # -- recommendations ----------------------------------------------------
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("company_ref", sa.String(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("priority", sa.String(), nullable=False, server_default="medium"),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("supporting_metrics", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_recommendations_tenant_id", "recommendations", ["tenant_id"])
    op.create_index("ix_recommendations_company_ref", "recommendations", ["company_ref"])
    op.create_index("ix_recommendations_action", "recommendations", ["action"])
    op.create_index("ix_recommendations_created_at", "recommendations", ["created_at"])

    # -- workflow_actions ---------------------------------------------------
    op.create_table(
        "workflow_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("company_ref", sa.String(), nullable=True),
        sa.Column("assessment_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False, server_default="proposed"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_workflow_actions_tenant_id", "workflow_actions", ["tenant_id"])
    op.create_index("ix_workflow_actions_company_ref", "workflow_actions", ["company_ref"])
    op.create_index("ix_workflow_actions_action_type", "workflow_actions", ["action_type"])
    op.create_index("ix_workflow_actions_status", "workflow_actions", ["status"])

    # -- model_governance_events --------------------------------------------
    op.create_table(
        "model_governance_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("model_key", sa.String(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_model_governance_events_model_id", "model_governance_events", ["model_id"])
    op.create_index("ix_model_governance_events_model_key", "model_governance_events", ["model_key"])
    op.create_index("ix_model_governance_events_event_type", "model_governance_events", ["event_type"])
    op.create_index("ix_model_governance_events_created_at", "model_governance_events", ["created_at"])

    # -- model_validations --------------------------------------------------
    op.create_table(
        "model_validations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("model_key", sa.String(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("validator", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_model_validations_model_id", "model_validations", ["model_id"])
    op.create_index("ix_model_validations_model_key", "model_validations", ["model_key"])

    # -- datalake_datasets --------------------------------------------------
    op.create_table(
        "datalake_datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("namespace", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schema_fields", sa.JSON(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_ingested_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "namespace", name="uq_datalake_ns"),
    )
    op.create_index("ix_datalake_datasets_tenant_id", "datalake_datasets", ["tenant_id"])
    op.create_index("ix_datalake_datasets_namespace", "datalake_datasets", ["namespace"])

    # -- datalake_objects ---------------------------------------------------
    op.create_table(
        "datalake_objects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("namespace", sa.String(), nullable=False),
        sa.Column("partition", sa.String(), nullable=True),
        sa.Column("entity_ref", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("namespace", "partition", "content_hash", name="uq_datalake_obj"),
    )
    for col in ("tenant_id", "namespace", "partition", "entity_ref", "content_hash", "ingested_at"):
        op.create_index(f"ix_datalake_objects_{col}", "datalake_objects", [col])


def downgrade() -> None:
    for table in (
        "datalake_objects", "datalake_datasets", "model_validations",
        "model_governance_events", "workflow_actions", "recommendations",
        "nl_query_logs", "rm_opportunities", "rm_interactions",
        "portfolio_optimizations", "stress_test_runs", "simulation_runs",
        "copilot_messages", "copilot_conversations", "ews_assessments",
        "intelligence_alerts", "monitoring_signals", "kg_relationships",
        "kg_entities",
    ):
        op.drop_table(table)
