"""Audit & Compliance engine (Phase 5, Milestone 4).

Central, best-effort audit recording plus a searchable query layer. Recording
never raises into the caller: an audit failure must not break a business action.
"""

from backend.app.services.audit.recorder import record, record_safe
from backend.app.services.audit.query import search_audit, audit_stats

__all__ = ["record", "record_safe", "search_audit", "audit_stats"]
