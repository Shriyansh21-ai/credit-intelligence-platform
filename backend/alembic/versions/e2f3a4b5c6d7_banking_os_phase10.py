"""Enterprise Banking Operating System tables (Phase 10)

Fully additive: creates the policy-engine, loan-committee, enterprise-search,
prompt-management and multi-LLM tables. Nothing from Phases 1-9 is altered or
dropped.

Revision ID: e2f3a4b5c6d7
Revises: d0e1f2a3b4c5
Create Date: 2026-07-26 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- os_policies --------------------------------------------------------
    op.create_table(
        "os_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "key", name="uq_os_policy_key"),
    )
    op.create_index("ix_os_policies_tenant_id", "os_policies", ["tenant_id"])
    op.create_index("ix_os_policies_key", "os_policies", ["key"])
    op.create_index("ix_os_policies_domain", "os_policies", ["domain"])
    op.create_index("ix_os_policies_status", "os_policies", ["status"])

    # -- os_policy_versions -------------------------------------------------
    op.create_table(
        "os_policy_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("os_policies.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("combine", sa.String(), nullable=False, server_default="first_match"),
        sa.Column("default_decision", sa.String(), nullable=False, server_default="pass"),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("policy_id", "version", name="uq_os_policy_version"),
    )
    op.create_index("ix_os_policy_versions_policy_id", "os_policy_versions", ["policy_id"])

    # -- os_policy_evaluations ----------------------------------------------
    op.create_table(
        "os_policy_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("policy_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("subject_ref", sa.String(), nullable=True),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("matched_rules", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_policy_evaluations_tenant_id", "os_policy_evaluations", ["tenant_id"])
    op.create_index("ix_os_policy_evaluations_policy_id", "os_policy_evaluations", ["policy_id"])
    op.create_index("ix_os_policy_evaluations_policy_key", "os_policy_evaluations", ["policy_key"])
    op.create_index("ix_os_policy_evaluations_subject_ref", "os_policy_evaluations", ["subject_ref"])
    op.create_index("ix_os_policy_evaluations_decision", "os_policy_evaluations", ["decision"])

    # -- os_committees ------------------------------------------------------
    op.create_table(
        "os_committees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quorum", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("members", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_committees_tenant_id", "os_committees", ["tenant_id"])

    # -- os_committee_meetings ----------------------------------------------
    op.create_table(
        "os_committee_meetings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("committee_id", sa.Integer(), sa.ForeignKey("os_committees.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="scheduled"),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("attendees", sa.JSON(), nullable=False),
        sa.Column("minutes", sa.Text(), nullable=True),
        sa.Column("chair", sa.String(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_committee_meetings_tenant_id", "os_committee_meetings", ["tenant_id"])
    op.create_index("ix_os_committee_meetings_committee_id", "os_committee_meetings", ["committee_id"])
    op.create_index("ix_os_committee_meetings_status", "os_committee_meetings", ["status"])

    # -- os_agenda_items ----------------------------------------------------
    op.create_table(
        "os_agenda_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("os_committee_meetings.id"), nullable=False),
        sa.Column("order_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("subject_ref", sa.String(), nullable=True),
        sa.Column("assessment_id", sa.Integer(), nullable=True),
        sa.Column("presenter", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("proposed_action", sa.String(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("materials", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("decision", sa.String(), nullable=True),
        sa.Column("decision_rationale", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_agenda_items_tenant_id", "os_agenda_items", ["tenant_id"])
    op.create_index("ix_os_agenda_items_meeting_id", "os_agenda_items", ["meeting_id"])
    op.create_index("ix_os_agenda_items_subject_ref", "os_agenda_items", ["subject_ref"])
    op.create_index("ix_os_agenda_items_status", "os_agenda_items", ["status"])

    # -- os_committee_votes -------------------------------------------------
    op.create_table(
        "os_committee_votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("agenda_item_id", sa.Integer(), sa.ForeignKey("os_agenda_items.id"), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("voter_user_id", sa.Integer(), nullable=True),
        sa.Column("voter_name", sa.String(), nullable=True),
        sa.Column("vote", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("signature", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("agenda_item_id", "voter_user_id", name="uq_os_vote_member"),
    )
    op.create_index("ix_os_committee_votes_tenant_id", "os_committee_votes", ["tenant_id"])
    op.create_index("ix_os_committee_votes_agenda_item_id", "os_committee_votes", ["agenda_item_id"])
    op.create_index("ix_os_committee_votes_meeting_id", "os_committee_votes", ["meeting_id"])

    # -- os_search_documents ------------------------------------------------
    op.create_table(
        "os_search_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("ref", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("doc_metadata", sa.JSON(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("numeric_fields", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "doc_type", "ref", name="uq_os_search_doc"),
    )
    op.create_index("ix_os_search_documents_tenant_id", "os_search_documents", ["tenant_id"])
    op.create_index("ix_os_search_documents_doc_type", "os_search_documents", ["doc_type"])
    op.create_index("ix_os_search_documents_ref", "os_search_documents", ["ref"])

    # -- os_saved_searches --------------------------------------------------
    op.create_table(
        "os_saved_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_saved_searches_tenant_id", "os_saved_searches", ["tenant_id"])
    op.create_index("ix_os_saved_searches_user_id", "os_saved_searches", ["user_id"])

    # -- os_search_history --------------------------------------------------
    op.create_table(
        "os_search_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_search_history_tenant_id", "os_search_history", ["tenant_id"])
    op.create_index("ix_os_search_history_user_id", "os_search_history", ["user_id"])

    # -- os_prompt_templates ------------------------------------------------
    op.create_table(
        "os_prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deployed_version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "key", name="uq_os_prompt_key"),
    )
    op.create_index("ix_os_prompt_templates_tenant_id", "os_prompt_templates", ["tenant_id"])
    op.create_index("ix_os_prompt_templates_key", "os_prompt_templates", ["key"])
    op.create_index("ix_os_prompt_templates_category", "os_prompt_templates", ["category"])

    # -- os_prompt_versions -------------------------------------------------
    op.create_table(
        "os_prompt_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("os_prompt_templates.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("model_hint", sa.String(), nullable=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("eval_score", sa.Float(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("template_id", "version", name="uq_os_prompt_version"),
    )
    op.create_index("ix_os_prompt_versions_template_id", "os_prompt_versions", ["template_id"])

    # -- os_prompt_evaluations ----------------------------------------------
    op.create_table(
        "os_prompt_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("cases", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_prompt_evaluations_template_id", "os_prompt_evaluations", ["template_id"])

    # -- os_llm_providers ---------------------------------------------------
    op.create_table(
        "os_llm_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("cost_per_1k_input", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cost_per_1k_output", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_os_llm_provider"),
    )
    op.create_index("ix_os_llm_providers_tenant_id", "os_llm_providers", ["tenant_id"])
    op.create_index("ix_os_llm_providers_name", "os_llm_providers", ["name"])

    # -- os_llm_invocations -------------------------------------------------
    op.create_table(
        "os_llm_invocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("strategy", sa.String(), nullable=True),
        sa.Column("prompt_ref", sa.String(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality", sa.Float(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("routed_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_llm_invocations_tenant_id", "os_llm_invocations", ["tenant_id"])
    op.create_index("ix_os_llm_invocations_provider", "os_llm_invocations", ["provider"])
    op.create_index("ix_os_llm_invocations_prompt_ref", "os_llm_invocations", ["prompt_ref"])

    # -- os_datasets --------------------------------------------------------
    op.create_table(
        "os_datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("classification", sa.String(), nullable=False, server_default="internal"),
        sa.Column("schema_fields", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_os_dataset_name"),
    )
    op.create_index("ix_os_datasets_tenant_id", "os_datasets", ["tenant_id"])
    op.create_index("ix_os_datasets_name", "os_datasets", ["name"])
    op.create_index("ix_os_datasets_domain", "os_datasets", ["domain"])

    # -- os_data_lineage ----------------------------------------------------
    op.create_table(
        "os_data_lineage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("dataset", sa.String(), nullable=False),
        sa.Column("upstream", sa.String(), nullable=False),
        sa.Column("transform", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "dataset", "upstream", name="uq_os_lineage_edge"),
    )
    op.create_index("ix_os_data_lineage_tenant_id", "os_data_lineage", ["tenant_id"])
    op.create_index("ix_os_data_lineage_dataset", "os_data_lineage", ["dataset"])
    op.create_index("ix_os_data_lineage_upstream", "os_data_lineage", ["upstream"])

    # -- os_data_contracts --------------------------------------------------
    op.create_table(
        "os_data_contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("dataset", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "dataset", "version", name="uq_os_contract_version"),
    )
    op.create_index("ix_os_data_contracts_tenant_id", "os_data_contracts", ["tenant_id"])
    op.create_index("ix_os_data_contracts_dataset", "os_data_contracts", ["dataset"])

    # -- os_data_quality_runs -----------------------------------------------
    op.create_table(
        "os_data_quality_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("dataset", sa.String(), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rows_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_data_quality_runs_tenant_id", "os_data_quality_runs", ["tenant_id"])
    op.create_index("ix_os_data_quality_runs_dataset", "os_data_quality_runs", ["dataset"])

    # -- os_workflow_definitions --------------------------------------------
    op.create_table(
        "os_workflow_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("graph", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "key", "version", name="uq_os_workflow_key_version"),
    )
    op.create_index("ix_os_workflow_definitions_tenant_id", "os_workflow_definitions", ["tenant_id"])
    op.create_index("ix_os_workflow_definitions_key", "os_workflow_definitions", ["key"])
    op.create_index("ix_os_workflow_definitions_status", "os_workflow_definitions", ["status"])

    # -- os_workflow_runs ---------------------------------------------------
    op.create_table(
        "os_workflow_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("definition_key", sa.String(), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("subject_ref", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("trace", sa.JSON(), nullable=False),
        sa.Column("path", sa.JSON(), nullable=False),
        sa.Column("current_node", sa.String(), nullable=True),
        sa.Column("outputs", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_workflow_runs_tenant_id", "os_workflow_runs", ["tenant_id"])
    op.create_index("ix_os_workflow_runs_definition_key", "os_workflow_runs", ["definition_key"])
    op.create_index("ix_os_workflow_runs_subject_ref", "os_workflow_runs", ["subject_ref"])
    op.create_index("ix_os_workflow_runs_status", "os_workflow_runs", ["status"])

    # -- os_marketplace_plugins ---------------------------------------------
    op.create_table(
        "os_marketplace_plugins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(), nullable=False, server_default="1.0.0"),
        sa.Column("publisher", sa.String(), nullable=True),
        sa.Column("installed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "key", name="uq_os_plugin_key"),
    )
    op.create_index("ix_os_marketplace_plugins_tenant_id", "os_marketplace_plugins", ["tenant_id"])
    op.create_index("ix_os_marketplace_plugins_key", "os_marketplace_plugins", ["key"])
    op.create_index("ix_os_marketplace_plugins_category", "os_marketplace_plugins", ["category"])

    # -- os_plugin_recommendations ------------------------------------------
    op.create_table(
        "os_plugin_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("plugin_key", sa.String(), nullable=False),
        sa.Column("subject_ref", sa.String(), nullable=True),
        sa.Column("assessment_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("priority", sa.String(), nullable=False, server_default="medium"),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_plugin_recommendations_tenant_id", "os_plugin_recommendations", ["tenant_id"])
    op.create_index("ix_os_plugin_recommendations_plugin_key", "os_plugin_recommendations", ["plugin_key"])
    op.create_index("ix_os_plugin_recommendations_subject_ref", "os_plugin_recommendations", ["subject_ref"])
    op.create_index("ix_os_plugin_recommendations_status", "os_plugin_recommendations", ["status"])

    # -- os_scenario_plans --------------------------------------------------
    op.create_table(
        "os_scenario_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False, server_default="portfolio"),
        sa.Column("scope_ref", sa.String(), nullable=True),
        sa.Column("scenarios", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_scenario_plans_tenant_id", "os_scenario_plans", ["tenant_id"])
    op.create_index("ix_os_scenario_plans_scope_ref", "os_scenario_plans", ["scope_ref"])

    # -- os_model_fairness_runs ---------------------------------------------
    op.create_table(
        "os_model_fairness_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("model_key", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="fairness"),
        sa.Column("protected_attribute", sa.String(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("groups", sa.JSON(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_os_model_fairness_runs_tenant_id", "os_model_fairness_runs", ["tenant_id"])
    op.create_index("ix_os_model_fairness_runs_model_key", "os_model_fairness_runs", ["model_key"])


def downgrade() -> None:
    for table in (
        "os_model_fairness_runs", "os_scenario_plans", "os_plugin_recommendations",
        "os_marketplace_plugins", "os_workflow_runs", "os_workflow_definitions",
        "os_data_quality_runs", "os_data_contracts", "os_data_lineage", "os_datasets",
        "os_llm_invocations", "os_llm_providers", "os_prompt_evaluations",
        "os_prompt_versions", "os_prompt_templates", "os_search_history",
        "os_saved_searches", "os_search_documents", "os_committee_votes",
        "os_agenda_items", "os_committee_meetings", "os_committees",
        "os_policy_evaluations", "os_policy_versions", "os_policies",
    ):
        op.drop_table(table)
