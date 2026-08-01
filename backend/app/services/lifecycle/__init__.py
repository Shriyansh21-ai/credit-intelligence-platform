"""Application Lifecycle Engine.

A validated state machine governing a credit application from Draft through to
Closed, with full status history, actor/reason capture, rollback, and auditing.
"""

from backend.app.services.lifecycle.state_machine import (
    ALLOWED_TRANSITIONS,
    STATUSES,
    TERMINAL_STATUSES,
    ApplicationStatus,
    can_transition,
    is_terminal,
    next_statuses,
    validate_transition,
)
from backend.app.services.lifecycle.service import (
    create_application,
    get_timeline,
    rollback,
    transition,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "STATUSES",
    "TERMINAL_STATUSES",
    "ApplicationStatus",
    "can_transition",
    "is_terminal",
    "next_statuses",
    "validate_transition",
    "create_application",
    "get_timeline",
    "rollback",
    "transition",
]
