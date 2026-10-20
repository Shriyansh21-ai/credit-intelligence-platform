"""Add tenant-scoped document review and financial provenance.

Revision ID: 9f4c2a7b1d6e
Revises: f4b6c8d0e2a4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f4c2a7b1d6e"
down_revision: Union[str, Sequence[str], None] = "f4b6c8d0e2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("fiscal_year", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("currency", sa.String(length=3), nullable=True))
        batch_op.add_column(
            sa.Column("unit", sa.String(), nullable=False, server_default="units")
        )
        batch_op.add_column(sa.Column("reviewed_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("approved_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("rejected_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("rejected_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("rejection_reason", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_documents_tenant_id_tenants", "tenants", ["tenant_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_documents_company_id_companies", "companies", ["company_id"], ["id"]
        )
        for column in ("reviewed_by", "approved_by", "rejected_by"):
            batch_op.create_foreign_key(
                f"fk_documents_{column}_users", "users", [column], ["id"]
            )
        batch_op.create_index("ix_documents_tenant_id", ["tenant_id"])
        batch_op.create_index("ix_documents_company_id", ["company_id"])
        batch_op.create_index("ix_documents_fiscal_year", ["fiscal_year"])

    op.execute(
        sa.text(
            "UPDATE documents SET tenant_id = ("
            "SELECT tenant_id FROM tenant_memberships "
            "WHERE tenant_memberships.user_id = documents.user_id "
            "ORDER BY is_default DESC, id LIMIT 1"
            ") WHERE tenant_id IS NULL"
        )
    )

    with op.batch_alter_table("document_extractions") as batch_op:
        batch_op.add_column(sa.Column("provider", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("provider_version", sa.String(), nullable=True))

    with op.batch_alter_table("company_financials") as batch_op:
        batch_op.add_column(sa.Column("currency", sa.String(length=3), nullable=True))
        batch_op.add_column(
            sa.Column("unit", sa.String(), nullable=False, server_default="units")
        )
        batch_op.add_column(sa.Column("source_document_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("source_document_extraction_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(sa.Column("reviewed_by", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_company_financials_source_document_documents",
            "documents",
            ["source_document_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_company_financials_source_extraction_document_extractions",
            "document_extractions",
            ["source_document_extraction_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_company_financials_reviewed_by_users", "users", ["reviewed_by"], ["id"]
        )
        batch_op.create_index(
            "ix_company_financials_source_document_id", ["source_document_id"]
        )

    op.create_table(
        "document_review_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("document_reference_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("from_status", sa.String(), nullable=True),
        sa.Column("to_status", sa.String(), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
    )
    op.create_index(
        "ix_document_review_events_document_id",
        "document_review_events",
        ["document_id"],
    )
    op.create_index(
        "ix_document_review_events_document_reference_id",
        "document_review_events",
        ["document_reference_id"],
    )
    op.create_index(
        "ix_document_review_events_tenant_id",
        "document_review_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_document_review_events_actor_id",
        "document_review_events",
        ["actor_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_review_events_document_reference_id",
        table_name="document_review_events",
    )
    op.drop_index("ix_document_review_events_actor_id", table_name="document_review_events")
    op.drop_index("ix_document_review_events_tenant_id", table_name="document_review_events")
    op.drop_index("ix_document_review_events_document_id", table_name="document_review_events")
    op.drop_table("document_review_events")

    with op.batch_alter_table("company_financials") as batch_op:
        batch_op.drop_index("ix_company_financials_source_document_id")
        batch_op.drop_constraint(
            "fk_company_financials_reviewed_by_users", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_company_financials_source_extraction_document_extractions",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_company_financials_source_document_documents", type_="foreignkey"
        )
        batch_op.drop_column("reviewed_by")
        batch_op.drop_column("source_document_extraction_id")
        batch_op.drop_column("source_document_id")
        batch_op.drop_column("unit")
        batch_op.drop_column("currency")

    with op.batch_alter_table("document_extractions") as batch_op:
        batch_op.drop_column("provider_version")
        batch_op.drop_column("provider")

    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_index("ix_documents_fiscal_year")
        batch_op.drop_index("ix_documents_company_id")
        batch_op.drop_index("ix_documents_tenant_id")
        batch_op.drop_constraint("fk_documents_rejected_by_users", type_="foreignkey")
        batch_op.drop_constraint("fk_documents_approved_by_users", type_="foreignkey")
        batch_op.drop_constraint("fk_documents_reviewed_by_users", type_="foreignkey")
        batch_op.drop_constraint("fk_documents_company_id_companies", type_="foreignkey")
        batch_op.drop_constraint("fk_documents_tenant_id_tenants", type_="foreignkey")
        for column in (
            "rejection_reason", "rejected_at", "rejected_by", "approved_at",
            "approved_by", "reviewed_at", "reviewed_by", "unit", "currency",
            "fiscal_year", "company_id", "tenant_id",
        ):
            batch_op.drop_column(column)
