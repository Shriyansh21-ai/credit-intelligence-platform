"""Dashboard aggregation service.

Server-side aggregates that back the enterprise dashboards, so the frontend reads
real numbers from one endpoint per dashboard instead of stitching many calls or
using placeholder data.
"""

from backend.app.services.dashboards.service import (
    admin_dashboard,
    analyst_dashboard,
    compliance_dashboard,
    manager_dashboard,
    monitoring_dashboard,
    operations_dashboard,
    portfolio_dashboard,
)

__all__ = [
    "admin_dashboard",
    "analyst_dashboard",
    "compliance_dashboard",
    "manager_dashboard",
    "monitoring_dashboard",
    "operations_dashboard",
    "portfolio_dashboard",
]
