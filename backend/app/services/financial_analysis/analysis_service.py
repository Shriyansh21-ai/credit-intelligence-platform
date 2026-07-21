"""Analysis orchestrator.

Runs every engine over a :class:`FinancialStatement` and assembles a single
serializable payload. This payload is both the API response shape and the
persistence input (``repository.save_analysis`` reads the same keys). Adapter
entrypoints build the statement from an assessment ``engine_input`` or from
document extraction fields.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from .health_engine import compute_health, overall_health
from .insight_engine import generate_insights
from .ratio_engine import compute_ratios, ratios_by_category
from .recommendation_engine import generate_recommendations
from .risk_flag_engine import detect_risk_flags
from .statement import (
    FinancialStatement,
    from_document_fields,
    from_engine_input,
    from_mapping,
)
from .trend_engine import compute_trends

ENGINE_VERSION = "1.0"

# Company-profile keys the stability dimension can use, if present.
_CONTEXT_KEYS = ("years_in_business", "employee_count", "business_expansion_stage")


def context_from_engine_input(data: Mapping[str, Any]) -> dict:
    return {k: data[k] for k in _CONTEXT_KEYS if k in data and data[k] is not None}


def run_analysis(
    statement: FinancialStatement,
    context: Optional[Mapping[str, Any]] = None,
    previous: Optional[FinancialStatement] = None,
) -> dict:
    """Compute the full financial-intelligence payload for one statement."""
    ratios = compute_ratios(statement)
    ratios_map = {r.key: r for r in ratios}
    health = compute_health(statement, context=context, previous=previous)
    overall = overall_health(health)
    insights = generate_insights(ratios, health)
    flags = detect_risk_flags(statement, ratios_map)
    recommendations = generate_recommendations(ratios_map, health)

    return {
        "period": statement.period.as_dict(),
        "statement": statement.as_dict(),
        "overall_health": overall.as_dict(),
        "health_scores": {key: hs.as_dict() for key, hs in health.items()},
        "ratios": [r.as_dict() for r in ratios],
        "ratios_by_category": {
            cat: [r.as_dict() for r in rs]
            for cat, rs in ratios_by_category(ratios).items()
        },
        "insights": [i.as_dict() for i in insights],
        "risk_flags": [f.as_dict() for f in flags],
        "recommendations": [r.as_dict() for r in recommendations],
        "risk_flag_count": len(flags),
        "highest_severity": flags[0].severity if flags else None,
        "engine_version": ENGINE_VERSION,
    }


def analyze_engine_input(
    data: Mapping[str, Any], previous: Optional[FinancialStatement] = None
) -> dict:
    """Analyse an enterprise assessment ``engine_input`` dict."""
    return run_analysis(
        from_engine_input(data),
        context=context_from_engine_input(data),
        previous=previous,
    )


def analyze_document_fields(
    fields: Any, context: Optional[Mapping[str, Any]] = None
) -> dict:
    """Analyse reviewed document extraction fields."""
    return run_analysis(from_document_fields(fields), context=context)


def analyze_mapping(
    financials: Mapping[str, Any],
    context: Optional[Mapping[str, Any]] = None,
    previous: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Analyse an arbitrary financials mapping (``POST /analysis/compute``)."""
    prev_statement = from_mapping(previous) if previous else None
    return run_analysis(from_mapping(financials), context=context, previous=prev_statement)


def trends_from_records(records) -> dict:
    """Compute trends from persisted analyses by rebuilding statements from
    their stored snapshots (oldest fiscal year first)."""
    statements = [from_mapping(r.statement_snapshot or {}) for r in records]
    return compute_trends(statements)


def serialize_record(record) -> dict:
    """Reconstruct the API payload from a persisted ``FinancialAnalysis`` row."""
    return {
        "id": record.id,
        "assessment_id": record.assessment_id,
        "version": record.version,
        "created_at": str(record.created_at) if record.created_at else None,
        "period": {
            "label": record.period_label,
            "period_type": record.period_type,
            "fiscal_year": record.fiscal_year,
        },
        "statement": record.statement_snapshot or {},
        "overall_health": {
            "key": "overall",
            "label": "Overall Financial Health",
            "score": record.overall_health_score,
            "status": record.overall_health_status,
        },
        "health_scores": record.health_scores or {},
        "ratios": record.ratios or [],
        "insights": record.insights or [],
        "risk_flags": record.risk_flags or [],
        "recommendations": record.recommendations or [],
        "risk_flag_count": record.risk_flag_count,
        "highest_severity": record.highest_severity,
        "engine_version": record.engine_version,
    }
