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
    count_alerts,
    create_covenant,
    evaluate_covenant,
    record_measurement,
    covenant_trend,
    get_alert,
    get_covenant,
    list_covenants,
    list_alerts,
    serialize_covenant,
    update_alert_status,
)

__all__ = [
    "COVENANT_METRICS",
    "metric_definition",
    "count_alerts",
    "create_covenant",
    "evaluate_covenant",
    "record_measurement",
    "covenant_trend",
    "get_covenant",
    "get_alert",
    "list_covenants",
    "list_alerts",
    "serialize_covenant",
    "update_alert_status",
]
