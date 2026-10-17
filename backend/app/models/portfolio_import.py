"""Tenant-scoped tracking for customer portfolio file imports."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String

from backend.app.db.database import Base


class PortfolioImport(Base):
    __tablename__ = "portfolio_imports"
    __table_args__ = (
        Index("ix_portfolio_imports_tenant_created", "tenant_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_format = Column(String(8), nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="awaiting_mapping", index=True)
    worksheet = Column(String(255), nullable=True)
    column_mapping = Column(JSON, nullable=False, default=dict)
    staged_data = Column(JSON, nullable=True)
    findings = Column(JSON, nullable=False, default=list)
    total_rows = Column(Integer, nullable=False, default=0)
    valid_rows = Column(Integer, nullable=False, default=0)
    invalid_rows = Column(Integer, nullable=False, default=0)
    warning_count = Column(Integer, nullable=False, default=0)
    imported_rows = Column(Integer, nullable=False, default=0)
    skipped_rows = Column(Integer, nullable=False, default=0)
    failed_rows = Column(Integer, nullable=False, default=0)
    error_summary = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)