"""M10 — Corporate Benchmarking Platform.

Compare a company against an industry peer set automatically: financial, growth,
profitability, liquidity, leverage, ESG, risk and credit rankings, with
percentile positioning and a synthesized competitive position. The peer set is
drawn from the platform's live assessments in the same industry (falling back to
industry norms when peers are sparse). Deterministic and grounded.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import FinBenchmark
from . import data_access as da
from . import esg as esg_svc
from .common import checksum, clamp, grounding_block, iso, mean, pd_from_score, percentile, safe_div, to_float, utcnow

# Metrics: key -> (label, higher_is_better).
METRICS: Dict[str, Dict[str, Any]] = {
    "revenue": {"label": "Revenue scale", "higher": True},
    "net_margin": {"label": "Profitability", "higher": True},
    "revenue_growth": {"label": "Growth", "higher": True},
    "current_ratio": {"label": "Liquidity", "higher": True},
    "debt_to_equity": {"label": "Leverage", "higher": False},
    "credit_score": {"label": "Credit quality", "higher": True},
    "pd": {"label": "Default risk", "higher": False},
    "esg_score": {"label": "ESG", "higher": True},
}

# Industry norm anchors used when the live peer set is thin.
INDUSTRY_NORMS: Dict[str, Dict[str, float]] = {
    "general": {"revenue": 120, "net_margin": 0.09, "revenue_growth": 0.08, "current_ratio": 1.4,
                "debt_to_equity": 1.6, "credit_score": 650, "pd": 0.05, "esg_score": 60},
    "manufacturing": {"revenue": 200, "net_margin": 0.08, "revenue_growth": 0.07, "current_ratio": 1.3,
                      "debt_to_equity": 1.8, "credit_score": 640, "pd": 0.055, "esg_score": 55},
    "technology": {"revenue": 90, "net_margin": 0.15, "revenue_growth": 0.20, "current_ratio": 2.0,
                   "debt_to_equity": 0.6, "credit_score": 700, "pd": 0.03, "esg_score": 68},
    "retail": {"revenue": 150, "net_margin": 0.05, "revenue_growth": 0.10, "current_ratio": 1.2,
               "debt_to_equity": 1.4, "credit_score": 630, "pd": 0.06, "esg_score": 58},
}


def _company_metrics(prof: Dict[str, Any]) -> Dict[str, float]:
    ei = prof.get("engine_input", {}) or {}
    return {
        "revenue": to_float(ei.get("revenue"), 100.0),
        "net_margin": to_float(ei.get("net_margin"), 0.08),
        "revenue_growth": to_float(ei.get("revenue_growth"), 0.06),
        "current_ratio": to_float(ei.get("current_ratio"), 1.3),
        "debt_to_equity": to_float(ei.get("debt_to_equity"), 1.6),
        "credit_score": to_float(prof.get("credit_score"), 650.0),
        "pd": da.pd_of(prof),
        "esg_score": 60.0,
    }


def _peer_set(db: Session, industry: str, subject_ref: str) -> List[Dict[str, float]]:
    peers = []
    for prof in da.portfolio_profiles(db):
        if not prof or prof.get("company_ref") == subject_ref:
            continue
        if (prof.get("industry") or "general").lower() == (industry or "general").lower():
            peers.append(_company_metrics(prof))
    return peers


def benchmark(db: Session, *, subject_ref: str, assessment_id: Optional[int] = None,
              industry: Optional[str] = None, tenant_id: Optional[int] = None,
              created_by: Optional[str] = None) -> Dict[str, Any]:
    prof = da.company_or_none(db, assessment_id=assessment_id, company_ref=subject_ref)
    if not prof:
        raise ValueError("company not found")
    industry = industry or prof.get("industry") or "general"
    subject = _company_metrics(prof)
    # ESG from the ESG engine (grounded), fall back to norm.
    try:
        subject["esg_score"] = esg_svc.assess(db, subject_ref=subject_ref, assessment_id=assessment_id,
                                              industry=industry, tenant_id=tenant_id)["esg_score"]
    except Exception:
        pass
    peers = _peer_set(db, industry, subject_ref)
    norm = INDUSTRY_NORMS.get(industry.lower(), INDUSTRY_NORMS["general"])
    # Synthesize a peer distribution: real peers + norm anchor.
    rankings: Dict[str, Any] = {}
    percentiles: Dict[str, float] = {}
    for key, spec in METRICS.items():
        peer_vals = [p[key] for p in peers if key in p] + [norm.get(key, subject[key])]
        val = subject[key]
        below = sum(1 for pv in peer_vals if pv < val)
        pctl = safe_div(below, len(peer_vals), 0.5) or 0.5
        if not spec["higher"]:
            pctl = 1 - pctl  # invert so higher percentile is always "better"
        percentiles[key] = round(pctl * 100, 1)
        rankings[key] = {"label": spec["label"], "value": round(val, 4),
                         "peer_median": round(percentile(peer_vals, 50), 4),
                         "percentile": round(pctl * 100, 1),
                         "quartile": 4 - min(int(pctl * 4), 3)}
    overall = mean(list(percentiles.values()))
    position = ("leader" if overall >= 75 else "above_average" if overall >= 55
                else "average" if overall >= 45 else "laggard")
    results = {
        "industry": industry, "peer_count": len(peers),
        "rankings": rankings, "percentiles": percentiles,
        "overall_percentile": round(overall, 1),
        "competitive_position": position,
        "strengths": [METRICS[k]["label"] for k, v in percentiles.items() if v >= 70],
        "weaknesses": [METRICS[k]["label"] for k, v in percentiles.items() if v < 40],
    }
    g = grounding_block("Corporate Benchmark", results)
    row = FinBenchmark(
        tenant_id=tenant_id, subject_ref=subject_ref, assessment_id=assessment_id, industry=industry,
        peer_set=[{"metrics": p} for p in peers], rankings=rankings, percentiles=percentiles,
        competitive_position=position, narrative=(
            f"{subject_ref} ranks in the {round(overall)}th percentile of {industry} peers "
            f"({position.replace('_', ' ')})."),
        created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"benchmark_id": row.id, "subject_ref": subject_ref, **results}


def list_benchmarks(db: Session, *, subject_ref: Optional[str] = None, limit: int = 50,
                    tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinBenchmark)
    if tenant_id is not None:
        q = q.filter(FinBenchmark.tenant_id == tenant_id)
    if subject_ref:
        q = q.filter(FinBenchmark.subject_ref == subject_ref)
    return [{"benchmark_id": b.id, "subject_ref": b.subject_ref, "industry": b.industry,
             "competitive_position": b.competitive_position, "created_at": iso(b.created_at)}
            for b in q.order_by(FinBenchmark.id.desc()).limit(limit).all()]


def get_benchmark(db: Session, benchmark_id: int) -> Optional[Dict[str, Any]]:
    b = db.query(FinBenchmark).filter(FinBenchmark.id == benchmark_id).first()
    if not b:
        return None
    return {"benchmark_id": b.id, "subject_ref": b.subject_ref, "industry": b.industry,
            "rankings": b.rankings, "percentiles": b.percentiles,
            "competitive_position": b.competitive_position, "narrative": b.narrative,
            "created_at": iso(b.created_at)}
