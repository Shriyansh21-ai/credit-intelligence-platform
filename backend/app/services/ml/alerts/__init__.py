"""Early Warning System (Phase 4, Milestone 7).

Proactively scans a borrower's features for deterioration signals — revenue
decline, cash-flow stress, rising leverage, working-capital erosion, weak
coverage, compliance/late-filing issues, fraud indicators and industry decline —
and raises structured, prioritised alerts an analyst can act on.

Rules are deterministic and transparent (a threshold + evidence), so every alert
is explainable and auditable. Alerts are persisted for history.
"""

from .alert_engine import scan  # noqa: F401
from .rules import RULES  # noqa: F401
