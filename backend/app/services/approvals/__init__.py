"""Multi-Stage Approval Workflow.

Configurable, ordered approval stages driving the application lifecycle. Every
approver action (approve / reject / request changes / escalate / hold / comment)
is recorded and, where appropriate, advances the lifecycle state machine.
"""

from backend.app.services.approvals.workflow import (
    ACTIONS,
    DEFAULT_WORKFLOW,
    ensure_default_workflow,
    get_default_workflow,
)
from backend.app.services.approvals.service import (
    get_approval_timeline,
    submit_decision,
)

__all__ = [
    "ACTIONS",
    "DEFAULT_WORKFLOW",
    "ensure_default_workflow",
    "get_default_workflow",
    "get_approval_timeline",
    "submit_decision",
]
