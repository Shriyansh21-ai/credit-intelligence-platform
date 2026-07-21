"""The application lifecycle state machine.

Defines every valid status, the legal transitions between them, and helpers to
validate a proposed move. Transition rules are the single source of truth — the
service layer never mutates status without consulting :func:`validate_transition`.
"""

from __future__ import annotations

from typing import Dict, List, Set


class ApplicationStatus:
    """Canonical status constants (string values persisted verbatim)."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    DOCUMENTS_PENDING = "documents_pending"
    UNDER_AI_ANALYSIS = "under_ai_analysis"
    ANALYST_REVIEW = "analyst_review"
    SENIOR_ANALYST_REVIEW = "senior_analyst_review"
    CREDIT_COMMITTEE = "credit_committee"
    APPROVED = "approved"
    CONDITIONALLY_APPROVED = "conditionally_approved"
    REJECTED = "rejected"
    DISBURSED = "disbursed"
    MONITORING = "monitoring"
    CLOSED = "closed"
    CANCELLED = "cancelled"


STATUSES: List[str] = [
    ApplicationStatus.DRAFT,
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.DOCUMENTS_PENDING,
    ApplicationStatus.UNDER_AI_ANALYSIS,
    ApplicationStatus.ANALYST_REVIEW,
    ApplicationStatus.SENIOR_ANALYST_REVIEW,
    ApplicationStatus.CREDIT_COMMITTEE,
    ApplicationStatus.APPROVED,
    ApplicationStatus.CONDITIONALLY_APPROVED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.DISBURSED,
    ApplicationStatus.MONITORING,
    ApplicationStatus.CLOSED,
    ApplicationStatus.CANCELLED,
]

# Human-friendly labels for UI / reports.
STATUS_LABELS: Dict[str, str] = {
    ApplicationStatus.DRAFT: "Draft",
    ApplicationStatus.SUBMITTED: "Submitted",
    ApplicationStatus.DOCUMENTS_PENDING: "Documents Pending",
    ApplicationStatus.UNDER_AI_ANALYSIS: "Under AI Analysis",
    ApplicationStatus.ANALYST_REVIEW: "Analyst Review",
    ApplicationStatus.SENIOR_ANALYST_REVIEW: "Senior Analyst Review",
    ApplicationStatus.CREDIT_COMMITTEE: "Credit Committee",
    ApplicationStatus.APPROVED: "Approved",
    ApplicationStatus.CONDITIONALLY_APPROVED: "Conditionally Approved",
    ApplicationStatus.REJECTED: "Rejected",
    ApplicationStatus.DISBURSED: "Disbursed",
    ApplicationStatus.MONITORING: "Monitoring",
    ApplicationStatus.CLOSED: "Closed",
    ApplicationStatus.CANCELLED: "Cancelled",
}

# Terminal statuses cannot transition further (except via explicit rollback).
TERMINAL_STATUSES: Set[str] = {
    ApplicationStatus.CLOSED,
    ApplicationStatus.CANCELLED,
}

# Forward transition graph. "cancel" is permitted from any non-terminal state and
# is handled separately in :func:`can_transition`.
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    ApplicationStatus.DRAFT: {
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.CANCELLED,
    },
    ApplicationStatus.SUBMITTED: {
        ApplicationStatus.DOCUMENTS_PENDING,
        ApplicationStatus.UNDER_AI_ANALYSIS,
        ApplicationStatus.CANCELLED,
    },
    ApplicationStatus.DOCUMENTS_PENDING: {
        ApplicationStatus.UNDER_AI_ANALYSIS,
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.CANCELLED,
    },
    ApplicationStatus.UNDER_AI_ANALYSIS: {
        ApplicationStatus.ANALYST_REVIEW,
        ApplicationStatus.DOCUMENTS_PENDING,
        ApplicationStatus.CANCELLED,
    },
    ApplicationStatus.ANALYST_REVIEW: {
        ApplicationStatus.SENIOR_ANALYST_REVIEW,
        ApplicationStatus.DOCUMENTS_PENDING,
        ApplicationStatus.REJECTED,
        ApplicationStatus.CANCELLED,
    },
    ApplicationStatus.SENIOR_ANALYST_REVIEW: {
        ApplicationStatus.CREDIT_COMMITTEE,
        ApplicationStatus.ANALYST_REVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.CANCELLED,
    },
    ApplicationStatus.CREDIT_COMMITTEE: {
        ApplicationStatus.APPROVED,
        ApplicationStatus.CONDITIONALLY_APPROVED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.SENIOR_ANALYST_REVIEW,
        ApplicationStatus.CANCELLED,
    },
    ApplicationStatus.APPROVED: {
        ApplicationStatus.DISBURSED,
        ApplicationStatus.CANCELLED,
    },
    ApplicationStatus.CONDITIONALLY_APPROVED: {
        ApplicationStatus.APPROVED,
        ApplicationStatus.DISBURSED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.CANCELLED,
    },
    ApplicationStatus.REJECTED: {
        # A rejected application may be reopened for another review round.
        ApplicationStatus.ANALYST_REVIEW,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.DISBURSED: {
        ApplicationStatus.MONITORING,
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.MONITORING: {
        ApplicationStatus.CLOSED,
    },
    ApplicationStatus.CLOSED: set(),
    ApplicationStatus.CANCELLED: set(),
}


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def next_statuses(status: str) -> List[str]:
    """The statuses reachable from ``status`` in a single forward transition."""
    return sorted(ALLOWED_TRANSITIONS.get(status, set()))


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status not in ALLOWED_TRANSITIONS:
        return False
    if to_status not in STATUSES:
        return False
    return to_status in ALLOWED_TRANSITIONS[from_status]


class InvalidTransition(ValueError):
    """Raised when a status change violates the state machine."""


def validate_transition(from_status: str, to_status: str) -> None:
    if to_status not in STATUSES:
        raise InvalidTransition(f"Unknown status: {to_status!r}")
    if from_status == to_status:
        raise InvalidTransition(f"Already in status {to_status!r}")
    if not can_transition(from_status, to_status):
        allowed = ", ".join(next_statuses(from_status)) or "(none)"
        raise InvalidTransition(
            f"Cannot move from {from_status!r} to {to_status!r}. Allowed: {allowed}"
        )
