"""M3 — Basel III / IFRS 9 Platform.

Enterprise regulatory calculations, fully explainable and deterministic
    IFRS 9 — PD / LGD / EAD, 12-month & lifetime ECL, staging, provisioning
    Basel III — IRB & standardized RWA, capital requirements, CAR, leverage
                and a consolidated regulatory dashboard.

Every calculation returns an ``explanation`` block naming the formula and the
inputs used, so results are auditable end-to-end. Results persist to
``fin_regulatory_calcs``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import FinRegulatoryCalc
from . import data_access as da
from .common import (
    checksum, clamp, expected_loss, grounding_block, iso, marginal_pd_curve,
    norm_cdf, norm_ppf, pct, pd_from_score, rating_from_pd, safe_div, to_float, utcnow,
)

# Standardized-approach corporate risk weights by external rating (Basel).
STD_RISK_WEIGHT = {
    "AAA": 0.20, "AA": 0.20, "A": 0.50, "BBB": 1.00, "BB": 1.00,
    "B": 1.50, "CCC": 1.50, "CC": 1.50, "C": 1.50, "D": 1.50, "NR": 1.00,
}
CONFIDENCE = 0.999  # Basel IRB confidence level
LGD_DOWNTURN_FLOOR = 0.10


def _save(db: Session, *, calc_type: str, framework: str, subject_ref: Optional[str],
          assessment_id: Optional[int], inputs: dict, results: dict, explanation: dict,
          tenant_id: Optional[int], created_by: Optional[str]) -> Dict[str, Any]:
    row = FinRegulatoryCalc(
        tenant_id=tenant_id, calc_type=calc_type, framework=framework,
        subject_ref=subject_ref, assessment_id=assessment_id, inputs=inputs,
        results=results, explanation=explanation, checksum=checksum(results),
        created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"calc_id": row.id, "calc_type": calc_type, "framework": framework,
            "checksum": row.checksum, "results": results, "explanation": explanation}


def _resolve_params(db: Session, *, subject_ref: Optional[str], assessment_id: Optional[int],
                    pd: Optional[float], lgd: Optional[float], ead: Optional[float]) -> Dict[str, Any]:
    prof = None
    if subject_ref or assessment_id:
        prof = da.company_or_none(db, assessment_id=assessment_id, company_ref=subject_ref)
    if prof:
        pd = pd if pd is not None else da.pd_of(prof)
        lgd = lgd if lgd is not None else da.lgd_of(prof)
        ead = ead if ead is not None else da.exposure_of(prof)
        rating = prof.get("rating") or rating_from_pd(pd)
    else:
        pd = pd if pd is not None else 0.05
        lgd = lgd if lgd is not None else 0.45
        ead = ead if ead is not None else 1_000_000.0
        rating = rating_from_pd(pd)
    return {"pd": clamp(to_float(pd), 1e-6, 1.0), "lgd": clamp(to_float(lgd), 0.0, 1.0),
            "ead": max(to_float(ead), 0.0), "rating": rating, "profile": bool(prof)}


# ---------------------------------------------------------------------------
# IFRS 9 — ECL, staging, provisioning
# ---------------------------------------------------------------------------

def _stage(pd: float, dpd: int, original_pd: Optional[float]) -> Dict[str, Any]:
    """IFRS 9 3-stage classification (SICR heuristic)."""
    sicr = False
    reasons = []
    if dpd >= 90:
        return {"stage": 3, "reasons": ["90+ days past due (credit-impaired)"], "sicr": True}
    if dpd >= 30:
        sicr = True
        reasons.append("30+ days past due (rebuttable SICR presumption)")
    if original_pd is not None and pd >= 2.0 * max(original_pd, 1e-6):
        sicr = True
        reasons.append("PD more than doubled vs origination")
    if pd >= 0.20:
        sicr = True
        reasons.append("absolute PD above 20%")
    stage = 2 if sicr else 1
    if not reasons:
        reasons.append("performing, no significant increase in credit risk")
    return {"stage": stage, "reasons": reasons, "sicr": sicr}


def ecl(db: Session, *, subject_ref: Optional[str] = None, assessment_id: Optional[int] = None,
        pd: Optional[float] = None, lgd: Optional[float] = None, ead: Optional[float] = None,
        dpd: int = 0, original_pd: Optional[float] = None, lifetime_years: int = 5,
        eir: float = 0.10, tenant_id: Optional[int] = None,
        created_by: Optional[str] = None) -> Dict[str, Any]:
    """12-month and lifetime Expected Credit Loss with staging & provisioning."""
    p = _resolve_params(db, subject_ref=subject_ref, assessment_id=assessment_id,
                        pd=pd, lgd=lgd, ead=ead)
    stage_info = _stage(p["pd"], dpd, original_pd)
    ecl_12m = expected_loss(p["pd"], p["lgd"], p["ead"])
    # Lifetime ECL: discounted marginal PD curve × LGD × EAD.
    curve = marginal_pd_curve(p["pd"], lifetime_years)
    ecl_lifetime = sum(mpd * p["lgd"] * p["ead"] / ((1 + eir) ** (t + 1))
                       for t, mpd in enumerate(curve))
    stage = stage_info["stage"]
    provision = ecl_12m if stage == 1 else ecl_lifetime
    results = {
        "pd": round(p["pd"], 6), "lgd": round(p["lgd"], 4), "ead": round(p["ead"], 2),
        "rating": p["rating"],
        "ecl_12m": round(ecl_12m, 2),
        "ecl_lifetime": round(ecl_lifetime, 2),
        "stage": stage,
        "stage_reasons": stage_info["reasons"],
        "provision": round(provision, 2),
        "coverage_ratio_pct": pct(safe_div(provision, p["ead"], 0.0)),
        "lifetime_pd_curve": [round(x, 6) for x in curve],
    }
    explanation = {
        "framework": "IFRS 9",
        "formulas": {
            "ecl_12m": "PD_12m × LGD × EAD",
            "ecl_lifetime": "Σ_t [marginal_PD_t × LGD × EAD / (1+EIR)^t]",
            "provision": "12m ECL if Stage 1 else lifetime ECL",
        },
        "inputs_used": {"eir": eir, "lifetime_years": lifetime_years, "dpd": dpd},
        "grounded_on_profile": p["profile"],
    }
    g = grounding_block("IFRS 9 ECL", results)
    return _save(db, calc_type="ecl", framework="ifrs9", subject_ref=subject_ref,
                 assessment_id=assessment_id,
                 inputs={"dpd": dpd, "eir": eir, "lifetime_years": lifetime_years},
                 results={**results, "grounding": g}, explanation=explanation,
                 tenant_id=tenant_id, created_by=created_by)


# ---------------------------------------------------------------------------
# Basel III — RWA, capital, CAR, leverage
# ---------------------------------------------------------------------------

def _irb_capital_ratio(pd: float, lgd: float, maturity: float = 2.5) -> float:
    """Basel IRB corporate capital requirement K (fraction of EAD)."""
    pd = clamp(pd, 1e-6, 1 - 1e-6)
    r = 0.12 * (1 - math.exp(-50 * pd)) / (1 - math.exp(-50)) + \
        0.24 * (1 - (1 - math.exp(-50 * pd)) / (1 - math.exp(-50)))
    b = (0.11852 - 0.05478 * math.log(pd)) ** 2
    maturity_adj = (1 + (maturity - 2.5) * b) / (1 - 1.5 * b)
    cond_pd = norm_cdf((norm_ppf(pd) + math.sqrt(r) * norm_ppf(CONFIDENCE)) / math.sqrt(1 - r))
    k = (lgd * cond_pd - pd * lgd) * maturity_adj
    return max(k, 0.0)


def rwa(db: Session, *, approach: str = "irb", subject_ref: Optional[str] = None,
        assessment_id: Optional[int] = None, pd: Optional[float] = None,
        lgd: Optional[float] = None, ead: Optional[float] = None, maturity: float = 2.5,
        tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Risk-Weighted Assets via IRB (default) or standardized approach."""
    p = _resolve_params(db, subject_ref=subject_ref, assessment_id=assessment_id,
                        pd=pd, lgd=lgd, ead=ead)
    if approach == "standardized":
        rw = STD_RISK_WEIGHT.get(p["rating"], 1.0)
        rwa_val = rw * p["ead"]
        k = rw * 0.08
        formula = "RWA = risk_weight(rating) × EAD"
    else:
        k = _irb_capital_ratio(p["pd"], p["lgd"], maturity)
        rwa_val = k * 12.5 * p["ead"]
        rw = safe_div(rwa_val, p["ead"], 0.0)
        formula = "RWA = K × 12.5 × EAD (Basel IRB Vasicek capital)"
    results = {
        "approach": approach, "pd": round(p["pd"], 6), "lgd": round(p["lgd"], 4),
        "ead": round(p["ead"], 2), "rating": p["rating"],
        "capital_requirement_k": round(k, 6),
        "risk_weight_pct": pct(rw),
        "rwa": round(rwa_val, 2),
        "capital_at_8pct": round(rwa_val * 0.08, 2),
    }
    explanation = {"framework": "Basel III", "formula": formula,
                   "inputs_used": {"maturity": maturity, "confidence": CONFIDENCE},
                   "grounded_on_profile": p["profile"]}
    g = grounding_block("Basel RWA", results)
    return _save(db, calc_type="rwa", framework="basel3", subject_ref=subject_ref,
                 assessment_id=assessment_id, inputs={"approach": approach, "maturity": maturity},
                 results={**results, "grounding": g}, explanation=explanation,
                 tenant_id=tenant_id, created_by=created_by)


