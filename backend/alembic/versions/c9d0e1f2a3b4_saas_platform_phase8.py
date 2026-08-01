"""Multi-Tenant Enterprise SaaS Platform tables

Fully additive: creates the tenancy, branding, billing, feature-flag
background-job, cloud-storage, real-time, observability and security tables.
Nothing from Phases 1-7 is altered or dropped.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-23 15:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- organizations ------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=True),
        sa.Column("org_type", sa.String(), nullable=False, server_default="bank"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("country", sa.String(), nullable=True, server_default="IN"),
        sa.Column("timezone", sa.String(), nullable=True, server_default="Asia/Kolkata"),
        sa.Column("currency", sa.String(), nullable=True, server_default="INR"),
        sa.Column("locale", sa.String(), nullable=True, server_default="en-IN"),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_index("ix_organizations_status", "organizations", ["status"])

    # -- tenants ------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("locale", sa.String(), nullable=True),
        sa.Column("encryption_key_ref", sa.String(), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("organization_id", "slug", name="uq_tenant_org_slug"),
    )
    op.create_index("ix_tenants_organization_id", "tenants", ["organization_id"])
    op.create_index("ix_tenants_slug", "tenants", ["slug"])
    op.create_index("ix_tenants_status", "tenants", ["status"])

    # -- business_units -----------------------------------------------------
    op.create_table(
        "business_units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("business_units.id"), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_business_units_tenant_id", "business_units", ["tenant_id"])

    # -- departments --------------------------------------------------------
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("business_unit_id", sa.Integer(), sa.ForeignKey("business_units.id"), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_departments_tenant_id", "departments", ["tenant_id"])
    op.create_index("ix_departments_business_unit_id", "departments", ["business_unit_id"])

    # -- teams --------------------------------------------------------------
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_teams_tenant_id", "teams", ["tenant_id"])
    op.create_index("ix_teams_department_id", "teams", ["department_id"])

    # -- workspaces ---------------------------------------------------------
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_workspaces_tenant_id", "workspaces", ["tenant_id"])

    # -- projects -----------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])

    # -- tenant_memberships -------------------------------------------------
    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("org_role", sa.String(), nullable=False, server_default="member"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("business_unit_id", sa.Integer(), sa.ForeignKey("business_units.id"), nullable=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),
    )
    op.create_index("ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"])
    op.create_index("ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"])

    # -- tenant_invitations -------------------------------------------------
    op.create_table(
        "tenant_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("org_role", sa.String(), nullable=False, server_default="member"),
        sa.Column("rbac_role", sa.String(), nullable=True),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("invited_by", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tenant_invitations_tenant_id", "tenant_invitations", ["tenant_id"])
    op.create_index("ix_tenant_invitations_email", "tenant_invitations", ["email"])
    op.create_index("ix_tenant_invitations_token", "tenant_invitations", ["token"], unique=True)
    op.create_index("ix_tenant_invitations_status", "tenant_invitations", ["status"])

    # -- tenant_branding ----------------------------------------------------
    op.create_table(
        "tenant_branding",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("logo_dark_url", sa.String(), nullable=True),
        sa.Column("favicon_url", sa.String(), nullable=True),
        sa.Column("theme", sa.JSON(), nullable=False),
        sa.Column("email_branding", sa.JSON(), nullable=False),
        sa.Column("login_page", sa.JSON(), nullable=False),
        sa.Column("dashboard_config", sa.JSON(), nullable=False),
        sa.Column("feature_visibility", sa.JSON(), nullable=False),
        sa.Column("navigation", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tenant_branding_tenant_id", "tenant_branding", ["tenant_id"], unique=True)

    # -- custom_domains -----------------------------------------------------
    op.create_table(
        "custom_domains",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("verification_token", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ssl_status", sa.String(), nullable=False, server_default="none"),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_custom_domains_tenant_id", "custom_domains", ["tenant_id"])
    op.create_index("ix_custom_domains_domain", "custom_domains", ["domain"], unique=True)

    # -- billing_plans ------------------------------------------------------
    op.create_table(
        "billing_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("tier", sa.String(), nullable=False, server_default="free"),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("base_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("billing_interval", sa.String(), nullable=False, server_default="monthly"),
        sa.Column("limits", sa.JSON(), nullable=False),
        sa.Column("unit_prices", sa.JSON(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_billing_plans_code", "billing_plans", ["code"])

    # -- subscriptions ------------------------------------------------------
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("billing_plans.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("seats", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(), nullable=False, server_default="internal"),
        sa.Column("provider_ref", sa.String(), nullable=True),
        sa.Column("trial_end", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_subscriptions_organization_id", "subscriptions", ["organization_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    # -- subscription_events ------------------------------------------------
    op.create_table(
        "subscription_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("from_plan", sa.String(), nullable=True),
        sa.Column("to_plan", sa.String(), nullable=True),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_subscription_events_subscription_id", "subscription_events", ["subscription_id"])
    op.create_index("ix_subscription_events_organization_id", "subscription_events", ["organization_id"])
    op.create_index("ix_subscription_events_created_at", "subscription_events", ["created_at"])

    # -- usage_records ------------------------------------------------------
    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("meter", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("organization_id", "tenant_id", "meter", "period", "created_at"):
        op.create_index(f"ix_usage_records_{col}", "usage_records", [col])

    # -- invoices -----------------------------------------------------------
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id"), nullable=True),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("subtotal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tax", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("provider", sa.String(), nullable=False, server_default="internal"),
        sa.Column("provider_ref", sa.String(), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_invoices_organization_id", "invoices", ["organization_id"])
    op.create_index("ix_invoices_number", "invoices", ["number"], unique=True)
    op.create_index("ix_invoices_period", "invoices", ["period"])

    # -- invoice_line_items -------------------------------------------------
    op.create_table(
        "invoice_line_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="usage"),
        sa.Column("meter", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index("ix_invoice_line_items_invoice_id", "invoice_line_items", ["invoice_id"])

    # -- feature_flags ------------------------------------------------------
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rollout_percentage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(), nullable=False, server_default="release"),
        sa.Column("target_roles", sa.JSON(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"], unique=True)

    # -- feature_flag_overrides ---------------------------------------------
    op.create_table(
        "feature_flag_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("flag_key", sa.String(), sa.ForeignKey("feature_flags.key"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("flag_key", "tenant_id", name="uq_flag_override_tenant"),
    )
    op.create_index("ix_feature_flag_overrides_flag_key", "feature_flag_overrides", ["flag_key"])
    op.create_index("ix_feature_flag_overrides_tenant_id", "feature_flag_overrides", ["tenant_id"])

    # -- job_schedules (before background_jobs FK) --------------------------
    op.create_table(
        "job_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("queue", sa.String(), nullable=False, server_default="default"),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_job_schedules_tenant_id", "job_schedules", ["tenant_id"])
    op.create_index("ix_job_schedules_next_run_at", "job_schedules", ["next_run_at"])

    # -- background_jobs -----------------------------------------------------
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("queue", sa.String(), nullable=False, server_default="default"),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(), nullable=True),
        sa.Column("available_at", sa.DateTime(), nullable=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("job_schedules.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    for col in ("tenant_id", "job_type", "queue", "status", "available_at",
                "idempotency_key", "created_at"):
        op.create_index(f"ix_background_jobs_{col}", "background_jobs", [col])

    # -- storage_objects ----------------------------------------------------
    op.create_table(
        "storage_objects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("bucket", sa.String(), nullable=False, server_default="default"),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("backend", sa.String(), nullable=False, server_default="local"),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lifecycle_policy", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    for col in ("tenant_id", "bucket", "key", "expires_at"):
        op.create_index(f"ix_storage_objects_{col}", "storage_objects", [col])

    # -- storage_object_versions --------------------------------------------
    op.create_table(
        "storage_object_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("object_id", sa.Integer(), sa.ForeignKey("storage_objects.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(), nullable=True),
        sa.Column("physical_uri", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_storage_object_versions_object_id", "storage_object_versions", ["object_id"])

    # -- activity_events ----------------------------------------------------
    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("channel", sa.String(), nullable=False, server_default="global"),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("tenant_id", "channel", "event_type", "created_at"):
        op.create_index(f"ix_activity_events_{col}", "activity_events", [col])

    # -- presence_records ---------------------------------------------------
    op.create_table(
        "presence_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="online"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False),
    )
    op.create_index("ix_presence_records_tenant_id", "presence_records", ["tenant_id"])
    op.create_index("ix_presence_records_user_id", "presence_records", ["user_id"])
    op.create_index("ix_presence_records_last_seen_at", "presence_records", ["last_seen_at"])

    # -- trace_spans --------------------------------------------------------
    op.create_table(
        "trace_spans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("span_id", sa.String(), nullable=False),
        sa.Column("parent_span_id", sa.String(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="internal"),
        sa.Column("service", sa.String(), nullable=False, server_default="api"),
        sa.Column("status", sa.String(), nullable=False, server_default="ok"),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
    )
    for col in ("correlation_id", "trace_id", "tenant_id", "started_at"):
        op.create_index(f"ix_trace_spans_{col}", "trace_spans", [col])

    # -- security_devices (before security_sessions FK) --------------------
    op.create_table(
        "security_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("trusted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_security_devices_tenant_id", "security_devices", ["tenant_id"])
    op.create_index("ix_security_devices_user_id", "security_devices", ["user_id"])
    op.create_index("ix_security_devices_fingerprint", "security_devices", ["fingerprint"])

    # -- security_sessions --------------------------------------------------
    op.create_table(
        "security_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_token", sa.String(), nullable=False),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("security_devices.id"), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_security_sessions_tenant_id", "security_sessions", ["tenant_id"])
    op.create_index("ix_security_sessions_user_id", "security_sessions", ["user_id"])
    op.create_index("ix_security_sessions_session_token", "security_sessions", ["session_token"], unique=True)

    # -- ip_allow_entries ---------------------------------------------------
    op.create_table(
        "ip_allow_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("cidr", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ip_allow_entries_tenant_id", "ip_allow_entries", ["tenant_id"])

    # -- secret_refs --------------------------------------------------------
    op.create_table(
        "secret_refs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("manager", sa.String(), nullable=False, server_default="local"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("value_encrypted", sa.Text(), nullable=True),
        sa.Column("rotated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_secret_refs_tenant_id", "secret_refs", ["tenant_id"])
    op.create_index("ix_secret_refs_name", "secret_refs", ["name"])

    # -- identity_provider_configs ------------------------------------------
    op.create_table(
        "identity_provider_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("protocol", sa.String(), nullable=False, server_default="oidc"),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("client_secret_ref", sa.String(), nullable=True),
        sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_identity_provider_configs_tenant_id", "identity_provider_configs", ["tenant_id"])


def downgrade() -> None:
    for table in (
        "identity_provider_configs", "secret_refs", "ip_allow_entries",
        "security_sessions", "security_devices", "trace_spans",
        "presence_records", "activity_events", "storage_object_versions",
        "storage_objects", "background_jobs", "job_schedules",
        "feature_flag_overrides", "feature_flags", "invoice_line_items",
        "invoices", "usage_records", "subscription_events", "subscriptions",
        "billing_plans", "custom_domains", "tenant_branding",
        "tenant_invitations", "tenant_memberships", "projects", "workspaces",
        "teams", "departments", "business_units", "tenants", "organizations",
    ):
        op.drop_table(table)
