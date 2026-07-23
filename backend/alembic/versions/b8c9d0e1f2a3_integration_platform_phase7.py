"""Banking Ecosystem Integration Platform tables (Phase 7)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-23 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- connector_configs --------------------------------------------------
    op.create_table(
        "connector_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connector_key", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("provider_mode", sa.String(), nullable=False, server_default="mock"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=True),
        sa.Column("rate_limit_per_sec", sa.Float(), nullable=True),
        sa.Column("timeout_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_connector_configs_connector_key", "connector_configs", ["connector_key"], unique=True)
    op.create_index("ix_connector_configs_category", "connector_configs", ["category"])

    # -- connector_call_logs ------------------------------------------------
    op.create_table(
        "connector_call_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connector_key", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("from_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("circuit_state", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("request_summary", sa.JSON(), nullable=True),
        sa.Column("entity_ref", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("connector_key", "category", "provider", "operation", "success", "entity_ref", "created_at"):
        op.create_index(f"ix_connector_call_logs_{col}", "connector_call_logs", [col])

    # -- integration_snapshots ----------------------------------------------
    op.create_table(
        "integration_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connector_key", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False, server_default="mock"),
        sa.Column("dataset", sa.String(), nullable=False, server_default="default"),
        sa.Column("entity_ref", sa.String(), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("refresh_due_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("connector_key", "dataset", "entity_ref", "application_id", "is_current", "content_hash", "created_at"):
        op.create_index(f"ix_integration_snapshots_{col}", "integration_snapshots", [col])

    # -- aa_consents --------------------------------------------------------
    op.create_table(
        "aa_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("handle", sa.String(), nullable=False),
        sa.Column("entity_ref", sa.String(), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("purpose", sa.String(), nullable=True),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("accounts", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_aa_consents_handle", "aa_consents", ["handle"], unique=True)
    for col in ("entity_ref", "application_id", "status", "expires_at"):
        op.create_index(f"ix_aa_consents_{col}", "aa_consents", [col])

    # -- bank_statements ----------------------------------------------------
    op.create_table(
        "bank_statements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_ref", sa.String(), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("consent_id", sa.Integer(), sa.ForeignKey("aa_consents.id"), nullable=True),
        sa.Column("account_ref", sa.String(), nullable=False),
        sa.Column("account_type", sa.String(), nullable=True),
        sa.Column("bank_name", sa.String(), nullable=True),
        sa.Column("ifsc", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("from_date", sa.DateTime(), nullable=True),
        sa.Column("to_date", sa.DateTime(), nullable=True),
        sa.Column("opening_balance", sa.Float(), nullable=True),
        sa.Column("closing_balance", sa.Float(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="account_aggregator"),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("txn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("entity_ref", "application_id", "consent_id", "account_ref", "created_at"):
        op.create_index(f"ix_bank_statements_{col}", "bank_statements", [col])

    # -- bank_transactions --------------------------------------------------
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("statement_id", sa.Integer(), sa.ForeignKey("bank_statements.id"), nullable=False),
        sa.Column("txn_date", sa.DateTime(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("balance", sa.Float(), nullable=True),
        sa.Column("narration", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("counterparty", sa.String(), nullable=True),
        sa.Column("mode", sa.String(), nullable=True),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_bank_transactions_statement_id", "bank_transactions", ["statement_id"])
    op.create_index("ix_bank_transactions_txn_date", "bank_transactions", ["txn_date"])
    op.create_index("ix_bank_transactions_category", "bank_transactions", ["category"])

    # -- statement_analytics ------------------------------------------------
    op.create_table(
        "statement_analytics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_ref", sa.String(), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("statement_id", sa.Integer(), sa.ForeignKey("bank_statements.id"), nullable=True),
        sa.Column("scope", sa.String(), nullable=False, server_default="statement"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("bank_health_score", sa.Float(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("entity_ref", "application_id", "statement_id", "created_at"):
        op.create_index(f"ix_statement_analytics_{col}", "statement_analytics", [col])

    # -- collateral_items ---------------------------------------------------
    op.create_table(
        "collateral_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_ref", sa.String(), nullable=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("collateral_type", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("market_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("haircut_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("realizable_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("loan_amount", sa.Float(), nullable=True),
        sa.Column("ltv", sa.Float(), nullable=True),
        sa.Column("coverage_ratio", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("charge_type", sa.String(), nullable=True),
        sa.Column("expiry_date", sa.DateTime(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    for col in ("entity_ref", "application_id", "collateral_type", "status", "expiry_date"):
        op.create_index(f"ix_collateral_items_{col}", "collateral_items", [col])

    # -- collateral_valuations ----------------------------------------------
    op.create_table(
        "collateral_valuations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collateral_id", sa.Integer(), sa.ForeignKey("collateral_items.id"), nullable=False),
        sa.Column("market_value", sa.Float(), nullable=False),
        sa.Column("haircut_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("realizable_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("method", sa.String(), nullable=True),
        sa.Column("valuer", sa.String(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("valued_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_collateral_valuations_collateral_id", "collateral_valuations", ["collateral_id"])
    op.create_index("ix_collateral_valuations_is_current", "collateral_valuations", ["is_current"])
    op.create_index("ix_collateral_valuations_valued_at", "collateral_valuations", ["valued_at"])

    # -- collateral_inspections ---------------------------------------------
    op.create_table(
        "collateral_inspections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collateral_id", sa.Integer(), sa.ForeignKey("collateral_items.id"), nullable=False),
        sa.Column("inspected_at", sa.DateTime(), nullable=True),
        sa.Column("inspector", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("condition", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_collateral_inspections_collateral_id", "collateral_inspections", ["collateral_id"])
    op.create_index("ix_collateral_inspections_inspected_at", "collateral_inspections", ["inspected_at"])

    # -- api_keys -----------------------------------------------------------
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rate_limit_per_min", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("ix_api_keys_active", "api_keys", ["active"])

    # -- api_usage_logs -----------------------------------------------------
    op.create_table(
        "api_usage_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_key_id", sa.Integer(), sa.ForeignKey("api_keys.id"), nullable=True),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_api_usage_logs_api_key_id", "api_usage_logs", ["api_key_id"])
    op.create_index("ix_api_usage_logs_endpoint", "api_usage_logs", ["endpoint"])
    op.create_index("ix_api_usage_logs_created_at", "api_usage_logs", ["created_at"])

    # -- webhook_subscriptions ----------------------------------------------
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("secret", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_webhook_subscriptions_active", "webhook_subscriptions", ["active"])

    # -- webhook_deliveries -------------------------------------------------
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("webhook_subscriptions.id"), nullable=False),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_webhook_deliveries_subscription_id", "webhook_deliveries", ["subscription_id"])
    op.create_index("ix_webhook_deliveries_event", "webhook_deliveries", ["event"])
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("ix_webhook_deliveries_created_at", "webhook_deliveries", ["created_at"])

    # -- portfolio_sync_jobs ------------------------------------------------
    op.create_table(
        "portfolio_sync_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sync_type", sa.String(), nullable=False, server_default="incremental"),
        sa.Column("connectors", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("cursor", sa.String(), nullable=True),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_portfolio_sync_jobs_status", "portfolio_sync_jobs", ["status"])
    op.create_index("ix_portfolio_sync_jobs_created_at", "portfolio_sync_jobs", ["created_at"])

    # -- sync_dead_letters --------------------------------------------------
    op.create_table(
        "sync_dead_letters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("portfolio_sync_jobs.id"), nullable=True),
        sa.Column("connector_key", sa.String(), nullable=True),
        sa.Column("entity_ref", sa.String(), nullable=True),
        sa.Column("operation", sa.String(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("job_id", "connector_key", "entity_ref", "resolved", "created_at"):
        op.create_index(f"ix_sync_dead_letters_{col}", "sync_dead_letters", [col])


def downgrade() -> None:
    for table in (
        "sync_dead_letters", "portfolio_sync_jobs", "webhook_deliveries",
        "webhook_subscriptions", "api_usage_logs", "api_keys",
        "collateral_inspections", "collateral_valuations", "collateral_items",
        "statement_analytics", "bank_transactions", "bank_statements",
        "aa_consents", "integration_snapshots", "connector_call_logs",
        "connector_configs",
    ):
        op.drop_table(table)