def capital_adequacy(db: Session, *, cet1: float, additional_tier1: float, tier2: float,
                     total_rwa: float, tenant_id: Optional[int] = None,
                     created_by: Optional[str] = None) -> Dict[str, Any]:
    """Capital Adequacy Ratios vs Basel III minimums (incl. buffers)."""
    rwa_d = max(to_float(total_rwa), 1.0)
    tier1 = cet1 + additional_tier1
    total_cap = tier1 + tier2
    cet1_ratio = safe_div(cet1, rwa_d, 0.0)
    tier1_ratio = safe_div(tier1, rwa_d, 0.0)
    car = safe_div(total_cap, rwa_d, 0.0)
    # Minimums: CET1 4.5% + 2.5% CCB = 7%, Tier1 8.5%, Total 10.5%.
    results = {
        "cet1_ratio_pct": pct(cet1_ratio), "tier1_ratio_pct": pct(tier1_ratio),
        "total_capital_ratio_pct": pct(car),
        "min_cet1_pct": 7.0, "min_tier1_pct": 8.5, "min_total_pct": 10.5,
        "cet1_compliant": cet1_ratio >= 0.07,
        "tier1_compliant": tier1_ratio >= 0.085,
        "total_compliant": car >= 0.105,
        "surplus_capital": round(total_cap - 0.105 * rwa_d, 2),
    }
    explanation = {"framework": "Basel III",
                   "formulas": {"CAR": "Total Capital / RWA",
                                "CET1": "CET1 / RWA", "Tier1": "(CET1+AT1) / RWA"},
                   "buffers": "2.5% capital conservation buffer included in minimums"}
    g = grounding_block("Capital Adequacy", results)
    return _save(db, calc_type="car", framework="basel3", subject_ref=None, assessment_id=None,
                 inputs={"cet1": cet1, "additional_tier1": additional_tier1,
                         "tier2": tier2, "total_rwa": total_rwa},
                 results={**results, "grounding": g}, explanation=explanation,
                 tenant_id=tenant_id, created_by=created_by)


