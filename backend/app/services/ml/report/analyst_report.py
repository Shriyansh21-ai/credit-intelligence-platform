"""Credit-memo composition.

``build_report_from_engine_input`` runs the full Phase-1..4 stack over an
assessment input and assembles a structured credit memo that mirrors the
sections of a real bank credit committee paper. Every section is derived from a
concrete signal — nothing is invented.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from backend.app.services.enterprise_assessment import evaluate_enterprise_assessment
from backend.app.services.financial_analysis import analysis_service
from backend.app.services.ml.alerts import alert_engine
from backend.app.services.ml.explainability import service as explain_service
from backend.app.services.ml.features import feature_pipeline

REPORT_VERSION = "1.0"

_GOOD_STATUSES = {"excellent", "good", "Strong"}
_WEAK_STATUSES = {"weak", "critical", "Weak"}

# Which alert categories roll up into which memo risk section.
_RISK_SECTION_MAP = {
    "financial": "financial_risks",
    "leverage": "financial_risks",
    "cash_flow": "financial_risks",
    "liquidity": "financial_risks",
    "working_capital": "business_risks",
    "external": "industry_risks",
    "conduct": "management_risks",
}


def _monitoring_frequency(grade: str, highest_severity: Optional[str]) -> str:
    if highest_severity == "critical":
        return "Monthly"
    if highest_severity == "high" or grade in ("BB", "B", "CCC", "CC"):
        return "Quarterly"
    if grade in ("BBB", "A"):
        return "Semi-annual"
    return "Annual"


def _business_overview(ei: Mapping[str, Any]) -> dict:
    return {
        "company_name": ei.get("company_name", "The company"),
        "industry": ei.get("industry"),
        "business_type": ei.get("business_type"),
        "years_in_business": ei.get("years_in_business"),
        "employee_count": ei.get("employee_count"),
        "country": ei.get("country"),
        "expansion_stage": ei.get("business_expansion_stage"),
    }


def _financial_summary(ei: Mapping[str, Any], analysis: Mapping[str, Any]) -> dict:
    overall = analysis.get("overall_health", {}) or {}
    return {
        "annual_revenue": ei.get("annual_revenue"),
        "ebitda": ei.get("ebitda"),
        "net_profit": ei.get("net_profit"),
        "operating_cash_flow": ei.get("operating_cash_flow"),
        "total_debt": (ei.get("long_term_debt") or 0) + (ei.get("short_term_debt") or 0),
        "net_worth": ei.get("net_worth"),
        "overall_financial_health": {
            "score": overall.get("score"),
            "status": overall.get("status"),
        },
        "key_ratios": _key_ratios(analysis),
        "health_scores": {
            key: hs.get("status")
            for key, hs in (analysis.get("health_scores", {}) or {}).items()
        },
    }


def _key_ratios(analysis: Mapping[str, Any]) -> List[dict]:
    wanted = {"current_ratio", "dscr", "interest_coverage", "debt_to_equity",
              "net_margin", "operating_cash_flow_ratio"}
    return [
        {"label": r.get("label"), "value": r.get("value"), "status": r.get("status")}
        for r in (analysis.get("ratios", []) or [])
        if r.get("key") in wanted
    ]


def _strengths(analysis: Mapping[str, Any], explanation: Mapping[str, Any]) -> List[str]:
    strengths: List[str] = []
    for key, hs in (analysis.get("health_scores", {}) or {}).items():
        if hs.get("status") in _GOOD_STATUSES:
            strengths.append(f"{key.replace('_', ' ').title()} is {hs.get('status')} "
                             f"(score {hs.get('score')}).")
    for c in explanation.get("top_negative_contributors", [])[:3]:
        strengths.append(c.get("narrative", ""))
    return [s for s in strengths if s][:6]


def _weaknesses(analysis: Mapping[str, Any], explanation: Mapping[str, Any]) -> List[str]:
    weaknesses: List[str] = []
    for key, hs in (analysis.get("health_scores", {}) or {}).items():
        if hs.get("status") in _WEAK_STATUSES:
            weaknesses.append(f"{key.replace('_', ' ').title()} is {hs.get('status')} "
                              f"(score {hs.get('score')}).")
    for c in explanation.get("top_positive_contributors", [])[:3]:
        weaknesses.append(c.get("narrative", ""))
    return [w for w in weaknesses if w][:6]


def _risk_sections(alerts: List[dict], ei: Mapping[str, Any]) -> Dict[str, List[dict]]:
    sections: Dict[str, List[dict]] = {
        "business_risks": [], "industry_risks": [],
        "financial_risks": [], "management_risks": [],
    }
    for alert in alerts:
        section = _RISK_SECTION_MAP.get(alert.get("category"), "business_risks")
        sections[section].append({
            "title": alert.get("title"),
            "severity": alert.get("severity"),
            "impact": alert.get("business_impact"),
            "action": alert.get("suggested_action"),
        })
    # Qualitative overlays that aren't alert-driven.
    if str(ei.get("industry_risk", "")).lower() == "high" and not sections["industry_risks"]:
        sections["industry_risks"].append({
            "title": "Elevated industry risk band",
            "severity": "medium",
            "impact": "Sector conditions raise correlated default risk.",
            "action": "Apply a sector overlay and monitor industry indicators.",
        })
    return sections


def _executive_summary(company: str, summary: Mapping, recommendation: Mapping,
                       strengths: List[str], weaknesses: List[str]) -> str:
    lead = (
        f"{company} carries an enterprise credit score of {summary['enterprise_credit_score']} "
        f"(grade {summary['risk_grade']}), implying a "
        f"{summary['probability_of_default'] * 100:.2f}% probability of default. "
        f"Recommended decision: {recommendation['decision'].lower()}."
    )
    if strengths:
        lead += f" Key strength: {strengths[0]}"
    if weaknesses:
        lead += f" Key concern: {weaknesses[0]}"
    return lead


def _analyst_notes(vector: Mapping[str, Any], alerts_summary: Mapping) -> List[str]:
    notes: List[str] = []
    low_conf = vector.get("low_confidence_count", 0)
    if low_conf:
        notes.append(
            f"{low_conf} feature(s) had low or no confidence (missing inputs); "
            "obtain complete financials to firm up the assessment."
        )
    if alerts_summary.get("alert_count"):
        notes.append(
            f"{alerts_summary['alert_count']} early-warning alert(s) raised "
            f"(highest severity: {alerts_summary.get('highest_severity')})."
        )
    notes.append("All figures and conclusions are model-derived and fully explainable.")
    return notes


def build_report_from_engine_input(
    engine_input: Mapping[str, Any],
    model_type: Optional[str] = None,
) -> dict:
    """Compose a full credit memo from an assessment engine input."""
    assessment = evaluate_enterprise_assessment(dict(engine_input))
    analysis = analysis_service.analyze_engine_input(dict(engine_input))
    vector = feature_pipeline.build_from_engine_input(dict(engine_input))
    explanation = explain_service.explain_vector(vector, model_type=model_type)
    alerts_summary = alert_engine.scan(vector, engine_input=engine_input)

    summary = assessment["summary"]
    recommendation = assessment["recommendation"]
    company = engine_input.get("company_name", "The company")

    strengths = _strengths(analysis, explanation)
    weaknesses = _weaknesses(analysis, explanation)
    risk_sections = _risk_sections(alerts_summary["alerts"], engine_input)

    return {
        "report_version": REPORT_VERSION,
        "report_type": "enterprise_credit_memo",
        "executive_summary": _executive_summary(
            company, summary, recommendation, strengths, weaknesses),
        "business_overview": _business_overview(engine_input),
        "financial_summary": _financial_summary(engine_input, analysis),
        "credit_strengths": strengths,
        "weaknesses": weaknesses,
        "business_risks": risk_sections["business_risks"],
        "industry_risks": risk_sections["industry_risks"],
        "financial_risks": risk_sections["financial_risks"],
        "management_risks": risk_sections["management_risks"],
        "risk_drivers": {
            "top_positive_contributors": explanation.get("top_positive_contributors", []),
            "top_negative_contributors": explanation.get("top_negative_contributors", []),
        },
        "recommendation": {
            "decision": recommendation["decision"],
            "recommended_loan_amount": summary["recommended_loan_amount"],
            "recommended_interest_rate": recommendation["interest_rate_recommendation"],
            "recommended_tenure": recommendation["loan_tenure_recommendation"],
            "collateral": recommendation["collateral_recommendation"],
            "monitoring_frequency": _monitoring_frequency(
                summary["risk_grade"], alerts_summary.get("highest_severity")),
            "loan_recommendation": recommendation["loan_recommendation"],
        },
        "alerts_summary": {
            "alert_count": alerts_summary["alert_count"],
            "highest_severity": alerts_summary["highest_severity"],
            "by_severity": alerts_summary["by_severity"],
        },
        "analyst_notes": _analyst_notes(vector, alerts_summary),
        "final_recommendation": (
            f"{recommendation['decision']} — {recommendation['loan_recommendation']}"
        ),
    }
