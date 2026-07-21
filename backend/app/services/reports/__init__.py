"""Enterprise Report Generator (Phase 5, Milestone 7).

Composes banking-style reports (credit memo, executive summary, financial, risk,
committee pack, portfolio, compliance, audit) from the platform's existing
engines, and renders them to JSON, HTML, PDF (reportlab), CSV (Excel-openable)
and RTF (Word-openable).
"""

from backend.app.services.reports.service import (
    REPORT_TYPES,
    SUPPORTED_FORMATS,
    generate_report,
)

__all__ = ["REPORT_TYPES", "SUPPORTED_FORMATS", "generate_report"]
