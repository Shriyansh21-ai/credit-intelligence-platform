"""Audit log persistence.

A single append-only table captures every material action on the platform
logins, API calls, predictions, uploads, edits, approvals, exports, and more.
Rows are never updated or deleted by application code.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from backend.app.db.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Actor. Nullable because some events (e.g. failed login) have no known user.
    user_id = Column(Integer, nullable=True, index=True)
    user_email = Column(String, nullable=True, index=True)

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Request context.
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    http_method = Column(String, nullable=True)
    path = Column(String, nullable=True)

    # What happened. ``action`` is a dotted verb, e.g. "application.transition".
    action = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(Integer, nullable=True, index=True)

    # Change payloads for edit-style events.
    previous_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)

    reason = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="success")
    meta = Column(JSON, nullable=True)
