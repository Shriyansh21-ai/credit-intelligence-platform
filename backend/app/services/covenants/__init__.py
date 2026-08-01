"""Covenant Monitoring engine.

Tracks loan covenants (DSCR, debt ratio, current ratio, interest coverage, net
worth, EBITDA, ...), evaluates measurements against thresholds, records trend
and raises breach alerts automatically.
"""

from backend.app.services.covenants.catalog import (
    COVENANT_METRICS,
    metric_definition,
)
from backend.app.services.covenants.service import (
    create_covenant,
    evaluate_covenant,
    record_measurement,
    covenant_trend,
    list_covenants,
    list_alerts,
    serialize_covenant,
)

__all__ = [
    "COVENANT_METRICS",
    "metric_definition",
    "create_covenant",
    "evaluate_covenant",
    "record_measurement",
    "covenant_trend",
    "list_covenants",
    "list_alerts",
    "serialize_covenant",
]
