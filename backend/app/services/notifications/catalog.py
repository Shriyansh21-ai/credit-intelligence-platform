"""Notification event catalog (pure data).

Each event declares a default severity and a human label. Preferences and the
dispatcher are keyed on these event types.
"""

from __future__ import annotations

from typing import Dict

# event_type -> {label, severity}
EVENT_TYPES: Dict[str, Dict[str, str]] = {
    "application_submitted": {"label": "Application Submitted", "severity": "info"},
    "approval_required": {"label": "Approval Required", "severity": "warning"},
    "document_missing": {"label": "Document Missing", "severity": "warning"},
    "risk_alert": {"label": "Risk Alert", "severity": "critical"},
    "committee_assigned": {"label": "Committee Assigned", "severity": "info"},
    "task_assigned": {"label": "Task Assigned", "severity": "info"},
    "task_due": {"label": "Task Due", "severity": "warning"},
    "task_completed": {"label": "Task Completed", "severity": "info"},
    "covenant_breach": {"label": "Covenant Breach", "severity": "critical"},
    "monitoring_alert": {"label": "Monitoring Alert", "severity": "warning"},
    "mention": {"label": "You Were Mentioned", "severity": "info"},
    "status_changed": {"label": "Application Status Changed", "severity": "info"},
}


def event_meta(event_type: str) -> Dict[str, str]:
    return EVENT_TYPES.get(event_type, {"label": event_type, "severity": "info"})