def leverage_ratio(db: Session, *, tier1_capital: float, total_exposure: float,
                   tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Basel III leverage ratio = Tier 1 / total exposure measure (≥3%)."""
    ratio = safe_div(tier1_capital, max(to_float(total_exposure), 1.0), 0.0)
    results = {"tier1_capital": round(tier1_capital, 2),
               "total_exposure": round(total_exposure, 2),
               "leverage_ratio_pct": pct(ratio), "min_pct": 3.0,
               "compliant": ratio >= 0.03}
    explanation = {"framework": "Basel III", "formula": "Tier1 / total exposure measure",
                   "minimum": "3%"}
    g = grounding_block("Leverage Ratio", results)
    return _save(db, calc_type="leverage", framework="basel3", subject_ref=None, assessment_id=None,
                 inputs={"tier1_capital": tier1_capital, "total_exposure": total_exposure},
                 results={**results, "grounding": g}, explanation=explanation,
                 tenant_id=tenant_id, created_by=created_by)


def portfolio_dashboard(db: Session, *, tenant_id: Optional[int] = None,
                        cet1: float = 0.0, additional_tier1: float = 0.0, tier2: float = 0.0,
                        created_by: Optional[str] = None) -> Dict[str, Any]:
    """Consolidated Basel/IFRS9 dashboard over the live exposure set."""
    exposures = da.portfolio_exposures(db)
    total_ead = sum(e["ead"] for e in exposures)
    total_rwa = 0.0
    total_ecl_12m = 0.0
    total_ecl_life = 0.0
    stages = {1: 0, 2: 0, 3: 0}
    for e in exposures:
        k = _irb_capital_ratio(e["pd"], e["lgd"])
        total_rwa += k * 12.5 * e["ead"]
        total_ecl_12m += expected_loss(e["pd"], e["lgd"], e["ead"])
        curve = marginal_pd_curve(e["pd"], 5)
        total_ecl_life += sum(mpd * e["lgd"] * e["ead"] / ((1.1) ** (t + 1)) for t, mpd in enumerate(curve))
        st = _stage(e["pd"], 0, None)["stage"]
        stages[st] += 1
    tier1 = cet1 + additional_tier1
    total_cap = tier1 + tier2
    results = {
        "exposure_count": len(exposures),
        "total_ead": round(total_ead, 2),
        "total_rwa": round(total_rwa, 2),
        "total_ecl_12m": round(total_ecl_12m, 2),
        "total_ecl_lifetime": round(total_ecl_life, 2),
        "stage_distribution": stages,
        "capital_required_8pct": round(total_rwa * 0.08, 2),
        "car_pct": pct(safe_div(total_cap, max(total_rwa, 1.0), 0.0)) if total_cap else None,
        "provision_coverage_pct": pct(safe_div(total_ecl_12m, total_ead, 0.0)),
    }
    g = grounding_block("Regulatory Dashboard", results)
    return _save(db, calc_type="dashboard", framework="basel3", subject_ref=None, assessment_id=None,
                 inputs={"cet1": cet1, "additional_tier1": additional_tier1, "tier2": tier2},
                 results={**results, "grounding": g},
                 explanation={"framework": "Basel III + IFRS 9",
                              "note": "aggregated over the live per-company exposure set"},
                 tenant_id=tenant_id, created_by=created_by)


def list_calcs(db: Session, *, calc_type: Optional[str] = None, framework: Optional[str] = None,
               limit: int = 50, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinRegulatoryCalc)
    if tenant_id is not None:
        q = q.filter(FinRegulatoryCalc.tenant_id == tenant_id)
    if calc_type:
        q = q.filter(FinRegulatoryCalc.calc_type == calc_type)
    if framework:
        q = q.filter(FinRegulatoryCalc.framework == framework)
    return [{"calc_id": c.id, "calc_type": c.calc_type, "framework": c.framework,
             "subject_ref": c.subject_ref, "checksum": c.checksum, "created_at": iso(c.created_at)}
            for c in q.order_by(FinRegulatoryCalc.id.desc()).limit(limit).all()]


def get_calc(db: Session, calc_id: int) -> Optional[Dict[str, Any]]:
    c = db.query(FinRegulatoryCalc).filter(FinRegulatoryCalc.id == calc_id).first()
    if not c:
        return None
    return {"calc_id": c.id, "calc_type": c.calc_type, "framework": c.framework,
            "subject_ref": c.subject_ref, "inputs": c.inputs, "results": c.results,
            "explanation": c.explanation, "created_at": iso(c.created_at)}
