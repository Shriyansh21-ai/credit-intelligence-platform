"""Report builders — turn platform data into a normalised report document.

A report document is
    {type, title, subtitle, generated_at, meta, sections: [section, ...]}
where each section is one of
    {"heading", "kind": "kv", "items": [{"label","value"}, ...]}
    {"heading", "kind": "table", "columns": [...], "rows": [[...], ...]}
    {"heading", "kind": "text", "text": "..."}

Builders are defensive: missing linked data yields an informative placeholder
section rather than an error, so a report can always be produced.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.application import Application
from backend.app.models.audit import AuditLog
from backend.app.models.covenant import Covenant
from backend.app.models.enterprise_assessment import EnterpriseAssessment
from backend.app.models.financial_analysis import FinancialAnalysis
from backend.app.models.monitoring import MonitoringAlert
from backend.app.services.approvals.service import get_approval_timeline
from backend.app.services.covenants.service import serialize_covenant
from backend.app.services.lifecycle.service import get_timeline


# --------------------------------------------------------------------------
# Context loading
# --------------------------------------------------------------------------

def _application(db: Session, application_id: int) -> Optional[Application]:
    return db.query(Application).filter(Application.id == application_id).first()


def _assessment_for(db: Session, app: Application) -> Optional[EnterpriseAssessment]:
    if app is None or app.assessment_id is None:
        return None
    return (
        db.query(EnterpriseAssessment)
        .filter(EnterpriseAssessment.id == app.assessment_id)
        .first()
    )


def _financials_for(db: Session, assessment_id: Optional[int]) -> Optional[FinancialAnalysis]:
    if assessment_id is None:
        return None
    return (
        db.query(FinancialAnalysis)
        .filter(
            FinancialAnalysis.assessment_id == assessment_id,
            FinancialAnalysis.is_current == True,  # noqa: E712
        )
        .first()
    )


def _doc(report_type: str, title: str, subtitle: str, sections: List[Dict[str, Any]], meta=None):
    return {
        "type": report_type,
        "title": title,
        "subtitle": subtitle,
        "generated_at": datetime.utcnow().isoformat(),
        "meta": meta or {},
        "sections": sections,
    }


def _missing(heading: str, message: str) -> Dict[str, Any]:
    return {"heading": heading, "kind": "text", "text": message}


def _overview_section(app: Application) -> Dict[str, Any]:
    return {
        "heading": "Application Overview",
        "kind": "kv",
        "items": [
            {"label": "Reference", "value": app.reference},
            {"label": "Company", "value": app.company_name},
            {"label": "Industry", "value": app.industry or "-"},
            {"label": "GSTIN", "value": app.gstin or "-"},
            {"label": "Requested Amount", "value": app.requested_amount},
            {"label": "Status", "value": app.status},
            {"label": "Risk Rating", "value": app.risk_rating or "-"},
        ],
    }


def _assessment_section(assessment: Optional[EnterpriseAssessment]) -> Dict[str, Any]:
    if assessment is None:
        return _missing("AI Assessment", "No linked enterprise assessment.")
    return {
        "heading": "AI Assessment",
        "kind": "kv",
        "items": [
            {"label": "Credit Score", "value": assessment.enterprise_credit_score},
            {"label": "Risk Rating", "value": assessment.risk_rating},
            {"label": "Probability of Default", "value": assessment.probability_of_default},
            {"label": "Loss Given Default", "value": assessment.loss_given_default},
            {"label": "Expected Loss", "value": assessment.expected_loss},
            {"label": "Recommended Loan", "value": assessment.recommended_loan_amount},
            {"label": "Recommended Rate", "value": assessment.recommended_interest_rate},
        ],
    }


def _financial_section(fin: Optional[FinancialAnalysis]) -> Dict[str, Any]:
    if fin is None:
        return _missing("Financial Analysis", "No financial analysis available.")
    ratios = fin.ratios or []
    rows = [
        [r.get("name") or r.get("key"), r.get("value"), r.get("status")]
        for r in ratios[:25]
    ]
    return {
        "heading": "Financial Analysis",
        "kind": "table",
        "columns": ["Ratio", "Value", "Status"],
        "rows": rows or [["No ratios", "-", "-"]],
    }


# --------------------------------------------------------------------------
# Report type builders
# --------------------------------------------------------------------------

def build_credit_memo(db: Session, application_id: int) -> Dict[str, Any]:
    app = _application(db, application_id)
    if app is None:
        return _doc("credit_memo", "Credit Memo", "Not found",
                    [_missing("Error", f"Application {application_id} not found.")])
    assessment = _assessment_for(db, app)
    fin = _financials_for(db, app.assessment_id)
    covenants = db.query(Covenant).filter(Covenant.application_id == app.id).all()

    sections = [
        _overview_section(app),
        _assessment_section(assessment),
        _financial_section(fin),
    ]
    if covenants:
        sections.append({
            "heading": "Covenants",
            "kind": "table",
            "columns": ["Covenant", "Operator", "Threshold", "Current", "Status"],
            "rows": [
                [c.name, c.operator, c.threshold,
                 serialize_covenant(db, c)["current_value"],
                 serialize_covenant(db, c)["current_status"]]
                for c in covenants
            ],
        })

    timeline = get_approval_timeline(db, app)
    if timeline:
        sections.append({
            "heading": "Approval History",
            "kind": "table",
            "columns": ["When", "Actor", "Action", "Stage"],
            "rows": [[t["created_at"], t["actor_email"], t["action"], t["stage_name"]] for t in timeline],
        })

    return _doc("credit_memo", f"Credit Memo — {app.company_name}",
                f"Reference {app.reference}", sections, meta={"application_id": app.id})


def build_executive_summary(db: Session, application_id: int) -> Dict[str, Any]:
    app = _application(db, application_id)
    if app is None:
        return _doc("executive_summary", "Executive Summary", "Not found",
                    [_missing("Error", f"Application {application_id} not found.")])
    assessment = _assessment_for(db, app)
    sections = [_overview_section(app), _assessment_section(assessment)]
    return _doc("executive_summary", f"Executive Summary — {app.company_name}",
                f"Reference {app.reference}", sections, meta={"application_id": app.id})


def build_financial_report(db: Session, application_id: int) -> Dict[str, Any]:
    app = _application(db, application_id)
    if app is None:
        return _doc("financial_report", "Financial Report", "Not found",
                    [_missing("Error", f"Application {application_id} not found.")])
    fin = _financials_for(db, app.assessment_id)
    sections = [_overview_section(app), _financial_section(fin)]
    if fin and fin.health_scores:
        sections.append({
            "heading": "Health Scores",
            "kind": "table",
            "columns": ["Dimension", "Score"],
            "rows": [[h.get("name") or h.get("key"), h.get("score") or h.get("value")]
                     for h in fin.health_scores],
        })
    return _doc("financial_report", f"Financial Report — {app.company_name}",
                f"Reference {app.reference}", sections, meta={"application_id": app.id})


def build_risk_report(db: Session, application_id: int) -> Dict[str, Any]:
    app = _application(db, application_id)
    if app is None:
        return _doc("risk_report", "Risk Report", "Not found",
                    [_missing("Error", f"Application {application_id} not found.")])
    assessment = _assessment_for(db, app)
    fin = _financials_for(db, app.assessment_id)
    sections = [_overview_section(app), _assessment_section(assessment)]
    if fin and fin.risk_flags:
        sections.append({
            "heading": "Risk Flags",
            "kind": "table",
            "columns": ["Flag", "Severity"],
            "rows": [[f.get("message") or f.get("title"), f.get("severity")] for f in fin.risk_flags],
        })
    return _doc("risk_report", f"Risk Report — {app.company_name}",
                f"Reference {app.reference}", sections, meta={"application_id": app.id})


def build_committee_pack(db: Session, application_id: int) -> Dict[str, Any]:
    memo = build_credit_memo(db, application_id)
    risk = build_risk_report(db, application_id)
    sections = memo["sections"] + [s for s in risk["sections"] if s["heading"] != "Application Overview"]
    app = _application(db, application_id)
    name = app.company_name if app else str(application_id)
    return _doc("committee_pack", f"Credit Committee Pack — {name}",
                "For committee review", sections, meta={"application_id": application_id})


def build_portfolio_report(db: Session) -> Dict[str, Any]:
    apps = db.query(Application).all()
    by_status: Dict[str, int] = {}
    total_exposure = 0.0
    for a in apps:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        total_exposure += a.requested_amount or 0
    sections = [
        {
            "heading": "Portfolio Summary",
            "kind": "kv",
            "items": [
                {"label": "Applications", "value": len(apps)},
                {"label": "Total Requested Exposure", "value": total_exposure},
            ],
        },
        {
            "heading": "By Status",
            "kind": "table",
            "columns": ["Status", "Count"],
            "rows": [[k, v] for k, v in sorted(by_status.items())] or [["-", 0]],
        },
    ]
    return _doc("portfolio_report", "Portfolio Report", "All applications", sections)


def build_compliance_report(db: Session, application_id: Optional[int] = None) -> Dict[str, Any]:
    mon_q = db.query(MonitoringAlert)
    if application_id is not None:
        mon_q = mon_q.filter(MonitoringAlert.application_id == application_id)
    alerts = mon_q.order_by(MonitoringAlert.created_at.desc()).limit(100).all()
    sections = [{
        "heading": "Monitoring Alerts",
        "kind": "table",
        "columns": ["When", "Category", "Severity", "Status", "Message"],
        "rows": [[a.created_at.isoformat() if a.created_at else None, a.category,
                  a.severity, a.status, a.message] for a in alerts] or [["-", "-", "-", "-", "None"]],
    }]
    return _doc("compliance_report", "Compliance Report",
                f"Application {application_id}" if application_id else "Platform-wide", sections)


def build_audit_report(db: Session, *, entity_type: Optional[str] = None,
                       entity_id: Optional[int] = None, limit: int = 200) -> Dict[str, Any]:
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.filter(AuditLog.entity_id == entity_id)
    rows = q.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    sections = [{
        "heading": "Audit Trail",
        "kind": "table",
        "columns": ["When", "User", "Action", "Entity", "Reason"],
        "rows": [[r.timestamp.isoformat() if r.timestamp else None, r.user_email,
                  r.action, f"{r.entity_type or ''}:{r.entity_id or ''}", r.reason]
                 for r in rows] or [["-", "-", "-", "-", "None"]],
    }]
    return _doc("audit_report", "Audit Report",
                f"{entity_type}:{entity_id}" if entity_type else "Platform-wide", sections)
